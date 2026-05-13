"""Tests for the ``/admin/guardian/*`` admin router (PR-5).

Covers every route plus the shared-secret auth dependency.

Auth matrix:
* ``GUARDIAN_ADMIN_TOKEN`` unset → 503
* Missing header → 401
* Wrong header → 401
* Correct header → 200

Each route is exercised on the happy path with a fake Supabase backing the
store. ``/collect-now`` additionally exercises per-collector failure
isolation (one collector raises, others still run).
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bot.config import CHICAGO_TZ
from bot.services.system_guardian import store
from bot.services.system_guardian.admin_router import router
from tests.system_guardian._fake_supabase import FakeSupabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_TOKEN = "test-guardian-token-XYZ"
_HEADER = "X-Guardian-Admin-Token"


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def app():
    return _make_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def token_env():
    """Set the GUARDIAN_ADMIN_TOKEN env var for the duration of the test."""
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
def no_token_env():
    """Ensure GUARDIAN_ADMIN_TOKEN is unset for the duration of the test."""
    prior = os.environ.pop("GUARDIAN_ADMIN_TOKEN", None)
    try:
        yield
    finally:
        if prior is not None:
            os.environ["GUARDIAN_ADMIN_TOKEN"] = prior


@pytest.fixture
def fake_db():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        yield fake


# ---------------------------------------------------------------------------
# Auth gates
# ---------------------------------------------------------------------------


def test_missing_env_returns_503(client, no_token_env):
    r = client.get("/admin/guardian")
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


def test_missing_header_returns_401(client, token_env, fake_db):
    r = client.get("/admin/guardian")
    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


def test_wrong_header_returns_401(client, token_env, fake_db):
    r = client.get("/admin/guardian", headers={_HEADER: "wrong"})
    assert r.status_code == 401


def test_correct_header_passes(client, token_env, fake_db):
    r = client.get("/admin/guardian", headers={_HEADER: _VALID_TOKEN})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /admin/guardian (overview)
# ---------------------------------------------------------------------------


def test_overview_returns_shakedown_inactive_by_default(client, token_env, fake_db):
    r = client.get("/admin/guardian", headers={_HEADER: _VALID_TOKEN})
    assert r.status_code == 200
    body = r.json()
    assert body["shakedown"]["active"] is False
    assert body["shakedown"]["started_at"] is None
    assert body["shakedown"]["expires_at"] is None
    assert body["incidents"]["open"] == 0
    assert body["observations"]["last_24h"] == 0
    assert set(body["collectors"]["last_run"].keys()) == {
        "existing_health",
        "app_health",
        "supabase_app",
    }


def test_overview_reflects_active_shakedown(client, token_env, fake_db):
    store.set_shakedown_active(True)
    r = client.get("/admin/guardian", headers={_HEADER: _VALID_TOKEN})
    body = r.json()
    assert body["shakedown"]["active"] is True
    assert body["shakedown"]["started_at"] is not None
    assert body["shakedown"]["expires_at"] is not None


# ---------------------------------------------------------------------------
# GET /admin/guardian/incidents
# ---------------------------------------------------------------------------


def test_list_incidents_returns_open_by_default(client, token_env, fake_db):
    # Seed two open + one resolved.
    fake_db.tables["system_incidents"] = [
        {"id": "a", "status": "open", "severity": "critical",
         "signature": "s1", "category": "runtime_error",
         "count": 1, "first_seen": "2026-05-12", "last_seen": "2026-05-12",
         "last_notified_at": None, "title": "first"},
        {"id": "b", "status": "ack", "severity": "warning",
         "signature": "s2", "category": "silent_degradation",
         "count": 2, "first_seen": "2026-05-12", "last_seen": "2026-05-12",
         "last_notified_at": None, "title": "second"},
        {"id": "c", "status": "resolved", "severity": "info",
         "signature": "s3", "category": "runtime_error",
         "count": 1, "first_seen": "2026-05-10", "last_seen": "2026-05-10",
         "last_notified_at": None, "title": "third"},
    ]
    r = client.get("/admin/guardian/incidents", headers={_HEADER: _VALID_TOKEN})
    assert r.status_code == 200
    body = r.json()
    statuses = {i["status"] for i in body["incidents"]}
    assert statuses == {"open", "ack"}  # default excludes resolved


def test_list_incidents_limit_clamped(client, token_env, fake_db):
    r = client.get(
        "/admin/guardian/incidents?limit=999999",
        headers={_HEADER: _VALID_TOKEN},
    )
    # Doesn't crash; limit silently clamped to _MAX_INCIDENTS_LIMIT.
    assert r.status_code == 200


def test_list_incidents_limit_rejects_zero(client, token_env, fake_db):
    r = client.get(
        "/admin/guardian/incidents?limit=0",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 400


def test_list_incidents_filters_by_category(client, token_env, fake_db):
    fake_db.tables["system_incidents"] = [
        {"id": "a", "status": "open", "severity": "critical",
         "signature": "s1", "category": "runtime_error",
         "count": 1, "first_seen": "x", "last_seen": "x",
         "last_notified_at": None, "title": "rt"},
        {"id": "b", "status": "open", "severity": "warning",
         "signature": "s2", "category": "silent_degradation",
         "count": 1, "first_seen": "x", "last_seen": "x",
         "last_notified_at": None, "title": "sd"},
    ]
    r = client.get(
        "/admin/guardian/incidents?category=silent_degradation",
        headers={_HEADER: _VALID_TOKEN},
    )
    body = r.json()
    assert len(body["incidents"]) == 1
    assert body["incidents"][0]["category"] == "silent_degradation"


# ---------------------------------------------------------------------------
# GET /admin/guardian/incidents/{id}
# ---------------------------------------------------------------------------


def test_get_incident_returns_404_when_missing(client, token_env, fake_db):
    r = client.get(
        "/admin/guardian/incidents/missing-id",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 404


def test_get_incident_returns_row_plus_recent_observations(client, token_env, fake_db):
    fake_db.tables["system_incidents"] = [
        {"id": "abc", "status": "open", "severity": "warning",
         "signature": "sig_x", "category": "runtime_error",
         "count": 3, "first_seen": "x", "last_seen": "y",
         "last_notified_at": None, "title": "x"},
    ]
    fake_db.tables["system_observations"] = [
        {"id": "o1", "signature": "sig_x", "observed_at": "2026-05-12T00:00:00-05:00",
         "message": "m1", "source": "x", "event_type": "e"},
        {"id": "o2", "signature": "sig_x", "observed_at": "2026-05-12T01:00:00-05:00",
         "message": "m2", "source": "x", "event_type": "e"},
    ]
    r = client.get(
        "/admin/guardian/incidents/abc",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["incident"]["id"] == "abc"
    assert len(body["recent_observations"]) == 2


# ---------------------------------------------------------------------------
# GET /admin/guardian/incidents/{id}/debug-packet
# ---------------------------------------------------------------------------


def test_debug_packet_returns_json_contract(client, token_env, fake_db):
    fake_db.tables["system_incidents"] = [
        {"id": "abc", "status": "open", "severity": "critical",
         "signature": "sig_x", "category": "runtime_error",
         "count": 3, "first_seen": "2026-05-12T00:00:00-05:00",
         "last_seen": "2026-05-12T00:30:00-05:00",
         "last_notified_at": None, "title": "Boom",
         "affected_services": ["api"], "affected_surfaces": ["POST /api/chat"],
         "sample_messages": [{"observed_at": "x", "message": "stuff happened"}],
         "suspected_files": ["api/routes.py"], "affected_entities": {}},
    ]
    r = client.get(
        "/admin/guardian/incidents/abc/debug-packet",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 200
    body = r.json()
    # §12 keys present
    for key in (
        "title", "severity", "category", "symptom", "impact",
        "evidence", "likely_entrypoint", "suspected_files",
        "recent_changes", "reproduction", "suggested_tests", "vision_flags",
    ):
        assert key in body, f"missing key {key}"


def test_debug_packet_404_when_incident_missing(client, token_env, fake_db):
    r = client.get(
        "/admin/guardian/incidents/missing/debug-packet",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /admin/guardian/incidents/{id}/status
# ---------------------------------------------------------------------------


def test_post_status_happy_path(client, token_env, fake_db):
    fake_db.tables["system_incidents"] = [
        {"id": "abc", "status": "open", "severity": "warning",
         "signature": "sig_x", "category": "runtime_error",
         "count": 1, "first_seen": "x", "last_seen": "y",
         "last_notified_at": None, "title": "x"},
    ]
    send_mock = AsyncMock(return_value=True)
    with patch(
        "bot.services.system_guardian.notify._send_admin_dm", send_mock
    ):
        r = client.post(
            "/admin/guardian/incidents/abc/status",
            headers={_HEADER: _VALID_TOKEN},
            json={"status": "ack", "note": "looking"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["incident"]["status"] == "ack"
    # Status-change DM fired.
    send_mock.assert_called_once()
    # Guardian review audit row written.
    reviews = fake_db.tables.get("guardian_reviews") or []
    assert any(
        rev.get("review_type") == "status_change:open->ack" for rev in reviews
    )


def test_post_status_rejects_illegal_transition(client, token_env, fake_db):
    fake_db.tables["system_incidents"] = [
        {"id": "abc", "status": "resolved", "severity": "warning",
         "signature": "sig_x", "category": "runtime_error",
         "count": 1, "first_seen": "x", "last_seen": "y",
         "last_notified_at": None, "title": "x"},
    ]
    r = client.post(
        "/admin/guardian/incidents/abc/status",
        headers={_HEADER: _VALID_TOKEN},
        json={"status": "ack"},  # resolved → ack is illegal
    )
    assert r.status_code == 400
    assert "illegal" in r.json()["detail"].lower()


def test_post_status_404_when_missing(client, token_env, fake_db):
    r = client.post(
        "/admin/guardian/incidents/missing/status",
        headers={_HEADER: _VALID_TOKEN},
        json={"status": "ack"},
    )
    assert r.status_code == 404


def test_post_status_400_when_empty(client, token_env, fake_db):
    fake_db.tables["system_incidents"] = [
        {"id": "abc", "status": "open", "severity": "warning",
         "signature": "sig_x", "category": "runtime_error",
         "count": 1, "first_seen": "x", "last_seen": "y",
         "last_notified_at": None, "title": "x"},
    ]
    r = client.post(
        "/admin/guardian/incidents/abc/status",
        headers={_HEADER: _VALID_TOKEN},
        json={"status": "   "},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /admin/guardian/shakedown/ack
# ---------------------------------------------------------------------------


def test_shakedown_ack_returns_already_inactive_when_no_window(client, token_env, fake_db):
    r = client.post(
        "/admin/guardian/shakedown/ack",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "already_inactive"


def test_shakedown_ack_dispatches_summary_and_flips(client, token_env, fake_db):
    store.set_shakedown_active(True)
    send_mock = AsyncMock(return_value=True)
    with patch(
        "bot.services.system_guardian.notify._send_admin_dm", send_mock
    ):
        r = client.post(
            "/admin/guardian/shakedown/ack",
            headers={_HEADER: _VALID_TOKEN},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "acked"
    send_mock.assert_called_once()
    # Shakedown is now inactive.
    assert store.is_shakedown_active() is False


# ---------------------------------------------------------------------------
# POST /admin/guardian/shakedown/rearm
# ---------------------------------------------------------------------------


def test_shakedown_rearm_writes_active_sentinel(client, token_env, fake_db):
    r = client.post(
        "/admin/guardian/shakedown/rearm",
        headers={_HEADER: _VALID_TOKEN},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "armed"
    assert body["started_at"]
    assert body["expires_at"]
    assert store.is_shakedown_active() is True


# ---------------------------------------------------------------------------
# POST /admin/guardian/collect-now
# ---------------------------------------------------------------------------


def test_collect_now_returns_per_collector_counts(client, token_env, fake_db):
    async def _ok1():
        return [{"event_type": "x", "message": "a"}]

    async def _ok2():
        return [
            {"event_type": "x", "message": "b1"},
            {"event_type": "x", "message": "b2"},
        ]

    async def _empty():
        return []

    with (
        patch(
            "bot.services.system_guardian.collectors.collect_existing_health",
            _ok1,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_app_health",
            _ok2,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_supabase_app",
            _empty,
        ),
        # Stub notify dispatch to avoid Telegram side effects.
        patch(
            "bot.services.system_guardian.notify._send_admin_dm",
            AsyncMock(return_value=True),
        ),
    ):
        r = client.post(
            "/admin/guardian/collect-now",
            headers={_HEADER: _VALID_TOKEN},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["existing_health"] == 1
    assert body["app_health"] == 2
    assert body["supabase_app"] == 0
    assert body["total_observations"] == 3


def test_collect_now_isolates_collector_failure(client, token_env, fake_db):
    """A1 failure isolation: one collector raises, others still run."""
    async def _ok():
        return [{"event_type": "x", "message": "ok"}]

    async def _boom():
        raise RuntimeError("collector exploded")

    async def _empty():
        return []

    with (
        patch(
            "bot.services.system_guardian.collectors.collect_existing_health",
            _ok,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_app_health",
            _boom,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_supabase_app",
            _empty,
        ),
        patch(
            "bot.services.system_guardian.notify._send_admin_dm",
            AsyncMock(return_value=True),
        ),
    ):
        r = client.post(
            "/admin/guardian/collect-now",
            headers={_HEADER: _VALID_TOKEN},
        )
    assert r.status_code == 200
    body = r.json()
    # Failure is reported as -1, others continue.
    assert body["existing_health"] == 1
    assert body["app_health"] == -1
    assert body["supabase_app"] == 0
    # Total counts only the successful observations.
    assert body["total_observations"] == 1


def test_collect_now_per_collector_timeout_isolated(client, token_env, fake_db):
    """A collector that hangs past 5s must be reported as -1 without
    blocking the other collectors (per A1)."""
    async def _slow():
        await asyncio.sleep(10.0)
        return []

    async def _ok():
        return [{"event_type": "x", "message": "ok"}]

    # Drop the collector timeout to 0.05s so the test runs fast.
    with (
        patch(
            "bot.services.system_guardian.admin_router._COLLECT_NOW_TIMEOUT_S",
            0.05,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_existing_health",
            _slow,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_app_health",
            _ok,
        ),
        patch(
            "bot.services.system_guardian.collectors.collect_supabase_app",
            _ok,
        ),
        patch(
            "bot.services.system_guardian.notify._send_admin_dm",
            AsyncMock(return_value=True),
        ),
    ):
        r = client.post(
            "/admin/guardian/collect-now",
            headers={_HEADER: _VALID_TOKEN},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["existing_health"] == -1
    assert body["app_health"] == 1
    assert body["supabase_app"] == 1
