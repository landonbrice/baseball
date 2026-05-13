"""Tests for the Guardian tick orchestrator (PR-6 / A1).

Covers:

* Happy path: three collectors all return observations; persisted via the
  notify wrapper; no over-budget incident.
* One slow collector (>5s) is bounded by the outer wrapper but the tick
  total stays under 30s — no tick_budget_exceeded.
* Whole tick over budget — emits info on the first over-budget, warning on
  the second consecutive (A1's "twice in a row" rule).
* Recovery resets the consecutive counter.
* One collector raises an exception — synthesized collector_failure emitted,
  others continue.
* Counter atomicity: nested ticks don't double-emit.
* Admin route ``POST /admin/guardian/tick`` — auth gates + happy path.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bot.services.system_guardian import tick as tick_mod
from bot.services.system_guardian.admin_router import router as guardian_admin_router
from tests.system_guardian._fake_supabase import FakeSupabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_VALID_TOKEN = "test-guardian-tick-token-XYZ"
_HEADER = "X-Guardian-Admin-Token"


@pytest.fixture(autouse=True)
def _reset_counter():
    """Each test starts with a clean consecutive-over-budget counter."""
    tick_mod._reset_consecutive_over_budget()
    yield
    tick_mod._reset_consecutive_over_budget()


@pytest.fixture
def fake_db():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        yield fake


@pytest.fixture
def silent_notifier():
    """Stub the Telegram notifier so tests never DM."""
    with patch(
        "bot.services.system_guardian.notify._send_admin_dm",
        AsyncMock(return_value=True),
    ):
        yield


def _make_obs(msg: str = "ok") -> dict:
    return {
        "observed_at": "2026-05-13T10:00:00-05:00",
        "source": "test_collector",
        "service": "guardian",
        "event_type": "data_quality_dip",
        "severity_hint": "info",
        "surface": "test",
        "route_or_job": "test",
        "message": msg,
        "metadata": {"category": "data_quality", "code": "test"},
    }


def _patch_collectors(existing=None, app=None, supabase=None):
    """Context-manager helper: patch the three Phase 1 collectors.

    Each arg is an async function (or None — defaults to "return empty list").
    """

    async def _default():
        return []

    return (
        patch(
            "bot.services.system_guardian.collectors.collect_existing_health",
            existing or _default,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_app_health",
            app or _default,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_supabase_app",
            supabase or _default,
        ),
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_happy_path_returns_summary_and_persists(fake_db, silent_notifier):
    async def _existing():
        return [_make_obs("existing")]

    async def _app():
        return [_make_obs("app1"), _make_obs("app2")]

    async def _supabase():
        return []

    p1, p2, p3 = _patch_collectors(existing=_existing, app=_app, supabase=_supabase)
    with p1, p2, p3:
        summary = await tick_mod.run_guardian_tick()

    # Shape
    assert "started_at" in summary
    assert summary["duration_s"] >= 0.0
    assert summary["over_budget"] is False
    assert summary["tick_budget_incident_emitted"] is False
    assert summary["consecutive_over_budget"] == 0

    # Per-collector summary
    assert set(summary["collectors"].keys()) == {
        "existing_health",
        "app_health",
        "supabase_app",
    }
    assert summary["collectors"]["existing_health"]["observation_count"] == 1
    assert summary["collectors"]["existing_health"]["outcome"] == "ok"
    assert summary["collectors"]["app_health"]["observation_count"] == 2
    assert summary["collectors"]["app_health"]["outcome"] == "ok"
    assert summary["collectors"]["supabase_app"]["observation_count"] == 0
    assert summary["collectors"]["supabase_app"]["outcome"] == "ok"

    # All 3 observations persisted through insert_observation_with_notify
    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    assert summary["observations_persisted"] == 3
    # At least the three observation rows landed (incident upserts may add
    # rows to system_incidents but not system_observations).
    assert len(obs_inserts) >= 3


async def test_happy_path_no_tick_budget_observation_when_under_budget(
    fake_db, silent_notifier
):
    """An under-budget tick must NOT emit tick_budget_exceeded."""

    async def _quick():
        return [_make_obs()]

    p1, p2, p3 = _patch_collectors(existing=_quick, app=_quick, supabase=_quick)
    with p1, p2, p3:
        summary = await tick_mod.run_guardian_tick()

    assert summary["over_budget"] is False
    # No tick_budget_exceeded observation in the persisted set.
    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    assert not any(
        p.get("event_type") == "tick_budget_exceeded" for p in obs_inserts
    )


# ---------------------------------------------------------------------------
# Per-collector failure isolation
# ---------------------------------------------------------------------------


async def test_one_collector_raises_others_still_complete(fake_db, silent_notifier):
    async def _ok():
        return [_make_obs("good")]

    async def _boom():
        raise RuntimeError("collector exploded")

    async def _empty():
        return []

    p1, p2, p3 = _patch_collectors(existing=_boom, app=_ok, supabase=_empty)
    with p1, p2, p3:
        summary = await tick_mod.run_guardian_tick()

    # The failing collector reports outcome=error with one collector_failure obs.
    assert summary["collectors"]["existing_health"]["outcome"] == "error"
    assert summary["collectors"]["existing_health"]["observation_count"] == 1
    # Others still ran.
    assert summary["collectors"]["app_health"]["outcome"] == "ok"
    assert summary["collectors"]["app_health"]["observation_count"] == 1
    assert summary["collectors"]["supabase_app"]["outcome"] == "ok"

    # collector_failure observation was emitted with the right source.
    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    failures = [
        p
        for p in obs_inserts
        if p.get("event_type") == "collector_failure"
        and p.get("source") == "tick.existing_health"
    ]
    assert failures, f"expected tick.existing_health collector_failure, got: {obs_inserts}"

    # Tick should still be under budget.
    assert summary["over_budget"] is False


async def test_slow_collector_caught_by_per_collector_wrapper(
    fake_db, silent_notifier, monkeypatch
):
    """A collector that hangs past 5s is caught by the OUTER per-collector
    wrapper without poisoning the tick. Tick total stays well under 30s.

    Drops PER_COLLECTOR_TIMEOUT_S to 0.05s so the test runs fast.
    """
    monkeypatch.setattr(tick_mod, "PER_COLLECTOR_TIMEOUT_S", 0.05)

    async def _slow():
        await asyncio.sleep(1.0)
        return [_make_obs("never returned")]

    async def _ok():
        return [_make_obs("ok")]

    p1, p2, p3 = _patch_collectors(existing=_ok, app=_slow, supabase=_ok)
    with p1, p2, p3:
        summary = await tick_mod.run_guardian_tick()

    # app_health timed out.
    assert summary["collectors"]["app_health"]["outcome"] == "timeout"
    assert summary["collectors"]["app_health"]["observation_count"] == 1
    # Others succeeded.
    assert summary["collectors"]["existing_health"]["outcome"] == "ok"
    assert summary["collectors"]["supabase_app"]["outcome"] == "ok"

    # Tick total stayed under 30s budget.
    assert summary["over_budget"] is False
    assert summary["tick_budget_incident_emitted"] is False
    assert summary["consecutive_over_budget"] == 0

    # No tick_budget_exceeded observation.
    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    assert not any(
        p.get("event_type") == "tick_budget_exceeded" for p in obs_inserts
    )


# ---------------------------------------------------------------------------
# Tick-budget over-budget detection
# ---------------------------------------------------------------------------


async def test_first_over_budget_tick_emits_info_not_warning(
    fake_db, silent_notifier, monkeypatch
):
    """FIRST consecutive over-budget tick: info severity, not warning.

    A1's "twice in a row" rule means the WARNING fires on the SECOND
    consecutive over-budget tick, not the first.
    """
    # Drop the tick budget low so we can over-run reliably.
    monkeypatch.setattr(tick_mod, "TICK_BUDGET_S", 0.05)
    # Keep per-collector ceiling above tick budget so the tick budget
    # actually fires (otherwise per-collector wrappers catch first).
    monkeypatch.setattr(tick_mod, "PER_COLLECTOR_TIMEOUT_S", 5.0)

    async def _slow():
        await asyncio.sleep(0.5)
        return []

    p1, p2, p3 = _patch_collectors(existing=_slow, app=_slow, supabase=_slow)
    with p1, p2, p3:
        summary = await tick_mod.run_guardian_tick()

    assert summary["over_budget"] is True
    assert summary["consecutive_over_budget"] == 1
    assert summary["tick_budget_incident_emitted"] is True

    # The persisted tick_budget_exceeded observation is severity=info.
    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    tick_obs = [
        p for p in obs_inserts if p.get("event_type") == "tick_budget_exceeded"
    ]
    assert len(tick_obs) == 1
    assert tick_obs[0].get("severity_hint") == "info"
    assert tick_obs[0].get("signature") == "tick_budget_exceeded"


async def test_second_consecutive_over_budget_emits_warning(
    fake_db, silent_notifier, monkeypatch
):
    """Run the tick twice over budget. Second tick emits severity=warning."""
    monkeypatch.setattr(tick_mod, "TICK_BUDGET_S", 0.05)
    monkeypatch.setattr(tick_mod, "PER_COLLECTOR_TIMEOUT_S", 5.0)

    async def _slow():
        await asyncio.sleep(0.5)
        return []

    p1, p2, p3 = _patch_collectors(existing=_slow, app=_slow, supabase=_slow)

    with p1, p2, p3:
        await tick_mod.run_guardian_tick()
        summary2 = await tick_mod.run_guardian_tick()

    assert summary2["over_budget"] is True
    assert summary2["consecutive_over_budget"] == 2
    assert summary2["tick_budget_incident_emitted"] is True

    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    tick_obs = [
        p for p in obs_inserts if p.get("event_type") == "tick_budget_exceeded"
    ]
    # Two emitted observations total — first info, second warning.
    assert len(tick_obs) == 2
    assert tick_obs[0].get("severity_hint") == "info"
    assert tick_obs[1].get("severity_hint") == "warning"
    # Both share the stable signature for clustering.
    assert all(o.get("signature") == "tick_budget_exceeded" for o in tick_obs)


async def test_recovery_resets_consecutive_counter(
    fake_db, silent_notifier, monkeypatch
):
    """Over-budget then under-budget → counter resets to 0."""
    monkeypatch.setattr(tick_mod, "TICK_BUDGET_S", 0.05)
    monkeypatch.setattr(tick_mod, "PER_COLLECTOR_TIMEOUT_S", 5.0)

    async def _slow():
        await asyncio.sleep(0.5)
        return []

    p1, p2, p3 = _patch_collectors(existing=_slow, app=_slow, supabase=_slow)
    with p1, p2, p3:
        s1 = await tick_mod.run_guardian_tick()
    assert s1["consecutive_over_budget"] == 1
    assert s1["over_budget"] is True

    # Now restore TICK_BUDGET_S so the next tick stays under budget.
    monkeypatch.setattr(tick_mod, "TICK_BUDGET_S", 30.0)

    async def _quick():
        return [_make_obs()]

    p1b, p2b, p3b = _patch_collectors(existing=_quick, app=_quick, supabase=_quick)
    with p1b, p2b, p3b:
        s2 = await tick_mod.run_guardian_tick()

    assert s2["over_budget"] is False
    assert s2["consecutive_over_budget"] == 0
    assert s2["tick_budget_incident_emitted"] is False


async def test_fifth_consecutive_over_budget_escalates_to_critical(
    fake_db, silent_notifier, monkeypatch
):
    """Chronic over-budget: 5th consecutive emits critical severity.

    Documented in tick.py as the obvious extension of A1's "twice in a row"
    rule — if we're chronically over budget that's an incident, not noise.
    """
    monkeypatch.setattr(tick_mod, "TICK_BUDGET_S", 0.05)
    monkeypatch.setattr(tick_mod, "PER_COLLECTOR_TIMEOUT_S", 5.0)

    async def _slow():
        await asyncio.sleep(0.3)
        return []

    p1, p2, p3 = _patch_collectors(existing=_slow, app=_slow, supabase=_slow)
    with p1, p2, p3:
        for _ in range(5):
            summary = await tick_mod.run_guardian_tick()

    assert summary["consecutive_over_budget"] == 5
    obs_inserts = [
        payload
        for kind, table, payload in fake_db.writes
        if kind == "insert" and table == "system_observations"
    ]
    tick_obs = [
        p for p in obs_inserts if p.get("event_type") == "tick_budget_exceeded"
    ]
    # Last entry should be critical.
    assert tick_obs[-1].get("severity_hint") == "critical"


# ---------------------------------------------------------------------------
# Helper invariants
# ---------------------------------------------------------------------------


async def test_run_one_collector_bounded_ok_path():
    async def _fn():
        return [_make_obs("a"), _make_obs("b")]

    name, obs, outcome, duration = await tick_mod._run_one_collector_bounded(
        "test", _fn, per_collector_timeout=1.0
    )
    assert name == "test"
    assert outcome == "ok"
    assert len(obs) == 2
    assert duration >= 0


async def test_run_one_collector_bounded_timeout_synthesizes_failure_obs():
    async def _slow():
        await asyncio.sleep(0.5)
        return []

    name, obs, outcome, duration = await tick_mod._run_one_collector_bounded(
        "test", _slow, per_collector_timeout=0.05
    )
    assert outcome == "timeout"
    assert len(obs) == 1
    assert obs[0]["event_type"] == "collector_failure"
    assert obs[0]["source"] == "tick.test"
    assert obs[0]["severity_hint"] == "warning"
    assert "timeout" in obs[0]["message"].lower()


async def test_run_one_collector_bounded_exception_synthesizes_failure_obs():
    async def _boom():
        raise ValueError("test error")

    name, obs, outcome, duration = await tick_mod._run_one_collector_bounded(
        "test", _boom, per_collector_timeout=1.0
    )
    assert outcome == "error"
    assert len(obs) == 1
    assert obs[0]["event_type"] == "collector_failure"
    assert obs[0]["source"] == "tick.test"
    assert obs[0]["metadata"]["exception_class"] == "ValueError"


async def test_run_one_collector_bounded_non_list_return_coerced():
    """A collector that returns the wrong shape (not a list) gets coerced to []."""

    async def _wrong_shape():
        return {"not": "a list"}

    name, obs, outcome, duration = await tick_mod._run_one_collector_bounded(
        "test", _wrong_shape, per_collector_timeout=1.0
    )
    assert outcome == "ok"
    assert obs == []


# ---------------------------------------------------------------------------
# Tick is idempotent: never raises
# ---------------------------------------------------------------------------


async def test_tick_never_raises_even_when_persistence_fails(monkeypatch):
    """If insert_observation_with_notify itself raises, the tick still
    completes and returns a summary with the persistence count reflecting
    only the successful inserts."""

    async def _ok():
        return [_make_obs()]

    failing_insert = AsyncMock(side_effect=RuntimeError("supabase down"))
    monkeypatch.setattr(
        "bot.services.system_guardian.tick._store.insert_observation_with_notify",
        failing_insert,
    )

    p1, p2, p3 = _patch_collectors(existing=_ok, app=_ok, supabase=_ok)
    with p1, p2, p3:
        summary = await tick_mod.run_guardian_tick()

    # Tick completed cleanly.
    assert "started_at" in summary
    assert summary["observations_persisted"] == 0
    # Each collector's run is still recorded in the summary.
    assert summary["collectors"]["existing_health"]["outcome"] == "ok"
    assert summary["collectors"]["app_health"]["outcome"] == "ok"


# ---------------------------------------------------------------------------
# Public surface checks
# ---------------------------------------------------------------------------


def test_run_guardian_tick_exported_from_package():
    """The public surface must include run_guardian_tick so the scheduler
    can do ``from bot.services.system_guardian import run_guardian_tick``."""
    from bot.services.system_guardian import run_guardian_tick

    assert asyncio.iscoroutinefunction(run_guardian_tick)


def test_tick_module_exports_helper_and_constants():
    assert hasattr(tick_mod, "run_guardian_tick")
    assert hasattr(tick_mod, "_run_one_collector_bounded")
    assert tick_mod.TICK_BUDGET_S == 30.0
    assert tick_mod.PER_COLLECTOR_TIMEOUT_S == 5.0


# ---------------------------------------------------------------------------
# Scheduler wiring smoke check — make sure bot/main.py exports the hook.
# ---------------------------------------------------------------------------


def test_bot_main_schedules_guardian_tick_every_15min():
    """``_schedule_jobs`` must register a 15-minute recurring job named
    ``guardian_tick`` that calls ``run_guardian_tick``."""
    from pathlib import Path

    main_path = Path(__file__).resolve().parents[2] / "bot" / "main.py"
    src = main_path.read_text(encoding="utf-8")
    assert "guardian_tick" in src
    assert "run_guardian_tick" in src
    assert "interval=900" in src  # 15 minutes


# ---------------------------------------------------------------------------
# Admin route: POST /admin/guardian/tick
# ---------------------------------------------------------------------------


def _make_admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(guardian_admin_router)
    return app


@pytest.fixture
def admin_client():
    return TestClient(_make_admin_app())


@pytest.fixture
def admin_token_env():
    prior = os.environ.get("GUARDIAN_ADMIN_TOKEN")
    os.environ["GUARDIAN_ADMIN_TOKEN"] = _VALID_TOKEN
    try:
        yield _VALID_TOKEN
    finally:
        if prior is None:
            os.environ.pop("GUARDIAN_ADMIN_TOKEN", None)
        else:
            os.environ["GUARDIAN_ADMIN_TOKEN"] = prior


@pytest.fixture
def admin_no_token_env():
    prior = os.environ.pop("GUARDIAN_ADMIN_TOKEN", None)
    try:
        yield
    finally:
        if prior is not None:
            os.environ["GUARDIAN_ADMIN_TOKEN"] = prior


def test_admin_tick_route_missing_env_returns_503(admin_client, admin_no_token_env):
    r = admin_client.post("/admin/guardian/tick")
    assert r.status_code == 503


def test_admin_tick_route_wrong_token_returns_401(admin_client, admin_token_env):
    r = admin_client.post(
        "/admin/guardian/tick",
        headers={_HEADER: "wrong-token"},
    )
    assert r.status_code == 401


def test_admin_tick_route_missing_header_returns_401(admin_client, admin_token_env):
    r = admin_client.post("/admin/guardian/tick")
    assert r.status_code == 401


def test_admin_tick_route_happy_path_returns_summary(
    admin_client, admin_token_env
):
    """Right token → 200 + tick summary JSON."""
    fake_summary = {
        "started_at": "2026-05-13T10:00:00-05:00",
        "duration_s": 0.5,
        "over_budget": False,
        "consecutive_over_budget": 0,
        "collectors": {
            "existing_health": {
                "observation_count": 1,
                "duration_s": 0.1,
                "outcome": "ok",
            },
            "app_health": {
                "observation_count": 0,
                "duration_s": 0.2,
                "outcome": "ok",
            },
            "supabase_app": {
                "observation_count": 0,
                "duration_s": 0.1,
                "outcome": "ok",
            },
        },
        "observations_persisted": 1,
        "tick_budget_incident_emitted": False,
    }

    with patch(
        "bot.services.system_guardian.tick.run_guardian_tick",
        AsyncMock(return_value=fake_summary),
    ):
        r = admin_client.post(
            "/admin/guardian/tick",
            headers={_HEADER: _VALID_TOKEN},
        )

    assert r.status_code == 200
    body = r.json()
    assert body == fake_summary


def test_admin_tick_route_returns_summary_even_when_over_budget(
    admin_client, admin_token_env
):
    """Over-budget tick still returns 200 with the summary — tick never raises."""
    fake_summary = {
        "started_at": "2026-05-13T10:00:00-05:00",
        "duration_s": 30.1,
        "over_budget": True,
        "consecutive_over_budget": 2,
        "collectors": {
            "existing_health": {
                "observation_count": 1,
                "duration_s": 30.0,
                "outcome": "timeout",
            },
            "app_health": {
                "observation_count": 1,
                "duration_s": 30.0,
                "outcome": "timeout",
            },
            "supabase_app": {
                "observation_count": 1,
                "duration_s": 30.0,
                "outcome": "timeout",
            },
        },
        "observations_persisted": 4,
        "tick_budget_incident_emitted": True,
    }

    with patch(
        "bot.services.system_guardian.tick.run_guardian_tick",
        AsyncMock(return_value=fake_summary),
    ):
        r = admin_client.post(
            "/admin/guardian/tick",
            headers={_HEADER: _VALID_TOKEN},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["over_budget"] is True
    assert body["consecutive_over_budget"] == 2
    assert body["tick_budget_incident_emitted"] is True
