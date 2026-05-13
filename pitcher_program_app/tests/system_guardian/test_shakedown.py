"""Tests for the A6 shakedown window in ``store.py`` (PR-5).

Covers:

* Auto-arm on first-ever observation insert (sentinel absent).
* Auto-expire after 24h via :func:`store.check_and_expire_shakedown`.
* Manual ``set_shakedown_active(False)`` flips immediately.
* :func:`list_shakedown_signatures` returns distinct signatures seen during
  the active window, sorted by severity desc.

Uses :class:`tests.system_guardian._fake_supabase.FakeSupabase` so the
sentinel-row roundtrip exercises real reads + writes without a database.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from bot.config import CHICAGO_TZ
from bot.services.system_guardian import store
from tests.system_guardian._fake_supabase import FakeSupabase


# ---------------------------------------------------------------------------
# Auto-arm
# ---------------------------------------------------------------------------


def test_auto_arm_on_first_ever_observation_writes_sentinel():
    """The very first regular observation insert must auto-arm a 24h
    shakedown by writing the sentinel row."""
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.insert_observation(
            {
                "event_type": "plan_health_summary",
                "message": "hello",
                "severity_hint": "info",
                "metadata": {"category": "existing_health"},
            }
        )

    rows = fake.tables.get("system_observations") or []
    assert rows, "expected at least one row written"

    sentinels = [
        r for r in rows
        if r.get("signature") == store.SHAKEDOWN_SENTINEL_SIGNATURE
    ]
    assert len(sentinels) == 1, f"expected exactly one sentinel row, got {len(sentinels)}"
    details = sentinels[0]["metadata"]["details"]
    assert details["active"] is True
    assert details["started_at"]  # ISO timestamp


def test_auto_arm_does_not_re_fire_when_sentinel_already_exists():
    """A second observation must NOT write a second sentinel — the
    deterministic check is "sentinel row exists at all" not "is_active"."""
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        # First observation arms.
        store.insert_observation(
            {"event_type": "plan_health_summary", "message": "a"}
        )
        sentinels_after_first = [
            r for r in fake.tables["system_observations"]
            if r.get("signature") == store.SHAKEDOWN_SENTINEL_SIGNATURE
        ]
        assert len(sentinels_after_first) == 1

        # Second observation must not double-arm.
        store.insert_observation(
            {"event_type": "plan_health_summary", "message": "b"}
        )
        sentinels_after_second = [
            r for r in fake.tables["system_observations"]
            if r.get("signature") == store.SHAKEDOWN_SENTINEL_SIGNATURE
        ]
        assert len(sentinels_after_second) == 1


def test_sentinel_inserts_do_not_recursively_re_arm():
    """Inserting the sentinel itself MUST NOT trigger the auto-arm branch —
    that would be infinite recursion."""
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        # Call set_shakedown_active directly (this is what insert_observation
        # would do internally on auto-arm). It should write ONE row, not loop.
        store.set_shakedown_active(True)
        rows = fake.tables["system_observations"]
        # Exactly one sentinel row.
        sentinels = [
            r for r in rows
            if r.get("signature") == store.SHAKEDOWN_SENTINEL_SIGNATURE
        ]
        assert len(sentinels) == 1


# ---------------------------------------------------------------------------
# Active/expired
# ---------------------------------------------------------------------------


def test_is_shakedown_active_true_within_window():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True)
        assert store.is_shakedown_active() is True


def test_is_shakedown_active_false_after_24h():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        # Write a sentinel rooted 25h in the past.
        old = datetime.now(CHICAGO_TZ) - timedelta(hours=25)
        store.set_shakedown_active(True, started_at=old)
        assert store.is_shakedown_active() is False


def test_is_shakedown_active_false_when_explicitly_set_inactive():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True)
        assert store.is_shakedown_active() is True
        # Now flip it off.
        store.set_shakedown_active(False)
        assert store.is_shakedown_active() is False


def test_get_shakedown_started_at_returns_none_when_inactive():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(False)
        assert store.get_shakedown_started_at() is None


def test_get_shakedown_started_at_returns_parsed_timestamp():
    fake = FakeSupabase()
    started = datetime.now(CHICAGO_TZ) - timedelta(hours=1)
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True, started_at=started)
        got = store.get_shakedown_started_at()
        assert got is not None
        # ISO round-trip via datetime.fromisoformat keeps tz info.
        assert abs((got - started).total_seconds()) < 1


# ---------------------------------------------------------------------------
# check_and_expire_shakedown
# ---------------------------------------------------------------------------


def test_check_and_expire_returns_false_when_already_inactive():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        # No sentinel at all → already inactive.
        assert store.check_and_expire_shakedown() is False


def test_check_and_expire_returns_false_when_still_within_window():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True)
        assert store.check_and_expire_shakedown() is False
        # Still active.
        assert store.is_shakedown_active() is True


def test_check_and_expire_returns_true_and_flips_state_after_24h():
    fake = FakeSupabase()
    old = datetime.now(CHICAGO_TZ) - timedelta(hours=25)
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True, started_at=old)
        transitioned = store.check_and_expire_shakedown()
        assert transitioned is True
        # Now inactive.
        assert store.is_shakedown_active() is False


# ---------------------------------------------------------------------------
# list_shakedown_signatures
# ---------------------------------------------------------------------------


def test_list_shakedown_signatures_returns_empty_when_inactive():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        # No sentinel → not active.
        assert store.list_shakedown_signatures() == []


def test_list_shakedown_signatures_returns_distinct_sorted_by_severity():
    fake = FakeSupabase()
    started = datetime.now(CHICAGO_TZ) - timedelta(hours=1)
    started_iso = started.isoformat()
    # Seed incidents.
    fake.tables["system_incidents"] = [
        {
            "signature": "sig_warn",
            "title": "warn",
            "severity": "warning",
            "count": 1,
            "last_seen": (started + timedelta(minutes=30)).isoformat(),
            "category": "runtime_error",
        },
        {
            "signature": "sig_crit_low_count",
            "title": "crit-low",
            "severity": "critical",
            "count": 1,
            "last_seen": (started + timedelta(minutes=30)).isoformat(),
            "category": "runtime_error",
        },
        {
            "signature": "sig_crit_high_count",
            "title": "crit-high",
            "severity": "critical",
            "count": 5,
            "last_seen": (started + timedelta(minutes=30)).isoformat(),
            "category": "runtime_error",
        },
        {
            "signature": "sig_too_old",
            "title": "too old",
            "severity": "critical",
            "count": 9,
            # before the shakedown window started — filtered out.
            "last_seen": (started - timedelta(hours=5)).isoformat(),
            "category": "runtime_error",
        },
    ]
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True, started_at=started)
        out = store.list_shakedown_signatures()
        signatures = [r["signature"] for r in out]
        # crit_high_count first (critical + count=5), then crit_low_count, then warn.
        # too_old excluded by the gte filter on last_seen.
        assert signatures[0] == "sig_crit_high_count"
        assert "sig_too_old" not in signatures
        assert signatures[1] == "sig_crit_low_count"
        assert signatures[2] == "sig_warn"


# ---------------------------------------------------------------------------
# Sentinel survives the standard normalize_observation roundtrip
# ---------------------------------------------------------------------------


def test_set_shakedown_writes_sentinel_with_correct_signature():
    fake = FakeSupabase()
    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        store.set_shakedown_active(True)
        rows = fake.tables["system_observations"]
        assert rows
        last = rows[-1]
        assert last["signature"] == "guardian_shakedown_state"
        # Should have written the sentinel even though the auto-arm logic
        # also fires — but auto-arm is gated on sentinel existence so we end
        # up with exactly one row.


# ---------------------------------------------------------------------------
# 2026-05-13 Bug A: ack-flood fix exercised end-to-end via the auto-expire
# scheduler hook. ``check_shakedown_expiry`` returns True past the 24h
# threshold and the caller invokes ``send_shakedown_summary``. THAT function
# is the ack-flood entrypoint; we cover the manual ack path in test_notify.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_expire_path_invokes_send_shakedown_summary_with_baseline_ack():
    """The hourly ``check_shakedown_expiry`` hook in ``__init__.py`` flips
    state then dispatches the summary DM — same code path as the manual ack
    so it gets the baseline-ack fix automatically. Smoke-test that the wiring
    is intact."""
    import asyncio as _asyncio
    from unittest.mock import AsyncMock as _AsyncMock

    from bot.services import system_guardian as _sg

    # Pretend the 24h transition just fired.
    with (
        patch.object(_sg.store, "check_and_expire_shakedown", return_value=True),
        patch(
            "bot.services.system_guardian.notify.send_shakedown_summary",
            new_callable=_AsyncMock,
        ) as mock_summary,
    ):
        transitioned = await _sg.check_shakedown_expiry()

    assert transitioned is True
    mock_summary.assert_awaited_once()


def test_baseline_ack_helper_advances_every_open_incident():
    """Direct test of the baseline-ack helper: every open incident gets
    ``last_notified_at`` stamped with its CURRENT severity (so a future
    same-band observation is rule-5'd, not rule-2'd)."""
    from bot.services.system_guardian import notify as _notify

    fake = FakeSupabase()
    fake.tables["system_incidents"] = [
        {
            "id": "inc-1",
            "severity": "info",
            "last_notified_at": None,
            "status": "open",
            "title": "research_load_anomaly: 0 calls",
            "signature": "sig_a",
            "category": "runtime_error",
            "count": 1,
            "last_seen": "2026-05-13T17:00:00-05:00",
        },
        {
            "id": "inc-2",
            "severity": "warning",
            "last_notified_at": None,
            "status": "ack",  # ack still counts as open per spec §8
            "title": "daily_entries_stale: 4 partials",
            "signature": "sig_b",
            "category": "silent_degradation",
            "count": 4,
            "last_seen": "2026-05-13T17:00:00-05:00",
        },
        {
            "id": "inc-3",
            "severity": "critical",
            "last_notified_at": None,
            "status": "resolved",  # NOT open — should be skipped
            "title": "resolved already",
            "signature": "sig_c",
            "category": "runtime_error",
            "count": 9,
            "last_seen": "2026-05-13T17:00:00-05:00",
        },
    ]

    with patch(
        "bot.services.system_guardian.store._db.get_client", return_value=fake
    ):
        stamped = _notify._acknowledge_shakedown_baseline()

    # Two open + ack incidents stamped; the resolved one skipped.
    assert stamped == 2
    # The fake stores updates by patching the in-memory rows.
    updated = {
        r["id"]: r
        for r in fake.tables["system_incidents"]
    }
    assert updated["inc-1"]["last_notified_at"] is not None
    assert updated["inc-1"]["severity"] == "info"  # preserved
    assert updated["inc-2"]["last_notified_at"] is not None
    assert updated["inc-2"]["severity"] == "warning"  # preserved
    # Resolved incident untouched.
    assert updated["inc-3"]["last_notified_at"] is None
