"""Tests for the ``supabase_app`` collector (PR-4).

Covers:

* Happy path: synthetic rows from each table produce the expected
  observations + heartbeat.
* Each table-query path tested in isolation:
    - daily_entries with N stale rows → warning vs heartbeat-only.
    - research_load_log at 50% degraded → warning; 5% degraded → info.
    - research_load_log with high mean injection chars → warning.
    - ui_fallback_log > 10 in 24h → warning.
    - whoop_daily missing rows → one warning per missing pitcher.
* One table query raises → ``signal_failure`` info note, OTHER signals
  still emitted.
* Whole client unreachable → ONE ``collector_failure`` observation.
* 5s timeout path.
* Public API surface check.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from bot.services.system_guardian.collectors import supabase_app
from bot.services.system_guardian.collectors.supabase_app import collect_supabase_app


# ---------------------------------------------------------------------------
# Fake Supabase client — minimal builder chain matching `supabase-py`.
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data):
        self.data = data


class _TableQuery:
    def __init__(self, table_name: str, fixtures: dict):
        self.table_name = table_name
        self.fixtures = fixtures
        # Track filter state if a test wants to assert on it.
        self.filters: list[tuple[str, str, str]] = []

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def gte(self, col, val):
        self.filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self.filters.append(("lte", col, val))
        return self

    def execute(self):
        data = self.fixtures.get(self.table_name, [])
        if isinstance(data, Exception):
            raise data
        return _Resp(data)


class _FakeClient:
    """Returns canned rows per table; raises on tables marked as failing."""

    def __init__(self, fixtures: dict):
        self.fixtures = fixtures
        # last-touched query so tests can inspect filters if they want.
        self.last_query: _TableQuery | None = None

    def table(self, name: str):
        q = _TableQuery(name, self.fixtures)
        self.last_query = q
        return q


def _patch_get_client(fake_client):
    """Patch the lazy import that ``_run_sync_collect`` does."""
    return patch("bot.services.db.get_client", return_value=fake_client)


def _patch_get_client_raises(exc: Exception):
    def boom():
        raise exc

    return patch("bot.services.db.get_client", side_effect=boom)


# ---------------------------------------------------------------------------
# Happy path — quiet system
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_clean_system_emits_heartbeat_and_info_only():
    fake = _FakeClient(
        {
            "daily_entries": [
                {
                    "pitcher_id": "p1",
                    "date": "2026-05-13",
                    "team_id": "uchicago_baseball",
                    "pre_training": {"arm_feel": 7},
                    "plan_generated": {"source": "llm_enriched"},
                },
            ],
            "research_load_log": [
                {"degraded": False, "total_chars": 2000},
                {"degraded": False, "total_chars": 2500},
            ],
            "ui_fallback_log": [],
            "whoop_tokens": [{"pitcher_id": "p1"}, {"pitcher_id": "p2"}],
            "whoop_daily": [{"pitcher_id": "p1"}, {"pitcher_id": "p2"}],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    # All required keys present.
    required = {"observed_at", "source", "event_type", "severity_hint", "message"}
    for obs in out:
        assert required <= set(obs.keys()), f"missing keys in {obs}"
        assert obs["source"] == "supabase_app.collect_supabase_app"

    types = [o["event_type"] for o in out]
    assert "daily_entries_stale" in types
    assert "research_load_anomaly" in types
    assert "ui_fallback_log_spike" in types
    assert "whoop_daily_freshness_summary" in types
    assert "supabase_app_heartbeat" in types

    # No warnings, no failures.
    warnings = [o for o in out if o["severity_hint"] == "warning"]
    assert warnings == [], f"expected no warnings on clean run; got {warnings}"
    failures = [o for o in out if o["event_type"] == "collector_failure"]
    assert failures == []
    sig_failures = [o for o in out if o["event_type"].endswith("_query_failed")]
    assert sig_failures == []


# ---------------------------------------------------------------------------
# daily_entries_stale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_entries_5_stale_emits_warning():
    # 5 entries with arm_feel but no plan_generated → > threshold of 3.
    stale_rows = [
        {
            "pitcher_id": f"p{i}",
            "date": "2026-05-13",
            "team_id": "uchicago_baseball",
            "pre_training": {"arm_feel": 7},
            "plan_generated": None,
        }
        for i in range(5)
    ]
    fake = _FakeClient(
        {
            "daily_entries": stale_rows,
            "research_load_log": [],
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    stale = [o for o in out if o["event_type"] == "daily_entries_stale"]
    assert len(stale) == 1
    assert stale[0]["severity_hint"] == "warning"
    assert stale[0]["metadata"]["stale_count"] == 5
    assert stale[0]["metadata"]["category"] == "silent_degradation"


@pytest.mark.asyncio
async def test_daily_entries_zero_stale_emits_info():
    fake = _FakeClient(
        {
            "daily_entries": [
                {
                    "pitcher_id": "p1",
                    "date": "2026-05-13",
                    "team_id": "uchicago_baseball",
                    "pre_training": {"arm_feel": 7},
                    "plan_generated": {"source": "llm_enriched"},
                }
            ],
            "research_load_log": [],
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    stale = [o for o in out if o["event_type"] == "daily_entries_stale"]
    assert len(stale) == 1
    assert stale[0]["severity_hint"] == "info"
    assert stale[0]["metadata"]["stale_count"] == 0


@pytest.mark.asyncio
async def test_daily_entries_skips_rows_without_arm_feel():
    """No arm_feel = not checked in = not stale, regardless of plan_generated."""
    rows = [
        # No arm_feel — should be ignored.
        {
            "pitcher_id": "p1",
            "date": "2026-05-13",
            "team_id": "uchicago_baseball",
            "pre_training": {},
            "plan_generated": None,
        },
        # arm_feel + plan → not stale.
        {
            "pitcher_id": "p2",
            "date": "2026-05-13",
            "team_id": "uchicago_baseball",
            "pre_training": {"arm_feel": 8},
            "plan_generated": {"source": "llm_enriched"},
        },
    ]
    fake = _FakeClient(
        {
            "daily_entries": rows,
            "research_load_log": [],
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    stale = [o for o in out if o["event_type"] == "daily_entries_stale"]
    assert stale[0]["metadata"]["stale_count"] == 0


# ---------------------------------------------------------------------------
# research_load_anomaly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_research_load_50pct_degraded_emits_warning():
    rows = [{"degraded": True, "total_chars": 4000}] * 5 + [
        {"degraded": False, "total_chars": 3000}
    ] * 5  # 50% degraded → > 25% threshold
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": rows,
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    rla = [o for o in out if o["event_type"] == "research_load_anomaly"]
    assert len(rla) == 1
    assert rla[0]["severity_hint"] == "warning"
    assert rla[0]["metadata"]["degraded_count"] == 5
    assert rla[0]["metadata"]["total_calls_24h"] == 10
    assert rla[0]["metadata"]["category"] == "llm_degradation"


@pytest.mark.asyncio
async def test_research_load_5pct_degraded_emits_info():
    rows = [{"degraded": True, "total_chars": 3000}] + [
        {"degraded": False, "total_chars": 3000}
    ] * 19  # 5% degraded → < 25%
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": rows,
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    rla = [o for o in out if o["event_type"] == "research_load_anomaly"]
    assert len(rla) == 1
    assert rla[0]["severity_hint"] == "info"
    assert rla[0]["metadata"]["degraded_count"] == 1


@pytest.mark.asyncio
async def test_research_load_high_injection_chars_emits_warning():
    """LLM-regression canary: mean injection chars > 8000 fires warning even
    if degraded share is 0."""
    rows = [{"degraded": False, "total_chars": 12000}] * 10
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": rows,
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    rla = [o for o in out if o["event_type"] == "research_load_anomaly"]
    assert len(rla) == 1
    assert rla[0]["severity_hint"] == "warning"
    assert rla[0]["metadata"]["mean_total_chars"] == 12000


@pytest.mark.asyncio
async def test_research_load_empty_emits_info_zero_calls():
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": [],
            "ui_fallback_log": [],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    rla = [o for o in out if o["event_type"] == "research_load_anomaly"]
    assert len(rla) == 1
    assert rla[0]["severity_hint"] == "info"
    assert rla[0]["metadata"]["total_calls_24h"] == 0


# ---------------------------------------------------------------------------
# ui_fallback_log_spike
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ui_fallback_spike_over_threshold_emits_warning():
    rows = [
        {"id": i, "exercise_id": f"ex_{i % 3}", "surface": "daily_card", "logged_at": "x"}
        for i in range(15)
    ]
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": [],
            "ui_fallback_log": rows,
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    spike = [o for o in out if o["event_type"] == "ui_fallback_log_spike"]
    assert len(spike) == 1
    assert spike[0]["severity_hint"] == "warning"
    assert spike[0]["metadata"]["count_24h"] == 15
    assert spike[0]["metadata"]["category"] == "frontend_degradation"
    assert len(spike[0]["metadata"]["top_exercises"]) <= 5


@pytest.mark.asyncio
async def test_ui_fallback_under_threshold_emits_info():
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": [],
            "ui_fallback_log": [
                {"id": 1, "exercise_id": "ex_1", "surface": "daily_card"}
            ],
            "whoop_tokens": [],
            "whoop_daily": [],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    spike = [o for o in out if o["event_type"] == "ui_fallback_log_spike"]
    assert len(spike) == 1
    assert spike[0]["severity_hint"] == "info"


# ---------------------------------------------------------------------------
# whoop_daily_freshness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whoop_missing_emits_one_warning_per_missing_pitcher():
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": [],
            "ui_fallback_log": [],
            "whoop_tokens": [
                {"pitcher_id": "p_kamat"},
                {"pitcher_id": "p_kwinter"},
                {"pitcher_id": "p_richert"},
            ],
            # Only one pitcher pulled today.
            "whoop_daily": [{"pitcher_id": "p_kamat"}],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    missing = [o for o in out if o["event_type"] == "whoop_daily_freshness"]
    assert len(missing) == 2
    pitcher_ids = {o["metadata"]["pitcher_id"] for o in missing}
    assert pitcher_ids == {"p_kwinter", "p_richert"}
    for o in missing:
        assert o["severity_hint"] == "warning"

    summary = [o for o in out if o["event_type"] == "whoop_daily_freshness_summary"]
    assert len(summary) == 1
    assert summary[0]["metadata"]["linked_count"] == 3
    assert summary[0]["metadata"]["pulled_count"] == 1
    assert summary[0]["metadata"]["missing_count"] == 2


@pytest.mark.asyncio
async def test_whoop_all_pulled_emits_no_warnings():
    fake = _FakeClient(
        {
            "daily_entries": [],
            "research_load_log": [],
            "ui_fallback_log": [],
            "whoop_tokens": [{"pitcher_id": "p1"}, {"pitcher_id": "p2"}],
            "whoop_daily": [{"pitcher_id": "p1"}, {"pitcher_id": "p2"}],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    missing = [o for o in out if o["event_type"] == "whoop_daily_freshness"]
    assert missing == []
    summary = [o for o in out if o["event_type"] == "whoop_daily_freshness_summary"]
    assert len(summary) == 1
    assert summary[0]["severity_hint"] == "info"


# ---------------------------------------------------------------------------
# Per-signal isolation: one table fails → others still run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_table_query_raises_others_still_produce():
    """Schema drift on research_load_log shouldn't kill the rest of the run."""
    fake = _FakeClient(
        {
            "daily_entries": [
                {
                    "pitcher_id": "p1",
                    "date": "2026-05-13",
                    "team_id": "uchicago_baseball",
                    "pre_training": {"arm_feel": 7},
                    "plan_generated": {"source": "llm_enriched"},
                }
            ],
            # This Exception is raised inside .execute().
            "research_load_log": RuntimeError(
                "column research_load_log.total_chars does not exist"
            ),
            "ui_fallback_log": [],
            "whoop_tokens": [{"pitcher_id": "p1"}],
            "whoop_daily": [{"pitcher_id": "p1"}],
        }
    )

    with _patch_get_client(fake):
        out = await collect_supabase_app()

    # signal_failure obs for the raising table.
    sig_failures = [
        o
        for o in out
        if o["event_type"] == "research_load_anomaly_query_failed"
    ]
    assert len(sig_failures) == 1
    assert sig_failures[0]["severity_hint"] == "info"
    assert sig_failures[0]["metadata"]["category"] == "guardian_self"
    assert sig_failures[0]["metadata"]["code"] == "signal_failure"

    # Other signals still produced.
    types = {o["event_type"] for o in out}
    assert "daily_entries_stale" in types
    assert "ui_fallback_log_spike" in types
    assert "whoop_daily_freshness_summary" in types
    assert "supabase_app_heartbeat" in types

    # No top-level collector_failure.
    cf = [o for o in out if o["event_type"] == "collector_failure"]
    assert cf == []


# ---------------------------------------------------------------------------
# Catastrophic catch-all: get_client raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_whole_client_unreachable_emits_one_collector_failure():
    with _patch_get_client_raises(
        RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    ):
        out = await collect_supabase_app()

    assert isinstance(out, list)
    assert len(out) == 1
    failure = out[0]
    assert failure["event_type"] == "collector_failure"
    assert failure["severity_hint"] == "warning"
    assert "RuntimeError" in failure["message"]
    assert failure["metadata"]["category"] == "guardian_self"
    assert failure["metadata"]["code"] == "collector_failure"


# ---------------------------------------------------------------------------
# Timeout path (A1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_emits_timeout_failure_when_sync_hangs(monkeypatch):
    """If the sync table-query block hangs past the 5s ceiling, emit one
    collector_failure with a "timed out" message."""
    import time as _time

    monkeypatch.setattr(supabase_app, "_COLLECTOR_TIMEOUT_S", 0.05)

    def slow_collect():
        _time.sleep(0.5)
        return []

    with patch.object(supabase_app, "_run_sync_collect", slow_collect):
        out = await collect_supabase_app()

    assert isinstance(out, list)
    assert len(out) == 1
    failure = out[0]
    assert failure["event_type"] == "collector_failure"
    assert failure["severity_hint"] == "warning"
    assert "timed out" in failure["message"].lower()


# ---------------------------------------------------------------------------
# Public API surface check
# ---------------------------------------------------------------------------


def test_collectors_subpackage_exports_supabase_app():
    from bot.services.system_guardian.collectors import collect_supabase_app as cs
    assert callable(cs)
    assert asyncio.iscoroutinefunction(cs)


def test_collect_supabase_app_is_coroutine_function():
    assert asyncio.iscoroutinefunction(collect_supabase_app)
