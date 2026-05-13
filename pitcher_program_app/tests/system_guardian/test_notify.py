"""Tests for ``bot.services.system_guardian.notify`` (PR-5).

Asserts the 5 A6 rules in :func:`notify.maybe_notify_admin` plus the
status-change DM helper + ``send_shakedown_summary`` self-observation.

All Telegram dispatch is mocked via the module-level ``_send_admin_dm``
function — these tests do not hit Telegram.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.system_guardian import notify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_incident(
    *,
    incident_id: str = "inc-1",
    severity: str = "warning",
    last_notified_at: str | None = None,
    status: str = "open",
    title: str = "an incident",
    signature: str = "obs_aaaaaaaa",
    count: int = 1,
    category: str = "runtime_error",
) -> dict:
    return {
        "id": incident_id,
        "severity": severity,
        "last_notified_at": last_notified_at,
        "status": status,
        "title": title,
        "signature": signature,
        "count": count,
        "category": category,
    }


def _mk_observation(
    *,
    severity: str = "warning",
    prev_severity: str | None = None,
    message: str = "x",
) -> dict:
    return {
        "severity_hint": severity,
        "severity": severity,
        "message": message,
        "_prev_severity": prev_severity,
    }


# ---------------------------------------------------------------------------
# Rule 1: shakedown active -> no DM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule1_shakedown_active_suppresses_dm():
    obs = _mk_observation()
    inc = _mk_incident(last_notified_at=None)  # would otherwise trigger rule 2
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=True),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is False
    send_mock.assert_not_called()
    advance_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Rule 2: first occurrence (last_notified_at is None) -> DM + advance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule2_first_occurrence_dms_and_advances():
    obs = _mk_observation(severity="critical")
    inc = _mk_incident(severity="critical", last_notified_at=None)
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is True
    send_mock.assert_called_once()
    advance_mock.assert_called_once_with("inc-1", severity="critical")


@pytest.mark.asyncio
async def test_rule2_does_not_advance_if_dm_failed():
    """If Telegram dispatch fails, last_notified_at must NOT advance so the
    next observation retries the DM."""
    obs = _mk_observation()
    inc = _mk_incident(last_notified_at=None)
    send_mock = AsyncMock(return_value=False)  # DM failed
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is False
    send_mock.assert_called_once()
    advance_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Rule 3: severity escalation -> DM + advance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule3_severity_escalation_warning_to_critical_dms():
    """incident_severity (post-upsert) > _prev_severity (pre-upsert) -> DM."""
    obs = _mk_observation(severity="critical", prev_severity="warning")
    inc = _mk_incident(
        severity="critical",  # post-upsert band
        last_notified_at="2026-05-12T00:00:00-05:00",  # already notified before
    )
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is True
    send_mock.assert_called_once()
    advance_mock.assert_called_once_with("inc-1", severity="critical")


@pytest.mark.asyncio
async def test_rule3_info_to_warning_dms():
    obs = _mk_observation(severity="warning", prev_severity="info")
    inc = _mk_incident(
        severity="warning",
        last_notified_at="2026-05-12T00:00:00-05:00",
    )
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is True
    send_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Rule 5: same-band count increment -> NO DM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rule5_count_increment_same_band_no_dm():
    """The most-common silenced case: incident already notified, no escalation."""
    obs = _mk_observation(severity="warning", prev_severity="warning")
    inc = _mk_incident(
        severity="warning",
        last_notified_at="2026-05-12T00:00:00-05:00",
        count=5,
    )
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is False
    send_mock.assert_not_called()
    advance_mock.assert_not_called()


@pytest.mark.asyncio
async def test_rule5_severity_de_escalation_no_dm():
    """Critical→warning is a de-escalation, NOT an escalation. No DM."""
    obs = _mk_observation(severity="warning", prev_severity="critical")
    inc = _mk_incident(
        severity="critical",  # upsert doesn't de-escalate
        last_notified_at="2026-05-12T00:00:00-05:00",
    )
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is False
    send_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Defensive: no incident id -> skip (avoid sending a DM we can't dedup)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_incident_id_skips_dm():
    obs = _mk_observation()
    inc = _mk_incident(last_notified_at=None)
    inc.pop("id")
    send_mock = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is False
    send_mock.assert_not_called()


# ---------------------------------------------------------------------------
# Shakedown lookup failure -> still dispatch (better to over-notify than to
# silently swallow a real alert)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shakedown_lookup_failure_still_dispatches():
    obs = _mk_observation()
    inc = _mk_incident(last_notified_at=None)
    send_mock = AsyncMock(return_value=True)
    advance_mock = MagicMock()
    with (
        patch.object(
            notify._store, "is_shakedown_active", side_effect=RuntimeError("boom")
        ),
        patch.object(notify, "_send_admin_dm", send_mock),
        patch.object(notify._store, "advance_last_notified_at", advance_mock),
    ):
        sent = await notify.maybe_notify_admin(obs, inc)
    assert sent is True
    send_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Rule 4 surrogate: notify_status_change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_status_change_dms_on_transition():
    inc = _mk_incident(status="ack")
    send_mock = AsyncMock(return_value=True)
    with patch.object(notify, "_send_admin_dm", send_mock):
        sent = await notify.notify_status_change(
            inc, "open", "ack", note="Looking into this"
        )
    assert sent is True
    send_mock.assert_called_once()
    # The DM body should contain the prev->new transition.
    args, _ = send_mock.call_args
    assert "open->ack" in args[0]


@pytest.mark.asyncio
async def test_notify_status_change_skips_noop():
    inc = _mk_incident(status="ack")
    send_mock = AsyncMock(return_value=True)
    with patch.object(notify, "_send_admin_dm", send_mock):
        sent = await notify.notify_status_change(inc, "ack", "ack")
    assert sent is False
    send_mock.assert_not_called()


# ---------------------------------------------------------------------------
# send_shakedown_summary writes the self-observation regardless of DM success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_shakedown_summary_writes_self_observation_and_flips_state():
    from datetime import datetime, timedelta

    from bot.config import CHICAGO_TZ

    started = datetime.now(CHICAGO_TZ) - timedelta(hours=2)
    captured_inserts: list[dict] = []
    captured_state_flips: list[tuple[bool, object]] = []

    def _fake_insert(payload: dict) -> dict | None:
        captured_inserts.append(payload)
        return payload

    def _fake_set_state(active: bool, started_at=None) -> None:
        captured_state_flips.append((active, started_at))

    send_mock = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "get_shakedown_started_at", return_value=started),
        patch.object(
            notify._store,
            "list_shakedown_signatures",
            return_value=[
                {
                    "signature": "sig_a",
                    "title": "a",
                    "severity": "critical",
                    "count": 3,
                },
                {
                    "signature": "sig_b",
                    "title": "b",
                    "severity": "warning",
                    "count": 1,
                },
            ],
        ),
        patch.object(notify._store, "insert_observation", _fake_insert),
        patch.object(notify._store, "set_shakedown_active", _fake_set_state),
        patch.object(notify, "_send_admin_dm", send_mock),
    ):
        await notify.send_shakedown_summary()

    # DM dispatched
    send_mock.assert_called_once()
    body = send_mock.call_args.args[0]
    assert "shakedown summary" in body.lower()
    assert "critical" in body.lower()

    # Self-observation persisted
    summary_obs = [
        i for i in captured_inserts
        if i.get("event_type") == "shakedown_summary_sent"
    ]
    assert summary_obs
    assert summary_obs[0]["metadata"]["signature_count"] == 2
    assert summary_obs[0]["metadata"]["dm_dispatched"] is True

    # State flipped to inactive
    assert captured_state_flips == [(False, None)]


@pytest.mark.asyncio
async def test_send_shakedown_summary_with_no_active_window_does_not_flip_state():
    """Idempotence: calling on an already-inactive shakedown still DMs (a
    no-incidents summary) but does NOT write set_shakedown_active(False)."""
    captured_inserts: list[dict] = []
    captured_state_flips: list[tuple[bool, object]] = []

    def _fake_insert(payload: dict) -> dict | None:
        captured_inserts.append(payload)
        return payload

    def _fake_set_state(active: bool, started_at=None) -> None:
        captured_state_flips.append((active, started_at))

    send_mock = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "get_shakedown_started_at", return_value=None),
        patch.object(
            notify._store,
            "list_shakedown_signatures",
            return_value=[],
        ),
        patch.object(notify._store, "insert_observation", _fake_insert),
        patch.object(notify._store, "set_shakedown_active", _fake_set_state),
        patch.object(notify, "_send_admin_dm", send_mock),
    ):
        await notify.send_shakedown_summary()

    # DM still goes out (empty summary)
    send_mock.assert_called_once()
    # No state flip because there was no active window to flip.
    assert captured_state_flips == []


# ---------------------------------------------------------------------------
# Formatter sanity: redaction is applied at emit time (D6 dual-pass)
# ---------------------------------------------------------------------------


def test_format_incident_line_redacts_jwt_in_title():
    """Even if a JWT survived write-time redaction, the read-time pass on the
    formatter must strip it before forming the Telegram body."""
    jwt = "eyJabc123.def456.ghi789"
    inc = _mk_incident(title=f"something exploded {jwt} ouch")
    obs = _mk_observation()
    body = notify._format_incident_line(obs, inc)
    assert "eyJabc123" not in body
    assert "REDACTED" in body


# ---------------------------------------------------------------------------
# 2026-05-13 Bug B: DM headline must show the SIGNAL name, not the literal
# category ``runtime_error`` (which incidents.py defaults to for any obs
# without an explicit category).
# ---------------------------------------------------------------------------


def test_format_incident_line_uses_signal_not_runtime_error_for_info_obs():
    """The 12:10 PM symptom: every DM read ``[INFO] runtime_error - ...``
    because the formatter used ``incident.category`` directly. We now pull
    the signal from ``observation.metadata.signal`` so the headline is
    actually informative."""
    obs = {
        "severity_hint": "info",
        "message": "research_load_anomaly: 0 calls in last 24h",
        "service": "supabase",
        "event_type": "research_load_anomaly",
        "metadata": {
            "category": "existing_health",
            "code": "research_load_anomaly",
            "signal": "research_load_anomaly",
        },
    }
    inc = _mk_incident(
        severity="info",
        category="runtime_error",  # the legacy default that triggered the bug
        title="research_load_anomaly: 0 calls in last 24h",
        signature="aaaaaaaa1234",
        count=1,
    )
    body = notify._format_incident_line(obs, inc)
    # Must NOT contain the misleading default category.
    assert "runtime_error" not in body
    # MUST contain the actual signal name.
    assert "research_load_anomaly" in body
    # The service:signal prefix.
    assert "supabase:research_load_anomaly" in body


def test_format_incident_line_falls_back_to_event_type_when_no_metadata_signal():
    """When metadata.signal isn't set (e.g. legacy obs from a path that
    pre-dates the supabase_app collector), event_type stands in. Still no
    ``runtime_error``."""
    obs = {
        "severity_hint": "info",
        "message": "plan_health_summary heartbeat",
        "service": "guardian",
        "event_type": "plan_health_summary",
        # NO metadata.signal / code
    }
    inc = _mk_incident(
        severity="info",
        category="runtime_error",
        title="plan_health_summary heartbeat",
    )
    body = notify._format_incident_line(obs, inc)
    assert "runtime_error" not in body
    assert "plan_health_summary" in body


def test_format_incident_line_snapshot_matches_expected_layout():
    """Snapshot: exact format the recipient sees for a typical INFO obs."""
    obs = {
        "severity_hint": "info",
        "message": "research_load_anomaly: 2 calls, 0 degraded (0%)",
        "service": "supabase",
        "event_type": "research_load_anomaly",
        "metadata": {"signal": "research_load_anomaly"},
    }
    inc = _mk_incident(
        severity="info",
        category="existing_health",
        title="research_load_anomaly: 2 calls, 0 degraded (0%)",
        signature="abcdef123456more",
        count=3,
    )
    body = notify._format_incident_line(obs, inc)
    assert body == (
        "[INFO] supabase:research_load_anomaly - "
        "research_load_anomaly: 2 calls, 0 degraded (0%) "
        "(count=3) sig=abcdef123456"
    )


# ---------------------------------------------------------------------------
# 2026-05-13 Bug A: ack-flood. Both the manual ack path and the auto-expire
# path flow through send_shakedown_summary; both must baseline-ack the
# currently-open incidents BEFORE flipping shakedown off so the next tick's
# A6 rule 2 (first-occurrence DM) does not fire for every signature seen.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_shakedown_summary_advances_last_notified_on_open_incidents():
    """After ack, every previously-open incident must have ``last_notified_at``
    set + ``severity`` stamped, so subsequent observations on the same
    signatures are treated as already-notified baseline."""
    from datetime import datetime, timedelta

    from bot.config import CHICAGO_TZ

    started = datetime.now(CHICAGO_TZ) - timedelta(hours=2)
    open_incidents = [
        {
            "id": "inc-1",
            "severity": "info",
            "last_notified_at": None,  # baseline -> would re-fire rule 2
            "status": "open",
            "title": "research_load_anomaly: 0 calls",
            "signature": "sig_research_aaaaaaaaaaaa",
            "category": "runtime_error",
            "count": 1,
        },
        {
            "id": "inc-2",
            "severity": "warning",
            "last_notified_at": None,
            "status": "open",
            "title": "daily_entries_stale: 4 partials",
            "signature": "sig_de_stale_bbbbbbbbbbbb",
            "category": "silent_degradation",
            "count": 1,
        },
    ]

    captured_advances: list[tuple[str, str | None]] = []

    def _fake_advance(incident_id, severity=None):
        captured_advances.append((incident_id, severity))
        return {"id": incident_id}

    captured_state_flips: list[tuple[bool, object]] = []

    def _fake_set_state(active, started_at=None):
        # Ensure baseline-ack happens BEFORE the flag flips off.
        # If this fires before advance was called, the order is wrong.
        captured_state_flips.append((active, started_at, list(captured_advances)))

    send_mock = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "get_shakedown_started_at", return_value=started),
        patch.object(notify._store, "list_shakedown_signatures", return_value=[]),
        patch.object(notify._store, "insert_observation", lambda p: p),
        patch.object(notify._store, "list_open_incidents", return_value=open_incidents),
        patch.object(notify._store, "advance_last_notified_at", _fake_advance),
        patch.object(notify._store, "set_shakedown_active", _fake_set_state),
        patch.object(notify, "_send_admin_dm", send_mock),
    ):
        await notify.send_shakedown_summary()

    # Every open incident got stamped with its current severity.
    assert ("inc-1", "info") in captured_advances
    assert ("inc-2", "warning") in captured_advances
    assert len(captured_advances) == 2
    # ...and BEFORE the shakedown flag flip.
    assert captured_state_flips == [(False, None, [("inc-1", "info"), ("inc-2", "warning")])]


@pytest.mark.asyncio
async def test_post_ack_next_observation_does_not_re_dm_baseline_signature():
    """End-to-end: after ack stamps a baseline incident, the next call to
    ``maybe_notify_admin`` for the same signature must NOT DM (because it
    no longer matches rule 2, and there's no severity escalation)."""
    # Step 1: pre-ack incident with NULL last_notified_at.
    pre_ack_incident = _mk_incident(severity="info", last_notified_at=None)
    # Step 2: simulate the ack stamping it with a timestamp.
    post_ack_incident = _mk_incident(
        severity="info",
        last_notified_at="2026-05-13T17:10:00-05:00",
    )

    # Pre-ack: rule 2 fires, DM goes out.
    pre_obs = _mk_observation(severity="info", prev_severity="info")
    send_pre = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_pre),
        patch.object(notify._store, "advance_last_notified_at", MagicMock()),
    ):
        sent_pre = await notify.maybe_notify_admin(pre_obs, pre_ack_incident)
    assert sent_pre is True, "Pre-ack baseline should have DM'd"

    # Post-ack: same observation on the same signature.
    # Rule 2 no longer applies (last_notified_at is set), rule 3 doesn't
    # either (same severity), so the dedup falls through to rule 5 → no DM.
    post_obs = _mk_observation(severity="info", prev_severity="info")
    send_post = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "is_shakedown_active", return_value=False),
        patch.object(notify, "_send_admin_dm", send_post),
        patch.object(notify._store, "advance_last_notified_at", MagicMock()),
    ):
        sent_post = await notify.maybe_notify_admin(post_obs, post_ack_incident)
    assert sent_post is False, (
        "Post-ack baseline observation re-fired rule 2 — ack-flood regression"
    )
    send_post.assert_not_called()


@pytest.mark.asyncio
async def test_send_shakedown_summary_skips_baseline_ack_when_already_inactive():
    """Idempotence: calling on an already-inactive shakedown still DMs an
    empty summary but MUST NOT iterate open incidents — there's nothing to
    baseline-ack and the spurious advance would noise the audit trail."""
    captured_list_calls: list[bool] = []
    captured_advances: list[tuple] = []

    def _record_list(limit=50):
        captured_list_calls.append(True)
        return []

    def _record_advance(*args, **kwargs):
        captured_advances.append((args, kwargs))
        return None

    send_mock = AsyncMock(return_value=True)
    with (
        patch.object(notify._store, "get_shakedown_started_at", return_value=None),
        patch.object(notify._store, "list_shakedown_signatures", return_value=[]),
        patch.object(notify._store, "insert_observation", lambda p: p),
        patch.object(notify._store, "list_open_incidents", _record_list),
        patch.object(notify._store, "advance_last_notified_at", _record_advance),
        patch.object(notify._store, "set_shakedown_active", MagicMock()),
        patch.object(notify, "_send_admin_dm", send_mock),
    ):
        await notify.send_shakedown_summary()

    # No baseline-ack should occur when there was no active window.
    assert captured_list_calls == []
    assert captured_advances == []
