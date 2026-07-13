"""Tests for the migration-034 db.py extensions (Task 3.4)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _stub_client_with_insert(return_program_id: str = "prog_new_42"):
    """Build a Supabase client mock that captures the inserted payload."""
    client = MagicMock()
    table = MagicMock()
    insert = MagicMock()
    insert.execute.return_value.data = [{"program_id": return_program_id}]
    table.insert.return_value = insert
    client.table.return_value = table
    return client, table, insert


def test_create_program_round_trips_engine_v1_fields():
    """knowledge_version + generation_provenance + engine_version land in the
    Supabase INSERT payload."""
    from bot.services import db
    client, table, insert = _stub_client_with_insert("prog_engine_v1")
    with patch("bot.services.db.get_client", return_value=client):
        row = {
            "pitcher_id": "landon_brice",
            "parent_template_id": "velocity_12wk_v1",
            "domain": "throwing",
            "tuned_spec_json": {"weeks": 12},
            "generated_schedule_json": {"days": []},
            "start_date": "2026-06-01",
            "nominal_end_date": "2026-08-24",
            "current_day_index": 0,
            "held_days_count": 0,
            "status": "draft",
            "created_by": "landon_brice",
            "created_by_role": "pitcher",
            "knowledge_version": "abc123def456",
            "generation_provenance": {"fallback_used": False, "attempts": 1},
            "engine_version": "v1",
        }
        pid = db.create_program(row)
    assert pid == "prog_engine_v1"
    # Inspect the captured INSERT payload
    insert_call_args = table.insert.call_args
    payload = insert_call_args[0][0]
    assert payload["knowledge_version"] == "abc123def456"
    assert payload["generation_provenance"] == {"fallback_used": False, "attempts": 1}
    assert payload["engine_version"] == "v1"


def test_create_program_strips_unknown_keys():
    """Unknown fields (`program_id`, random typos) get whitelisted out."""
    from bot.services import db
    client, table, insert = _stub_client_with_insert()
    with patch("bot.services.db.get_client", return_value=client):
        row = {
            "pitcher_id": "p",
            "parent_template_id": "t",
            "domain": "throwing",
            "tuned_spec_json": {},
            "generated_schedule_json": {},
            "start_date": "2026-06-01",
            "nominal_end_date": "2026-08-24",
            "current_day_index": 0,
            "held_days_count": 0,
            "status": "draft",
            "created_by": "p",
            "created_by_role": "pitcher",
            "program_id": "p_should_be_stripped",  # not allowed
            "totally_made_up_field": "x",            # not allowed
        }
        db.create_program(row)
    payload = table.insert.call_args[0][0]
    assert "program_id" not in payload
    assert "totally_made_up_field" not in payload


def test_insert_program_generation_failure_writes_payload():
    """Orchestrator's observability write hits the right table + columns."""
    from bot.services import db
    client = MagicMock()
    table = MagicMock()
    insert = MagicMock()
    insert.execute.return_value.data = []
    table.insert.return_value = insert
    client.table.return_value = table

    with patch("bot.services.db.get_client", return_value=client):
        db.insert_program_generation_failure(
            pitcher_id="landon_brice",
            attempt_n=2,
            status="reject",
            violations=[{"kind": "acwr_hard_cap_exceeded", "where": {"day_index": 30}}],
            reason=None,
        )
    client.table.assert_called_with("program_generation_failures")
    payload = table.insert.call_args[0][0]
    assert payload["pitcher_id"] == "landon_brice"
    assert payload["attempt_number"] == 2
    assert payload["validation_failure_kind"] == "reject"
    assert payload["llm_response"]["violations"][0]["kind"] == "acwr_hard_cap_exceeded"


def test_insert_program_generation_failure_swallows_errors():
    """Observability write must never break authoring — DB exceptions are eaten."""
    from bot.services import db
    client = MagicMock()
    client.table.side_effect = RuntimeError("DB down")
    with patch("bot.services.db.get_client", return_value=client):
        # Should NOT raise
        db.insert_program_generation_failure(
            pitcher_id="p", attempt_n=1, status="valid", violations=None, reason=None,
        )


def test_program_columns_whitelist_includes_engine_v1_fields():
    """Sanity guard so the whitelist edit isn't accidentally reverted."""
    from bot.services.db import _PROGRAM_COLUMNS
    assert "knowledge_version" in _PROGRAM_COLUMNS
    assert "generation_provenance" in _PROGRAM_COLUMNS
    assert "engine_version" in _PROGRAM_COLUMNS
