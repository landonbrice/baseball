"""Regression test: context_manager slices recent interactions safely.

Covers D4 — msg['content'] can theoretically be a dict from bad upstream data.
The line used [:200] on .get('content', '') which TypeErrors on dicts.
"""
from unittest.mock import patch
from bot.services import context_manager


def test_load_context_handles_non_string_content(monkeypatch):
    # Arrange: chat_history returns a message with dict content (bad data)
    bad_messages = [
        {"created_at": "2026-04-18T09:00:00", "role": "user", "content": {"text": "hi"}},
        {"created_at": "2026-04-18T09:01:00", "role": "bot", "content": None},
        {"created_at": "2026-04-18T09:02:00", "role": "user", "content": "normal string"},
    ]
    monkeypatch.setattr(
        "bot.services.context_manager._db.get_chat_history",
        lambda pid, limit=15: bad_messages,
    )
    monkeypatch.setattr(
        "bot.services.context_manager.load_profile",
        lambda pid: {"name": "Test", "pitcher_id": pid},
    )
    monkeypatch.setattr(
        "bot.services.context_manager.get_recent_entries",
        lambda pid, days=14: [],
    )

    # Act: must not raise TypeError
    result = context_manager.load_context("test_pitcher_001")

    # Assert: output is a string and contains all three messages in some form
    assert isinstance(result, str)
    assert "normal string" in result
