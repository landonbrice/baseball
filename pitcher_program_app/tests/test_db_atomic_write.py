"""Tests for db.write_daily_entry_with_counter_advance.

The helper does two things:
1. Upserts the daily_entries row (whitelisted columns only).
2. Calls the advance_program_counter Postgres function via RPC, passing
   the counter-advance OR hold-event payload.

Not cross-step atomic (Supabase REST limitation): step 1 may succeed
while step 2 fails. program_id=None skips the RPC entirely (cold-start
parity for pitchers without an active program).
"""

from datetime import date
from unittest.mock import MagicMock, patch

from bot.services import db


def _build_mock_client():
    client = MagicMock()
    # Chain: client.table("daily_entries").upsert(row, on_conflict=...).execute()
    client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])
    # Chain: client.rpc("advance_program_counter", params).execute()
    client.rpc.return_value.execute.return_value = MagicMock(data=None)
    return client


def test_write_advances_counter_when_no_hold_event():
    client = _build_mock_client()
    entry = {
        "pitcher_id": "landon_brice",
        "date": "2026-05-01",
        "pre_training": {"arm_feel": 8},
        "lifting": {"exercises": []},
        "ignored_field": "should be stripped",
    }
    with patch.object(db, "get_client", return_value=client):
        db.write_daily_entry_with_counter_advance(
            entry,
            program_id="prog-uuid-1",
            hold_event=None,
            event_date=date(2026, 5, 1),
        )

    # Upsert was called on daily_entries with whitelisted fields only.
    client.table.assert_called_with("daily_entries")
    upsert_call = client.table.return_value.upsert.call_args
    upserted_row = upsert_call.args[0]
    assert "ignored_field" not in upserted_row
    assert upserted_row["pitcher_id"] == "landon_brice"
    assert upsert_call.kwargs == {"on_conflict": "pitcher_id,date"}

    # RPC called with hold_event=None (advance path).
    client.rpc.assert_called_once_with(
        "advance_program_counter",
        {
            "p_program_id": "prog-uuid-1",
            "p_hold_event": None,
            "p_event_date": "2026-05-01",
        },
    )


def test_write_inserts_hold_event_when_hold_payload_provided():
    client = _build_mock_client()
    entry = {"pitcher_id": "landon_brice", "date": "2026-05-02"}
    hold = {
        "triage_result": {"flag": "yellow"},
        "reason_code": "arm_feel_low",
    }
    with patch.object(db, "get_client", return_value=client):
        db.write_daily_entry_with_counter_advance(
            entry,
            program_id="prog-uuid-2",
            hold_event=hold,
            event_date=date(2026, 5, 2),
        )

    client.rpc.assert_called_once_with(
        "advance_program_counter",
        {
            "p_program_id": "prog-uuid-2",
            "p_hold_event": hold,
            "p_event_date": "2026-05-02",
        },
    )


def test_write_skips_rpc_when_program_id_is_none():
    client = _build_mock_client()
    entry = {"pitcher_id": "landon_brice", "date": "2026-05-03"}
    with patch.object(db, "get_client", return_value=client):
        db.write_daily_entry_with_counter_advance(
            entry,
            program_id=None,
            hold_event=None,
            event_date=date(2026, 5, 3),
        )

    # Daily entry still upserted.
    client.table.assert_called_with("daily_entries")
    client.table.return_value.upsert.return_value.execute.assert_called_once()
    # But no RPC call for cold-start pitchers.
    client.rpc.assert_not_called()
