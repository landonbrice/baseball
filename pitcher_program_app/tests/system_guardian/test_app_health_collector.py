"""Tests for the ``app_health`` collector (PR-4).

Covers:

* Happy path: monkeypatched ``/health`` returns a known payload — assert
  observation shapes, severities, source, and DB-connectivity propagation.
* ``/health`` 500 → critical observation.
* ``/health`` raises → ONE ``collector_failure`` observation, no re-raise.
* ``/admin/health`` 401/403 (auth wall) → info observation.
* ``/admin/health`` 404 → no observation produced (skip pattern).
* ``/admin/health`` 5xx → critical observation.
* 5s timeout: monkeypatch the in-process probe to sleep past the ceiling,
  assert one ``collector_failure`` with a "timed out" message.
* "Not yet wired" notes are always emitted for recent_errors_count and
  route_latency_p95.
* Public API check.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from bot.services.system_guardian.collectors import app_health
from bot.services.system_guardian.collectors.app_health import collect_app_health


# ---------------------------------------------------------------------------
# Helpers: patch the in-process probe so we don't actually run ASGI in tests.
# ---------------------------------------------------------------------------


def _make_probe_table(
    *,
    health_status: int | None = 200,
    health_payload: dict | None = None,
    health_error: str | None = None,
    admin_status: int | None = 401,
    admin_error: str | None = None,
):
    """Build an async ``_probe_route`` replacement that returns canned data
    keyed on path."""

    async def fake_probe(path: str):
        if path == "/health":
            return (health_status, health_payload, health_error)
        if path == "/admin/health":
            return (admin_status, None, admin_error)
        return (None, None, f"unexpected path: {path}")

    return fake_probe


def _default_health_payload() -> dict:
    return {
        "status": "ok",
        "mini_app_url_set": True,
        "disable_auth": False,
        "supabase_connected": True,
        "pitcher_count": 12,
        "bot_token_set": True,
        "deepseek_key_set": True,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_returns_expected_observation_shape():
    fake = _make_probe_table(health_payload=_default_health_payload())
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    # Every observation has the required column-aligned keys.
    required_keys = {"observed_at", "source", "event_type", "severity_hint", "message"}
    for obs in out:
        assert required_keys <= set(obs.keys()), f"missing keys in {obs}"
        assert obs["source"] == "app_health.collect_app_health"
        assert obs["severity_hint"] in {"critical", "warning", "info"}

    # /health observation present + info severity.
    health = [o for o in out if o["event_type"] == "app_health_endpoint_status"]
    assert len(health) == 1
    assert health[0]["severity_hint"] == "info"
    assert health[0]["metadata"]["status_code"] == 200
    assert health[0]["metadata"]["supabase_connected"] is True

    # db connectivity propagated as a separate observation.
    db = [o for o in out if o["event_type"] == "db_connectivity_via_health"]
    assert len(db) == 1
    assert db[0]["severity_hint"] == "info"
    assert db[0]["metadata"]["pitcher_count"] == 12

    # admin/health (401 → auth wall intact → info).
    admin = [o for o in out if o["event_type"] == "admin_health_endpoint_status"]
    assert len(admin) == 1
    assert admin[0]["severity_hint"] == "info"
    assert admin[0]["metadata"]["auth_wall_intact"] is True

    # Not-yet-wired notes present.
    not_wired_events = {
        "recent_errors_count_not_wired",
        "route_latency_p95_not_wired",
    }
    assert not_wired_events <= {o["event_type"] for o in out}

    # No collector_failure on the happy path.
    failures = [o for o in out if o["event_type"] == "collector_failure"]
    assert failures == []


@pytest.mark.asyncio
async def test_health_500_is_critical():
    fake = _make_probe_table(
        health_status=500, health_payload=None
    )
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    health = [o for o in out if o["event_type"] == "app_health_endpoint_status"]
    assert len(health) == 1
    assert health[0]["severity_hint"] == "critical"
    assert "500" in health[0]["message"]
    # No db connectivity observation because payload was None.
    db = [o for o in out if o["event_type"] == "db_connectivity_via_health"]
    assert db == []


@pytest.mark.asyncio
async def test_health_raises_yields_critical_observation_not_reraise():
    """When the probe itself returns an error string (httpx exception path)
    the collector emits a critical observation — the collector overall does
    not re-raise."""
    fake = _make_probe_table(
        health_status=None,
        health_payload=None,
        health_error="ConnectionError: simulated",
    )
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    # /health observation is critical because the probe raised.
    health = [o for o in out if o["event_type"] == "app_health_endpoint_status"]
    assert len(health) == 1
    assert health[0]["severity_hint"] == "critical"
    assert "ConnectionError" in health[0]["message"]


@pytest.mark.asyncio
async def test_db_connectivity_critical_when_supabase_connected_false():
    payload = _default_health_payload() | {"supabase_connected": False}
    fake = _make_probe_table(health_payload=payload)
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    db = [o for o in out if o["event_type"] == "db_connectivity_via_health"]
    assert len(db) == 1
    assert db[0]["severity_hint"] == "critical"
    assert db[0]["metadata"]["supabase_connected"] is False


@pytest.mark.asyncio
async def test_db_connectivity_skipped_when_field_missing():
    """If the /health payload doesn't carry supabase_connected, we don't
    fabricate the observation."""
    payload = {"status": "ok"}  # no supabase_connected field
    fake = _make_probe_table(health_payload=payload)
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    db = [o for o in out if o["event_type"] == "db_connectivity_via_health"]
    assert db == []


# ---------------------------------------------------------------------------
# /admin/health behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_health_404_is_skipped():
    fake = _make_probe_table(
        health_payload=_default_health_payload(),
        admin_status=404,
    )
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    admin = [o for o in out if o["event_type"] == "admin_health_endpoint_status"]
    assert admin == [], "404 from /admin/health must be silent"


@pytest.mark.asyncio
async def test_admin_health_403_is_info_with_auth_wall_marker():
    fake = _make_probe_table(
        health_payload=_default_health_payload(),
        admin_status=403,
    )
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    admin = [o for o in out if o["event_type"] == "admin_health_endpoint_status"]
    assert len(admin) == 1
    assert admin[0]["severity_hint"] == "info"
    assert admin[0]["metadata"]["auth_wall_intact"] is True


@pytest.mark.asyncio
async def test_admin_health_500_is_critical():
    fake = _make_probe_table(
        health_payload=_default_health_payload(),
        admin_status=503,
    )
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    admin = [o for o in out if o["event_type"] == "admin_health_endpoint_status"]
    assert len(admin) == 1
    assert admin[0]["severity_hint"] == "critical"
    assert "503" in admin[0]["message"]


@pytest.mark.asyncio
async def test_admin_health_200_is_info():
    fake = _make_probe_table(
        health_payload=_default_health_payload(),
        admin_status=200,
    )
    with patch.object(app_health, "_probe_route", fake):
        out = await collect_app_health()

    admin = [o for o in out if o["event_type"] == "admin_health_endpoint_status"]
    assert len(admin) == 1
    assert admin[0]["severity_hint"] == "info"


# ---------------------------------------------------------------------------
# Timeout path (A1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_emits_timeout_failure_when_probe_hangs(monkeypatch):
    """If a probe hangs past the 5s ceiling, emit one collector_failure with
    a "timed out" message. We monkeypatch the timeout constant to keep tests
    fast."""
    monkeypatch.setattr(app_health, "_COLLECTOR_TIMEOUT_S", 0.05)

    async def slow_probe(path: str):
        await asyncio.sleep(0.5)
        return (200, _default_health_payload(), None)

    with patch.object(app_health, "_probe_route", slow_probe):
        out = await collect_app_health()

    assert isinstance(out, list)
    assert len(out) == 1
    failure = out[0]
    assert failure["event_type"] == "collector_failure"
    assert failure["severity_hint"] == "warning"
    assert "timed out" in failure["message"].lower()
    assert failure["metadata"]["category"] == "guardian_self"
    assert failure["metadata"]["code"] == "collector_failure"


# ---------------------------------------------------------------------------
# Catastrophic catch-all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_does_not_raise_when_run_probes_raises():
    """If something inside the probe pipeline raises (not a per-probe error
    string), the outer wrap turns it into one collector_failure. We force
    this by patching _run_probes."""

    async def boom():
        raise RuntimeError("simulated catastrophic failure")

    with patch.object(app_health, "_run_probes", boom):
        out = await collect_app_health()

    assert isinstance(out, list)
    assert len(out) == 1
    failure = out[0]
    assert failure["event_type"] == "collector_failure"
    assert failure["severity_hint"] == "warning"
    assert "RuntimeError" in failure["message"]
    assert failure["metadata"]["code"] == "collector_failure"


# ---------------------------------------------------------------------------
# Public API surface check
# ---------------------------------------------------------------------------


def test_collectors_subpackage_exports_app_health():
    """The collectors subpackage exports ``collect_app_health``."""
    from bot.services.system_guardian.collectors import collect_app_health as ch
    assert callable(ch)
    assert asyncio.iscoroutinefunction(ch)


def test_collect_app_health_is_coroutine_function():
    """A1 contract: collectors are async."""
    assert asyncio.iscoroutinefunction(collect_app_health)
