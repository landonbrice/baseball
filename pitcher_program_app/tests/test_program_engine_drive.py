"""Sprint C — the live drive (propose-and-confirm projection into check-ins).

Covers:
  - compose_drive_plan: green ships silently, yellow/red carry a proposal,
    rest days emit no throwing, plan shape matches what the entry build +
    DailyCard consume.
  - _select_plan_path fork order: engine drive first, flag-gated, falls
    through cleanly on no-coverage and on exceptions.
"""

from datetime import date

import pytest

from bot.services.program_engine import drive


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — a minimal active engine program row
# ─────────────────────────────────────────────────────────────────────────────


def _engine_row():
    def day(i, iso, throws=40, intensity=70, lifting=True):
        return {
            "day_index": i,
            "template_key": f"wk1_d{i + 1}",
            "date": iso,
            "anchor_kind": "calendar_relative",
            "phase_name": "Base Throwing",
            "intent_pct": intensity,
            "is_deload": False,
            "is_rest": False,
            "throwing_5tuple": {
                "distance_ft": 90,
                "throw_count": throws,
                "intensity_pct": intensity,
                "drill": "catch_play_extension",
                "note": None,
            },
            "lifting_blocks": (
                [{
                    "block_name": "Lower Strength",
                    "exercises": [
                        {"exercise_id": "ex_002", "sets": 3, "reps": "5", "intensity": None,
                         "superset_group": None, "note": None},
                        {"exercise_id": "ex_020", "sets": 3, "reps": "8", "intensity": None,
                         "superset_group": None, "note": None},
                    ],
                }] if lifting else []
            ),
            "day_focus": "Extension day",
            "cues": [],
        }

    return {
        "program_id": "prog-test-0001",
        "domain": "throwing",
        "engine_version": "v1",
        "start_date": "2026-07-13",
        "nominal_end_date": "2026-07-15",
        "generated_schedule_json": {
            "scaffold_kind": "engine_v1_authored",
            "days": [
                day(0, "2026-07-13"),
                day(1, "2026-07-14"),
                day(2, "2026-07-15"),
            ],
        },
    }


@pytest.fixture
def patched_drive(monkeypatch):
    monkeypatch.setattr(drive, "find_active_engine_program", lambda pid, d: _engine_row())
    monkeypatch.setattr(drive, "_exercise_name_map", lambda: {"ex_002": "Front Squat", "ex_020": "Chest-Supported Row"})
    return drive


GREEN = {"flag_level": "green", "modification_flags": [], "reasoning": ""}
YELLOW = {"flag_level": "yellow", "modification_flags": [], "reasoning": ""}
RED = {"flag_level": "red", "modification_flags": ["acute_medial_elbow_pain"], "reasoning": ""}


# ─────────────────────────────────────────────────────────────────────────────
# compose_drive_plan
# ─────────────────────────────────────────────────────────────────────────────


def test_green_day_ships_silently(patched_drive):
    plan = drive.compose_drive_plan("landon_brice", GREEN, {}, date(2026, 7, 13), checkin_inputs={"arm_feel": 9})
    assert plan["source"] == "engine_projected"
    assert plan["proposal"] is None
    assert plan["throwing"]["throw_count"] == 40
    assert plan["throwing"]["type"] == "program_throwing"
    # volume_summary MUST be a dict — a string here crashed every check-in
    # post-persist on 2026-07-13 (str.get AttributeError in the session-note
    # builder and progression.py)
    assert isinstance(plan["throwing"]["volume_summary"], dict)
    assert plan["throwing"]["volume_summary"]["total_throws_estimate"] == 40
    assert plan["throwing"]["day_type_label"]
    assert len(plan["lifting"]["exercises"]) == 2
    assert plan["lifting"]["exercises"][0]["name"] == "Front Squat"
    assert any(b["block_name"] == "Lower Strength" for b in plan["exercise_blocks"])
    assert plan["engine_projection"]["program_id"] == "prog-test-0001"


def test_yellow_day_carries_auto_accept_proposal(patched_drive):
    plan = drive.compose_drive_plan("landon_brice", YELLOW, {}, date(2026, 7, 13), checkin_inputs={"arm_feel": 6})
    prop = plan["proposal"]
    assert prop is not None
    assert prop["status"] == "proposed"
    assert prop["auto_accept"] is True
    assert prop["readiness_class"] == "yellow"
    assert prop["changes"]  # human-readable deltas present
    # YELLOW modulation: throws ×0.80 → 32
    assert plan["throwing"]["throw_count"] == 32
    # Volume-first philosophy (2026-07-13): ALL exercises survive; working
    # sets ≥3 lose one set (3 → 2 on both lifts here)
    assert len(plan["lifting"]["exercises"]) == 2
    assert all(ex["sets"] == 2 for ex in plan["lifting"]["exercises"])
    assert any("total sets" in c for c in prop["changes"])


def test_red_day_clamps_to_recovery(patched_drive):
    plan = drive.compose_drive_plan("landon_brice", RED, {}, date(2026, 7, 13), checkin_inputs={"arm_feel": 4})
    assert plan["proposal"]["readiness_class"] == "red"
    assert plan["throwing"]["throw_count"] <= 20
    assert plan["throwing"]["distance_ft"] <= 45


def test_arm_care_rider_attached(patched_drive):
    """Every drive day carries the legacy arm-care block (ratified 2026-07-13)."""
    plan = drive.compose_drive_plan("landon_brice", GREEN, {}, date(2026, 7, 13), checkin_inputs={"arm_feel": 9})
    assert plan["arm_care"] is not None
    # arm care blocks prepend the engine's lifting blocks
    assert "Arm Care" in plan["exercise_blocks"][0]["block_name"]
    assert any(b["block_name"] == "Lower Strength" for b in plan["exercise_blocks"])


@pytest.mark.asyncio
async def test_enrich_narrative_patches_entry(monkeypatch):
    """Async color: LLM text lands in plan_narrative; morning_brief untouched."""
    store = {"entry": {"plan_generated": {"source": "engine_projected"}}}

    async def fake_llm(sys, user, **k):
        return "Day one sets the base. Stay smooth on the RDLs."

    async def no_sleep(_):
        return None

    monkeypatch.setattr("bot.services.llm.call_llm", fake_llm)
    monkeypatch.setattr("asyncio.sleep", no_sleep)
    monkeypatch.setattr("bot.services.db.get_daily_entry", lambda pid, d: dict(store["entry"]))
    monkeypatch.setattr(
        "bot.services.db.upsert_daily_entry",
        lambda pid, e: store.update(entry=e),
    )
    plan = {
        "morning_brief": "Week 1, day 1 — Base Throwing.",
        "engine_projection": {"day_index": 0, "phase_name": "Base Throwing"},
        "lifting": {"exercises": [{"name": "Front Squat"}]},
        "throwing": {"volume_summary": {"text": "48 throws @ 60ft"}},
    }
    ok = await drive.enrich_narrative_async("landon_brice", date(2026, 7, 13), plan, {"name": "Landon"}, {"reasoning": "yellow via WHOOP"})
    assert ok is True
    assert "Stay smooth" in store["entry"]["plan_narrative"]
    assert store["entry"]["plan_narrative"].startswith("Week 1, day 1")
    assert store["entry"]["plan_generated"]["brief_enriched"] is True


@pytest.mark.asyncio
async def test_enrich_narrative_silent_on_llm_failure(monkeypatch):
    async def boom(*a, **k):
        raise TimeoutError("llm down")

    async def no_sleep(_):
        return None

    monkeypatch.setattr("bot.services.llm.call_llm", boom)
    monkeypatch.setattr("asyncio.sleep", no_sleep)
    ok = await drive.enrich_narrative_async("landon_brice", date(2026, 7, 13), {}, {}, {})
    assert ok is False  # silent, no raise


def test_no_active_program_returns_none(monkeypatch):
    monkeypatch.setattr(drive, "find_active_engine_program", lambda pid, d: None)
    assert drive.compose_drive_plan("landon_brice", GREEN, {}, date(2026, 7, 13)) is None


def test_date_outside_program_raises_for_caller_fallthrough(patched_drive):
    with pytest.raises(ValueError):
        drive.compose_drive_plan("landon_brice", GREEN, {}, date(2026, 8, 1))


def test_find_active_filters_by_date_coverage(monkeypatch):
    row = _engine_row()

    class _Q:
        def __init__(self, data):
            self._d = data
        def select(self, *a): return self
        def eq(self, *a): return self
        @property
        def not_(self): return self
        def is_(self, *a): return self
        def execute(self): return type("R", (), {"data": self._d})()

    class _C:
        def table(self, name): return _Q([row])

    monkeypatch.setattr("bot.services.db.get_client", lambda: _C())
    assert drive.find_active_engine_program("p", date(2026, 7, 14)) is not None
    assert drive.find_active_engine_program("p", date(2026, 9, 1)) is None


# ─────────────────────────────────────────────────────────────────────────────
# Fork order in _select_plan_path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fork_engine_drive_first(monkeypatch):
    from bot.services import checkin_service as cs

    sentinel = {"source": "engine_projected", "proposal": None}
    monkeypatch.setattr(cs, "_is_engine_drive_enabled", lambda pid: True)
    monkeypatch.setattr(
        "bot.services.program_engine.drive.compose_drive_plan",
        lambda *a, **k: sentinel,
    )
    plan, program_id, hold = await cs._select_plan_path(
        "landon_brice", GREEN, {}, date(2026, 7, 13), checkin_inputs={}, triage_rationale_detail=None,
    )
    assert plan is sentinel
    assert program_id is None and hold is None  # date-keyed: no counter advance


@pytest.mark.asyncio
async def test_fork_flag_off_skips_engine(monkeypatch):
    from bot.services import checkin_service as cs

    called = {"drive": False}

    def _boom(*a, **k):
        called["drive"] = True
        raise AssertionError("engine drive must not run with flag off")

    monkeypatch.setattr(cs, "_is_engine_drive_enabled", lambda pid: False)
    monkeypatch.setattr("bot.services.program_engine.drive.compose_drive_plan", _boom)
    monkeypatch.setattr(cs, "_is_program_aware_enabled", lambda pid: False)

    async def _legacy(*a, **k):
        return {"source": "python_fallback"}

    monkeypatch.setattr(cs, "generate_plan", _legacy)
    plan, _, _ = await cs._select_plan_path(
        "landon_brice", GREEN, {}, date(2026, 7, 13), checkin_inputs={}, triage_rationale_detail=None,
    )
    assert called["drive"] is False
    assert plan["source"] == "python_fallback"


@pytest.mark.asyncio
async def test_fork_engine_failure_falls_through(monkeypatch):
    from bot.services import checkin_service as cs

    monkeypatch.setattr(cs, "_is_engine_drive_enabled", lambda pid: True)
    monkeypatch.setattr(
        "bot.services.program_engine.drive.compose_drive_plan",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("date not covered")),
    )
    monkeypatch.setattr(cs, "_is_program_aware_enabled", lambda pid: False)

    async def _legacy(*a, **k):
        return {"source": "python_fallback"}

    monkeypatch.setattr(cs, "generate_plan", _legacy)
    plan, _, _ = await cs._select_plan_path(
        "landon_brice", GREEN, {}, date(2026, 7, 13), checkin_inputs={}, triage_rationale_detail=None,
    )
    assert plan["source"] == "python_fallback"
