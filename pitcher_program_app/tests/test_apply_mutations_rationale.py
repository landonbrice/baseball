"""Tests for Task 12: apply_mutations regenerates touched-exercise + day rationale.

Verifies:
- Swap regenerates rationale for the touched exercise only (untouched kept).
- Any mutation regenerates day_summary_rationale.
- Triage rationale (entry["rationale"]) is pinned (unchanged) after mutation.
"""
import copy
import pytest
from unittest.mock import patch

from api.routes import _apply_mutations_to_entry

# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_entry(**overrides):
    """Minimal daily entry that passes through _apply_mutations_to_entry."""
    base = {
        "pitcher_id": "test_pitcher_001",
        "date": "2026-04-30",
        "pre_training": {
            "arm_feel": 7,
            "overall_energy": 7,
            "flag_level": "green",
            "category_scores": {"tissue": 8.0, "load": 8.0, "recovery": 8.0},
        },
        "lifting": {
            "exercises": [
                {
                    "exercise_id": "ex_1",
                    "id": "ex_1",
                    "name": "Squat",
                    "prescribed": "3x5",
                    "rx": "3x5",
                    "rationale": "original_rationale_ex1",
                },
                {
                    "exercise_id": "ex_2",
                    "id": "ex_2",
                    "name": "Deadlift",
                    "prescribed": "3x5",
                    "rx": "3x5",
                    "rationale": "original_rationale_ex2",
                },
            ]
        },
        "plan_generated": {
            "day_focus": "lift",
            "modifications_applied": [],
            "day_summary_rationale": "original_day_summary",
        },
        "rationale": {
            "short": "All systems good.",
            "detail": {
                "status_line": "Green",
                "signal_line": "Arm feel holding at 7.",
                "response_line": "Full program today.",
            },
        },
    }
    base.update(overrides)
    return base


# Shared mock targets to avoid Supabase calls
_PATCH_GET_EXERCISE = patch(
    "bot.services.db.get_exercise",
    side_effect=lambda eid: {"id": eid, "exercise_id": eid, "name": f"Exercise {eid}"},
)
_PATCH_GET_TRAINING_MODEL = patch(
    "bot.services.db.get_training_model",
    return_value={},
)
_PATCH_UPSERT_TRAINING_MODEL = patch(
    "bot.services.db.upsert_training_model",
    return_value=None,
)
_PATCH_HYDRATE = patch(
    "bot.services.exercise_pool.hydrate_exercises",
    return_value=None,
)


# ---------------------------------------------------------------------------
# Test 1: swap regenerates the touched exercise's rationale only
# ---------------------------------------------------------------------------

def test_swap_regenerates_touched_exercise_only():
    entry = _make_entry()
    mutations = [
        {"action": "swap", "from_exercise_id": "ex_1", "to_exercise_id": "ex_99", "rx": "3x8"}
    ]

    with _PATCH_GET_EXERCISE, _PATCH_GET_TRAINING_MODEL, _PATCH_UPSERT_TRAINING_MODEL, _PATCH_HYDRATE:
        result = _apply_mutations_to_entry(entry, mutations, source="test")

    exercises = result["lifting"]["exercises"]
    # There should be 2 exercises (1 swapped, 1 untouched)
    assert len(exercises) == 2

    # Find by exercise_id (after swap, ex_1 position has ex_99 id)
    touched = next((e for e in exercises if e.get("exercise_id") == "ex_99"), None)
    untouched = next((e for e in exercises if e.get("exercise_id") == "ex_2"), None)

    assert touched is not None, "Swapped-in exercise ex_99 not found"
    assert untouched is not None, "Untouched exercise ex_2 not found"

    # Touched exercise must have had rationale REGENERATED — the original value
    # was "original_rationale_ex1" (from ex_1 which was mutated in-place).
    # After regeneration, the key should exist and the value should NOT be the
    # original stale rationale any more (None is acceptable per spec A29).
    assert "rationale" in touched, "Touched exercise is missing rationale key after swap"
    assert touched.get("rationale") != "original_rationale_ex1", (
        "Touched exercise rationale was NOT regenerated — still shows stale ex_1 rationale"
    )

    # Untouched exercise must retain its original rationale
    assert untouched.get("rationale") == "original_rationale_ex2", (
        f"Untouched exercise rationale was altered: {untouched.get('rationale')!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: any mutation regenerates day_summary_rationale
# ---------------------------------------------------------------------------

def test_mutation_regenerates_day_summary():
    entry = _make_entry()
    mutations = [
        {"action": "swap", "from_exercise_id": "ex_1", "to_exercise_id": "ex_99", "rx": "3x8"}
    ]

    with _PATCH_GET_EXERCISE, _PATCH_GET_TRAINING_MODEL, _PATCH_UPSERT_TRAINING_MODEL, _PATCH_HYDRATE:
        result = _apply_mutations_to_entry(entry, mutations, source="test")

    plan = result.get("plan_generated") or {}
    assert "day_summary_rationale" in plan, "day_summary_rationale key missing after mutation"
    # The value must be regenerated — not the original fixture value
    assert plan.get("day_summary_rationale") != "original_day_summary", (
        "day_summary_rationale was NOT regenerated — still shows original fixture value"
    )


# ---------------------------------------------------------------------------
# Test 3: triage rationale is pinned (unchanged) after mutation
# ---------------------------------------------------------------------------

def test_mutation_pins_triage_rationale():
    entry = _make_entry()
    original_rationale = copy.deepcopy(entry["rationale"])

    mutations = [
        {"action": "swap", "from_exercise_id": "ex_1", "to_exercise_id": "ex_99", "rx": "3x8"}
    ]

    with _PATCH_GET_EXERCISE, _PATCH_GET_TRAINING_MODEL, _PATCH_UPSERT_TRAINING_MODEL, _PATCH_HYDRATE:
        result = _apply_mutations_to_entry(entry, mutations, source="test")

    # entry["rationale"] must be unchanged
    assert result.get("rationale") == original_rationale, (
        f"Triage rationale was mutated. Expected: {original_rationale!r}, "
        f"got: {result.get('rationale')!r}"
    )
