"""Plan 8 / C2 — insight body LLM polish tests.

Covers :func:`bot.services.coach_insights.polish_insight_body` and a wiring
smoke that confirms the polish call is gated by the dedup check (cost-bounded).
"""

from unittest.mock import patch, AsyncMock

from bot.services import coach_insights
from bot.services import db as _db
from bot.services import health_monitor


# ---------------------------------------------------------------------------
# polish_insight_body — unit tests
# ---------------------------------------------------------------------------


async def test_polish_insight_body_rewrites_reasoning_on_success():
    """Happy path: LLM returns prose → reasoning swapped + polished flag set.

    Also asserts the input dict is NOT mutated (callers may keep a reference).
    """
    sug = {
        "category": "program_drift",
        "title": "Program drifted 8 days behind",
        "reasoning": "Original rule-based body.",
        "proposed_action": {"program_id": "p1", "drift_days": 8},
    }
    with patch(
        "bot.services.llm.call_llm",
        new=AsyncMock(
            return_value="Their velocity program is 8 days behind. Consider archiving and rebuilding."
        ),
    ):
        out = await coach_insights.polish_insight_body(sug)
    assert (
        out["reasoning"]
        == "Their velocity program is 8 days behind. Consider archiving and rebuilding."
    )
    assert out["proposed_action"]["polished"] is True
    # Original sug must not be mutated.
    assert sug["reasoning"] == "Original rule-based body."
    assert "polished" not in sug["proposed_action"]


async def test_polish_insight_body_falls_back_on_llm_timeout():
    """When ``call_llm`` raises (timeout / network error), polish swallows
    and returns the suggestion unchanged — the rule-based body still ships.
    """
    sug = {
        "category": "program_drift",
        "title": "x",
        "reasoning": "rule-based",
        "proposed_action": {"program_id": "p1"},
    }
    with patch(
        "bot.services.llm.call_llm",
        new=AsyncMock(side_effect=TimeoutError("boom")),
    ):
        out = await coach_insights.polish_insight_body(sug)
    assert out["reasoning"] == "rule-based"
    assert "polished" not in out.get("proposed_action", {})


async def test_polish_insight_body_falls_back_on_empty_response():
    """Whitespace-only / empty LLM response → keep the rule-based body."""
    sug = {
        "category": "program_flag_mismatch",
        "title": "x",
        "reasoning": "rule-based",
        "proposed_action": {},
    }
    with patch(
        "bot.services.llm.call_llm",
        new=AsyncMock(return_value="   "),
    ):
        out = await coach_insights.polish_insight_body(sug)
    assert out["reasoning"] == "rule-based"
    assert "polished" not in out.get("proposed_action", {})


async def test_polish_insight_body_unknown_category_passthrough():
    """Categories outside the A4 map (e.g. ``pre_start_nudge``) must NEVER
    trigger an LLM call. Polish returns the suggestion unchanged.
    """
    sug = {
        "category": "pre_start_nudge",
        "title": "x",
        "reasoning": "rule-based",
        "proposed_action": {},
    }
    with patch(
        "bot.services.llm.call_llm",
        new=AsyncMock(return_value="should never reach this"),
    ) as llm_mock:
        out = await coach_insights.polish_insight_body(sug)
    llm_mock.assert_not_called()
    assert out["reasoning"] == "rule-based"
    assert "polished" not in out.get("proposed_action", {})


async def test_polish_insight_body_uses_correct_prompt_per_category():
    """Each A4 category resolves to its own prompt file. Verifies the
    routing in ``_POLISH_PROMPT_BY_CATEGORY``.
    """
    sug_drift = {
        "category": "program_drift",
        "title": "x",
        "reasoning": "rb",
        "proposed_action": {},
    }
    sug_mismatch = {
        "category": "program_flag_mismatch",
        "title": "x",
        "reasoning": "rb",
        "proposed_action": {},
    }
    sug_team = {
        "category": "team_program_lagging",
        "title": "x",
        "reasoning": "rb",
        "proposed_action": {},
    }

    with patch(
        "bot.services.llm.call_llm",
        new=AsyncMock(return_value="polished"),
    ):
        with patch("bot.services.llm.load_prompt") as load:
            load.return_value = "fake prompt body"
            await coach_insights.polish_insight_body(sug_drift)
            await coach_insights.polish_insight_body(sug_mismatch)
            await coach_insights.polish_insight_body(sug_team)
    prompts_loaded = [c.args[0] for c in load.call_args_list]
    assert prompts_loaded == [
        "insight_drift.md",
        "insight_mismatch.md",
        "insight_completion.md",
    ]


# ---------------------------------------------------------------------------
# Wiring integration — polish is cost-bounded: never called when dedup hits.
# ---------------------------------------------------------------------------


async def test_generate_coach_insights_skips_polish_when_dedup_hits():
    """When ``suggestion_exists_for_today`` returns True for the drift
    category, the digest pipeline must NOT call ``polish_insight_body`` for
    that drift insight (cost-bounded — never polish what we won't insert).

    Wiring contract: dedup check first, polish second, insert third.
    """
    program = {
        "program_id": "p1",
        "pitcher_id": "pitcher_polish_test",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-01",
        "current_day_index": 5,  # drift > 5 days vs 2026-05-01
        "held_days_count": 0,
        "generated_schedule_json": {"days": [{} for _ in range(84)]},
    }
    roster = [{"pitcher_id": "pitcher_polish_test", "name": "Polish Test"}]
    inserted = []

    # Polish should never be invoked on this path — wrap the real function
    # with a strict AsyncMock that would fail the assert below if called.
    polish_calls = []

    async def fake_polish(suggestion, **kw):
        polish_calls.append(suggestion)
        return suggestion

    with (
        patch.object(health_monitor, "_today_iso", return_value="2026-05-01"),
        patch(
            "bot.services.team_scope.get_team_roster_overview",
            return_value=roster,
        ),
        patch.object(
            _db,
            "list_programs_for_pitcher_summary",
            return_value=[program],
        ),
        patch.object(
            _db,
            "get_active_flags",
            return_value={"current_flag_level": "green"},
        ),
        patch.object(_db, "list_team_assigned_blocks", return_value=[]),
        # dedup says "already inserted today" for drift category
        patch.object(_db, "suggestion_exists_for_today", return_value=True),
        patch.object(
            _db,
            "insert_coach_suggestion",
            side_effect=lambda row: inserted.append(row) or row,
        ),
        patch.object(coach_insights, "polish_insight_body", new=fake_polish),
    ):
        new_count = await health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    # Drift was generated AND deduped → no insert, no polish.
    assert new_count == 0
    assert inserted == []
    assert polish_calls == [], (
        "polish must not run when dedup blocks insert "
        f"(saw {len(polish_calls)} polish calls)"
    )


async def test_generate_coach_insights_polishes_drift_before_insert():
    """Counterpart to the dedup-gated test: when dedup is clean, polish IS
    called, BEFORE the insert. Verifies argument order + that the polished
    body reaches ``insert_coach_suggestion``.
    """
    program = {
        "program_id": "p1",
        "pitcher_id": "pitcher_polish_test",
        "domain": "throwing",
        "parent_template_id": "velocity_12wk_v1",
        "start_date": "2026-04-01",
        "current_day_index": 5,  # drift > 5 days
        "held_days_count": 0,
        "generated_schedule_json": {"days": [{} for _ in range(84)]},
    }
    roster = [{"pitcher_id": "pitcher_polish_test", "name": "Polish Test"}]
    inserted = []
    call_order = []

    def fake_dedup(*args, **kwargs):
        call_order.append("dedup")
        return False

    async def fake_polish(suggestion, **kw):
        call_order.append("polish")
        out = dict(suggestion)
        out["reasoning"] = "LLM-polished version."
        pa = dict(out.get("proposed_action") or {})
        pa["polished"] = True
        out["proposed_action"] = pa
        return out

    def fake_insert(row):
        call_order.append("insert")
        inserted.append(row)
        return row

    with (
        patch.object(health_monitor, "_today_iso", return_value="2026-05-01"),
        patch(
            "bot.services.team_scope.get_team_roster_overview",
            return_value=roster,
        ),
        patch.object(
            _db,
            "list_programs_for_pitcher_summary",
            return_value=[program],
        ),
        patch.object(
            _db,
            "get_active_flags",
            return_value={"current_flag_level": "green"},
        ),
        patch.object(_db, "list_team_assigned_blocks", return_value=[]),
        patch.object(_db, "suggestion_exists_for_today", side_effect=fake_dedup),
        patch.object(_db, "insert_coach_suggestion", side_effect=fake_insert),
        patch.object(coach_insights, "polish_insight_body", new=fake_polish),
    ):
        new_count = await health_monitor._generate_coach_insights_for_team(
            "uchicago_baseball"
        )

    assert new_count == 1
    assert len(inserted) == 1
    # The polished body is what ships to insert_coach_suggestion.
    assert inserted[0]["reasoning"] == "LLM-polished version."
    assert inserted[0]["proposed_action"]["polished"] is True
    # Order: dedup THEN polish THEN insert (per category — only drift here
    # since we patched flags to green so mismatch is None, and no team blocks).
    assert call_order == ["dedup", "polish", "insert"]
