"""Tests for program_lifecycle (Layer 4).

State machine: draft → active (with confirm-then-archive of any existing active in same domain),
              draft → archived,
              active → archived.
"""
from unittest.mock import patch, call


def test_activate_draft_with_no_existing_active():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "pitcher_id": "landon_brice",
            "domain": "throwing", "status": "draft"}), \
         patch.object(program_lifecycle, "_get_active_program_in_domain", return_value=None), \
         patch.object(program_lifecycle, "_update_status") as upd:
        result = program_lifecycle.activate("p1")
    assert result["activated"] == "p1"
    assert result["archived"] is None
    upd.assert_called_once_with("p1", "active", activated_at=upd.call_args.kwargs["activated_at"])


def test_activate_archives_existing_active_in_same_domain():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p2", "pitcher_id": "landon_brice",
            "domain": "throwing", "status": "draft"}), \
         patch.object(program_lifecycle, "_get_active_program_in_domain", return_value={
            "program_id": "p1_old", "pitcher_id": "landon_brice",
            "domain": "throwing", "status": "active"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        result = program_lifecycle.activate("p2", archive_reason="superseded")
    assert result["activated"] == "p2"
    assert result["archived"] == "p1_old"
    # Two update calls in order: archive old, then activate new
    assert len(upd.call_args_list) == 2
    assert upd.call_args_list[0][0][0] == "p1_old"
    assert upd.call_args_list[0][0][1] == "archived"
    assert upd.call_args_list[1][0][0] == "p2"
    assert upd.call_args_list[1][0][1] == "active"


def test_activate_does_nothing_if_already_active():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "active", "domain": "throwing"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        result = program_lifecycle.activate("p1")
    assert result["activated"] == "p1"
    assert result["already_active"] is True
    upd.assert_not_called()


def test_activate_rejects_archived_program():
    from bot.services import program_lifecycle
    import pytest
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "archived"}):
        with pytest.raises(ValueError, match="archived"):
            program_lifecycle.activate("p1")


def test_archive_sets_reason_and_archived_at():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "active"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        program_lifecycle.archive("p1", reason="completed")
    upd.assert_called_once()
    args, kwargs = upd.call_args
    assert args == ("p1", "archived")
    assert kwargs["archive_reason"] == "completed"
    assert "archived_at" in kwargs


def test_archive_idempotent_on_already_archived():
    from bot.services import program_lifecycle
    with patch.object(program_lifecycle, "_get_program", return_value={
            "program_id": "p1", "status": "archived"}), \
         patch.object(program_lifecycle, "_update_status") as upd:
        program_lifecycle.archive("p1", reason="x")
    upd.assert_not_called()


def test_get_program_or_raise_not_found():
    from bot.services import program_lifecycle
    import pytest
    with patch.object(program_lifecycle, "_get_program", return_value=None):
        with pytest.raises(LookupError):
            program_lifecycle.activate("nonexistent")
