"""Regression tests for has_briefing computation (Issue 1 from Task 3b review).

Guards against the semantic regression where canonical empty briefs ('{}'  or None)
were incorrectly evaluated as truthy after normalize_brief was introduced.

The logic under test is extracted here as a pure helper that mirrors exactly what
api/routes.py produces for the `has_briefing` field.
"""
import json
import pytest


def _compute_has_briefing(entry_dict: dict | None) -> bool:
    """Mirror the logic in api/routes.py for the `has_briefing` response field.

    Keep this in sync with:
        api/routes.py  →  "has_briefing": bool(
            today_entry
            and today_entry.get("morning_brief")
            and today_entry.get("morning_brief") != "{}"
        )
    """
    if not entry_dict:
        return False
    raw = entry_dict.get("morning_brief")
    return bool(raw and raw != "{}")


# ---------------------------------------------------------------------------
# Canonical cases
# ---------------------------------------------------------------------------

class TestHasBriefingCanonicalEmpty:
    def test_none_entry_returns_false(self):
        """No today_entry at all — pre-check-in state."""
        assert _compute_has_briefing(None) is False

    def test_missing_morning_brief_key_returns_false(self):
        """Entry exists but morning_brief key was never written."""
        assert _compute_has_briefing({}) is False

    def test_none_morning_brief_returns_false(self):
        """Partial check-in row — morning_brief explicitly None."""
        assert _compute_has_briefing({"morning_brief": None}) is False

    def test_empty_string_returns_false(self):
        """Degenerate empty string — should not count as a brief."""
        assert _compute_has_briefing({"morning_brief": ""}) is False

    def test_canonical_empty_json_string_returns_false(self):
        """Core regression guard: normalize_brief(None/empty) → '{}' must be falsy."""
        assert _compute_has_briefing({"morning_brief": "{}"}) is False


class TestHasBriefingRealContent:
    def test_coaching_note_only_returns_true(self):
        brief = json.dumps({"coaching_note": "focus on recovery"})
        assert _compute_has_briefing({"morning_brief": brief}) is True

    def test_arm_verdict_only_returns_true(self):
        brief = json.dumps({"arm_verdict": "green", "coaching_note": ""})
        assert _compute_has_briefing({"morning_brief": brief}) is True

    def test_full_brief_returns_true(self):
        brief = json.dumps({
            "coaching_note": "Light day today — good sleep numbers.",
            "arm_verdict": "green",
            "energy_note": "Recovery solid at 82%",
        })
        assert _compute_has_briefing({"morning_brief": brief}) is True

    def test_plain_string_brief_wrapped_by_normalize_returns_true(self):
        """normalize_brief wraps plain strings as {coaching_note: ...}, not '{}'."""
        brief = json.dumps({"coaching_note": "pre-normalize legacy string"})
        assert _compute_has_briefing({"morning_brief": brief}) is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestHasBriefingEdgeCases:
    def test_other_entry_fields_do_not_affect_result(self):
        """Extra fields on the entry dict have no influence."""
        assert _compute_has_briefing({
            "pre_training": {"arm_feel": 7},
            "morning_brief": "{}",
        }) is False

        assert _compute_has_briefing({
            "pre_training": {"arm_feel": 7},
            "morning_brief": json.dumps({"coaching_note": "all good"}),
        }) is True
