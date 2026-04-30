"""Tests for Task 13: POST /api/pitcher/{id}/preview-mutations dry-run endpoint.

Verifies:
- Returns a rationale diff without persisting anything (no upsert_daily_entry,
  no upsert_training_model).
- Returns 400 when date or mutations are missing.
- Diff correctly captures changed rationale for swapped exercises.

Note on patch targets:
`_apply_mutations_to_entry` uses in-function imports for db helpers
(`from bot.services.db import ...`), so we patch the source module path
(`bot.services.db.get_exercise`, etc.) rather than `api.routes.<name>`.
"""
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest

import api.routes as routes_module
from api.routes import preview_mutations


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_entry(**overrides):
    """Minimal daily entry for preview-mutations tests."""
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


def _make_request(body: dict) -> MagicMock:
    """Build a mock Request with the given JSON body."""
    req = MagicMock()
    req.json = AsyncMock(return_value=body)
    return req


# Shared mock patches (same targets as test_apply_mutations_rationale.py)
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
_PATCH_GET_PITCHER = patch(
    "bot.services.db.get_pitcher",
    lambda pid: {"role": "starter", "active_flags": {"days_since_outing": 3}},
)


# ---------------------------------------------------------------------------
# Test 1: returns rationale diff for a swap mutation
# ---------------------------------------------------------------------------

def test_preview_returns_rationale_diff():
    """A swap mutation should appear in exercise_rationale_diff and return 200."""
    entry = _make_entry()
    mutations = [
        {"action": "swap", "from_exercise_id": "ex_1", "to_exercise_id": "ex_99", "rx": "3x8"}
    ]
    req = _make_request({"date": "2026-04-30", "mutations": mutations})

    # Disable auth for direct call
    original_disable_auth = routes_module.DISABLE_AUTH
    routes_module.DISABLE_AUTH = True

    try:
        with (
            patch("bot.services.db.get_daily_entry", return_value=entry),
            _PATCH_GET_EXERCISE,
            _PATCH_GET_TRAINING_MODEL,
            _PATCH_UPSERT_TRAINING_MODEL,
            _PATCH_HYDRATE,
            _PATCH_GET_PITCHER,
        ):
            result = asyncio.run(preview_mutations("test_pitcher_001", req))
    finally:
        routes_module.DISABLE_AUTH = original_disable_auth

    assert "mutations" in result
    assert "proposed_rationale" in result

    pr = result["proposed_rationale"]
    assert "exercise_rationale_diff" in pr
    assert "day_summary_before" in pr
    assert "day_summary_after" in pr

    # day_summary_before should be the original value
    assert pr["day_summary_before"] == "original_day_summary"

    # The diff should contain the swapped exercise (ex_99 or ex_1 removed)
    diff = pr["exercise_rationale_diff"]
    assert isinstance(diff, list)
    # ex_99 is the new exercise (swapped in); it should appear since rationale changed
    touched_ids = {item["exercise_id"] for item in diff}
    assert len(touched_ids) >= 1, "Expected at least one exercise in the diff"


# ---------------------------------------------------------------------------
# Test 2: preview does NOT persist any side effects
# ---------------------------------------------------------------------------

def test_preview_does_not_persist():
    """Neither upsert_daily_entry nor upsert_training_model must be called."""
    entry = _make_entry()
    mutations = [
        {"action": "swap", "from_exercise_id": "ex_1", "to_exercise_id": "ex_99", "rx": "3x8"}
    ]
    req = _make_request({"date": "2026-04-30", "mutations": mutations})

    original_disable_auth = routes_module.DISABLE_AUTH
    routes_module.DISABLE_AUTH = True

    try:
        with (
            patch("bot.services.db.get_daily_entry", return_value=entry),
            patch("bot.services.db.upsert_daily_entry") as mock_upsert_entry,
            patch("bot.services.db.upsert_training_model") as mock_upsert_model,
            _PATCH_GET_EXERCISE,
            _PATCH_GET_TRAINING_MODEL,
            _PATCH_HYDRATE,
            _PATCH_GET_PITCHER,
        ):
            asyncio.run(preview_mutations("test_pitcher_001", req))

            mock_upsert_entry.assert_not_called()
            mock_upsert_model.assert_not_called()
    finally:
        routes_module.DISABLE_AUTH = original_disable_auth


# ---------------------------------------------------------------------------
# Test 3: 400 when date or mutations are missing
# ---------------------------------------------------------------------------

def test_preview_400_on_missing_fields():
    """Empty body should raise 400."""
    from fastapi import HTTPException

    original_disable_auth = routes_module.DISABLE_AUTH
    routes_module.DISABLE_AUTH = True

    try:
        # Missing both date and mutations
        req = _make_request({})
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(preview_mutations("test_pitcher_001", req))
        assert exc_info.value.status_code == 400

        # Missing mutations
        req2 = _make_request({"date": "2026-04-30"})
        with pytest.raises(HTTPException) as exc_info2:
            asyncio.run(preview_mutations("test_pitcher_001", req2))
        assert exc_info2.value.status_code == 400

        # Missing date
        req3 = _make_request({"mutations": [{"action": "swap"}]})
        with pytest.raises(HTTPException) as exc_info3:
            asyncio.run(preview_mutations("test_pitcher_001", req3))
        assert exc_info3.value.status_code == 400
    finally:
        routes_module.DISABLE_AUTH = original_disable_auth
