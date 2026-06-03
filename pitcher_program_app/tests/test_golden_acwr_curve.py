"""Tests for the golden ACWR curve fixture (Program Engine Task 0.3).

Pinning this fixture is the regression test that Phase 2's load math + ACWR
governor honor the human coach's mental model. Even with the daily grid
unavailable (Drive-aliased), the weekly curve + the 3-up-1-down deload
undulation are enough to lock the shape.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "golden_acwr_curve.json"


@pytest.fixture(scope="module")
def curve() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_fixture_exists(curve):
    assert curve, "golden_acwr_curve.json must exist and parse as JSON"


def test_weekly_curve_has_twelve_weeks(curve):
    assert len(curve["weekly_G_load_units"]) == 12


def test_weekly_curve_values_positive(curve):
    for w_idx, g in enumerate(curve["weekly_G_load_units"]):
        assert isinstance(g, (int, float)), f"week {w_idx + 1}: G must be numeric"
        assert g > 0, f"week {w_idx + 1}: G must be > 0"


def test_recon_weekly_curve_matches_dossier_transcript(curve):
    """The first 9 weeks were transcribed verbatim from the recon dossier.

    If this test fails after re-extraction from the xlsx, that's expected — but
    the recon-vs-extracted gap must then be documented in the fixture's _meta.
    """
    expected_first_9 = [6960, 9194, 10935, 10375, 12049, 13516, 12090, 12960, 13620]
    assert curve["weekly_G_load_units"][:9] == expected_first_9


def test_deload_weeks_present(curve):
    """The empty %increase / ACWLR columns ARE the human ACWR governor model.

    The curve has 3-up-1-down undulation: Wk4 dips below Wk3, Wk7 dips below Wk6.
    """
    weekly = curve["weekly_G_load_units"]
    # Wk4 (idx 3) < Wk3 (idx 2)
    assert weekly[3] < weekly[2], "Wk4 must dip below Wk3 (3-up-1-down deload)"
    # Wk7 (idx 6) < Wk6 (idx 5)
    assert weekly[6] < weekly[5], "Wk7 must dip below Wk6 (3-up-1-down deload)"


def test_overall_trajectory_climbs(curve):
    """End-of-program load > start-of-program load by a meaningful margin."""
    weekly = curve["weekly_G_load_units"]
    assert weekly[-1] > weekly[0] * 1.5, "Wk12 should be at least 50% above Wk1"


def test_acwr_band_bounds_present(curve):
    band = curve["expected_invariants"]["acute_chronic_ratio_band"]
    assert band["lower"] == 0.8
    assert band["upper"] == 1.3
    assert band["hard_cap"] == 1.5


def test_verified_daily_anchor_documented(curve):
    """The recon dossier verified one specific daily 5-tuple → G mapping.

    Phase 2.1's load_math must reproduce G≈2145 from (40 throws, 50% intent, 45ft).
    """
    meta = curve["_meta"]
    if "verified_daily_anchor" not in meta:
        # The richer extraction (post-Drive-alias-resolution) may drop this in
        # favor of the full daily_5tuples grid. That's fine.
        return
    anchor = meta["verified_daily_anchor"]
    assert anchor["throw_count"] == 40
    assert anchor["intent_pct"] == 50
    assert anchor["distance_ft"] == 45
    assert abs(anchor["G_load_units"] - 2145) <= 5  # ±5 tolerance for transcript precision


def test_compute_simple_acwr_from_weekly_curve(curve):
    """Sanity check the ACWR formula against the curve itself.

    Acute = current week; chronic = trailing 4-week avg (a coarse weekly variant
    of the daily 7d/28d formula). Should stay inside the hard cap at every point.
    """
    weekly = curve["weekly_G_load_units"]
    band = curve["expected_invariants"]["acute_chronic_ratio_band"]
    for i in range(3, len(weekly)):
        chronic = sum(weekly[i - 3:i + 1]) / 4.0
        if chronic == 0:
            continue
        acwr = weekly[i] / chronic
        assert acwr <= band["hard_cap"], f"Wk{i + 1} ACWR {acwr:.2f} exceeds hard cap {band['hard_cap']}"
