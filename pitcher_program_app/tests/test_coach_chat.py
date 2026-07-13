# tests/test_coach_chat.py
"""Tests for research-aware coach chat structured output."""

import json
import sys
import types
import pytest


def _stub_telegram():
    """Make sure qa.py can be imported, with or without telegram installed.

    Prefers the real `python-telegram-bot` package when it's available —
    qa.py's module-level `context: ContextTypes.DEFAULT_TYPE` annotation
    needs a real `ContextTypes` (with a `DEFAULT_TYPE` attribute), which a
    bare `object` placeholder can't provide. Only when running in isolation
    did an earlier version of this stub install `ContextTypes = object`
    unconditionally, which happened to work when some other test module
    imported the real `telegram` package first (populating sys.modules
    before this file's guard short-circuited) but raised
    `AttributeError: type object 'object' has no attribute 'DEFAULT_TYPE'`
    when this file ran alone. Falling back to a minimal fake only when the
    real package genuinely isn't installed keeps this file self-sufficient
    in both orderings without touching production code.
    """
    try:
        import telegram  # noqa: F401
        import telegram.ext  # noqa: F401
        return
    except ImportError:
        pass
    if "telegram" in sys.modules and "telegram.ext" in sys.modules:
        return
    telegram = types.ModuleType("telegram")
    telegram.Update = object
    sys.modules["telegram"] = telegram
    ext = types.ModuleType("telegram.ext")
    ext.ContextTypes = object
    sys.modules["telegram.ext"] = ext


_stub_telegram()


def test_parse_coach_response_valid():
    from bot.handlers.qa import _parse_coach_response
    raw = json.dumps({
        "reply": "Hey, I hear you on the elbow.",
        "mutation_card": {
            "type": "rest",
            "title": "Rest today",
            "rationale": "Per the FPM protocol.",
            "actions": [],
            "applies_to_date": "today",
        },
        "lookahead": "Start in 3 days.",
    })
    result = _parse_coach_response(raw)
    assert result is not None
    assert result["reply"] == "Hey, I hear you on the elbow."
    assert result["mutation_card"]["type"] == "rest"
    assert result["lookahead"] == "Start in 3 days."


def test_parse_coach_response_malformed():
    from bot.handlers.qa import _parse_coach_response
    result = _parse_coach_response("This is just plain text, no JSON.")
    assert result is None


def test_parse_coach_response_partial_json():
    from bot.handlers.qa import _parse_coach_response
    raw = '{"reply": "Hey", "mutation_card": {"type": "rest"'
    result = _parse_coach_response(raw)
    assert result is None


def test_extract_reply_from_malformed():
    from bot.handlers.qa import _extract_reply_fallback
    raw = '{"reply": "Some text here", "mutation_card": broken'
    result = _extract_reply_fallback(raw)
    assert "Some text here" in result


def test_parse_coach_response_with_markdown_fences():
    from bot.handlers.qa import _parse_coach_response
    raw = '```json\n{"reply": "Hey there", "lookahead": "Tomorrow looks good."}\n```'
    result = _parse_coach_response(raw)
    assert result is not None
    assert result["reply"] == "Hey there"
