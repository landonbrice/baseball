"""D3: morning_brief is always stored as a JSON-string with a stable envelope."""
import json
import pytest
from bot.services.checkin_service import normalize_brief


def test_normalize_none_returns_empty_json_object():
    assert normalize_brief(None) == json.dumps({})


def test_normalize_empty_string_returns_empty_json_object():
    assert normalize_brief("") == json.dumps({})


def test_normalize_plain_string_wraps_in_coaching_note():
    out = normalize_brief("Focus on recovery.")
    assert json.loads(out) == {"coaching_note": "Focus on recovery."}


def test_normalize_dict_serializes_verbatim():
    data = {"coaching_note": "rest", "arm_verdict": {"status": "green"}}
    out = normalize_brief(data)
    assert json.loads(out) == data


def test_normalize_already_json_string_passes_through():
    raw = json.dumps({"coaching_note": "already json"})
    out = normalize_brief(raw)
    assert json.loads(out) == {"coaching_note": "already json"}


def test_normalize_malformed_json_string_treated_as_plain_string():
    out = normalize_brief("{not valid json")
    assert json.loads(out) == {"coaching_note": "{not valid json"}
