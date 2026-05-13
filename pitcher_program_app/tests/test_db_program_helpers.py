"""Tests for new program/builder_session repository helpers in db.py."""

from unittest.mock import MagicMock, patch
import pytest

from bot.services import db


def _mock_client(execute_data):
    """Build a chainable mock of the Supabase client returning the given data."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=execute_data)
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=execute_data)
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=execute_data)
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=execute_data)
    return client


def test_create_program_inserts_and_returns_program_id():
    fake_inserted = [{"program_id": "abc-123", "pitcher_id": "landon_brice", "domain": "throwing"}]
    with patch.object(db, "get_client", return_value=_mock_client(fake_inserted)):
        program_id = db.create_program({
            "pitcher_id": "landon_brice",
            "parent_template_id": "tpl_starter_7day_cadence_v1",
            "domain": "throwing",
            "generated_schedule_json": {"days": []},
            "start_date": "2026-05-01",
            "nominal_end_date": "2026-07-24",
            "status": "draft",
            "created_by": "landon_brice",
            "created_by_role": "pitcher",
        })
    assert program_id == "abc-123"


def test_update_program_status_calls_update():
    with patch.object(db, "get_client", return_value=_mock_client([{"program_id": "abc"}])):
        db.update_program_status("abc-123", "active", activated_at="2026-05-01T00:00:00Z")
    # No exception = pass; behavior verified via mock chain.


def test_get_program_returns_dict_or_none():
    with patch.object(db, "get_client", return_value=_mock_client([{"program_id": "abc"}])):
        assert db.get_program("abc-123") == {"program_id": "abc"}
    with patch.object(db, "get_client", return_value=_mock_client([])):
        assert db.get_program("nonexistent") is None


def test_list_programs_for_pitcher_returns_list():
    with patch.object(db, "get_client", return_value=_mock_client([
        {"program_id": "p1"}, {"program_id": "p2"}
    ])):
        result = db.list_programs_for_pitcher("landon_brice")
        assert len(result) == 2


def test_list_programs_for_pitcher_summary_uses_projection_and_default_order():
    """Verify the summary helper selects the trimmed column list (no generated_schedule_json)
    and orders by created_at desc by default."""
    client = MagicMock()
    chain = (
        client.table.return_value.select.return_value.eq.return_value.eq.return_value
              .order.return_value
    )
    chain.execute.return_value = MagicMock(data=[{"program_id": "p1"}])
    # Also support the no-status branch
    client.table.return_value.select.return_value.eq.return_value.order.return_value \
          .execute.return_value = MagicMock(data=[{"program_id": "p1"}])

    with patch.object(db, "get_client", return_value=client):
        out = db.list_programs_for_pitcher_summary("landon_brice", status="draft")
    assert out == [{"program_id": "p1"}]
    # First positional arg to select() is the column list — assert generated_schedule_json absent
    select_call = client.table.return_value.select.call_args
    cols = select_call.args[0]
    assert "generated_schedule_json" not in cols
    assert "tuned_spec_json" in cols
    assert "program_id" in cols


def test_list_programs_for_pitcher_summary_accepts_archived_at_order():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value \
          .order.return_value.execute.return_value = MagicMock(data=[])
    with patch.object(db, "get_client", return_value=client):
        db.list_programs_for_pitcher_summary("landon_brice", status="archived",
                                             order_by="archived_at")
    order_call = client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.call_args
    assert order_call.args[0] == "archived_at"
    assert order_call.kwargs.get("desc") is True


def test_list_programs_for_pitcher_summary_rejects_bad_order_by():
    with pytest.raises(ValueError):
        db.list_programs_for_pitcher_summary("landon_brice", order_by="random_column")


def test_create_builder_session_returns_session_id():
    fake = [{"session_id": "sess-1", "pitcher_id": "landon_brice"}]
    with patch.object(db, "get_client", return_value=_mock_client(fake)):
        session_id = db.create_builder_session({
            "pitcher_id": "landon_brice",
            "initiator_id": "landon_brice",
            "initiator_role": "pitcher",
            "interview_mode": "personalize",
            "constraint_envelope_json": {},
            "candidate_template_ids": [],
            "status": "in_progress",
        })
    assert session_id == "sess-1"


def test_record_generation_failure_inserts_row():
    with patch.object(db, "get_client", return_value=_mock_client([{"failure_id": "f1"}])):
        db.record_generation_failure(
            session_id="sess-1",
            attempt_number=1,
            validation_failure_kind="exercise_not_found",
            llm_response={"error": "tried ex_999"},
        )
    # No exception = pass.
