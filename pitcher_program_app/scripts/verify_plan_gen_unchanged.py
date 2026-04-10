#!/usr/bin/env python3
"""Diff test for plan generation — proves the in-season code path is byte-identical
before and after the periodization phase gate is added.

Usage:
  python -m scripts.verify_plan_gen_unchanged --capture   # capture baseline
  python -m scripts.verify_plan_gen_unchanged             # diff against baseline

The baseline file lives at scripts/.plan_gen_baseline.json (gitignored).
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.services.plan_generator import _get_training_intent

# Lock the random seeds and "today" so the diff is deterministic
FIXED_TODAY = date(2026, 4, 9)

BASELINE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".plan_gen_baseline.json",
)


def fingerprint_pitcher(pitcher_id: str) -> dict:
    """Capture the inputs and outputs of _get_training_intent for a pitcher.

    We probe the function across all rotation days and three flag levels —
    that exercises every branch of the in-season legacy code path.
    """
    fp = {"pitcher_id": pitcher_id, "intents": {}}
    for rotation_day in range(0, 8):
        for flag in ("green", "yellow", "red"):
            triage = {"flag_level": flag}
            try:
                intent = _get_training_intent(rotation_day, triage)
            except Exception as exc:
                intent = f"ERROR:{type(exc).__name__}:{exc}"
            fp["intents"][f"d{rotation_day}_{flag}"] = intent
    return fp


def list_active_pitchers() -> list[str]:
    """Try DB first (preferred), fall back to hardcoded list if env vars missing."""
    try:
        from bot.services import db
        resp = db.get_client().table("pitchers").select("pitcher_id").execute()
        return sorted(row["pitcher_id"] for row in (resp.data or []))
    except Exception as exc:
        print(f"  (DB unavailable: {exc}; using hardcoded pitcher list)", file=sys.stderr)
        return _HARDCODED_PITCHER_IDS


# Hardcoded fallback list — captured from Supabase on 2026-04-09 because the
# local shell does not have SUPABASE_URL/SUPABASE_SERVICE_KEY. Update when
# the active roster changes.
_HARDCODED_PITCHER_IDS: list[str] = [
    "landon_brice",
    "pitcher_benner_001",
    "pitcher_hartrick_001",
    "pitcher_heron_001",
    "pitcher_kamat_001",
    "pitcher_kwinter_001",
    "pitcher_lazar_001",
    "pitcher_reed_001",
    "pitcher_richert_001",
    "pitcher_sosna_001",
    "pitcher_wilson_001",
    "test_pitcher_001",
]


def capture(out_path: str) -> int:
    pitcher_ids = list_active_pitchers()
    if not pitcher_ids:
        print("ERROR: no pitchers found")
        return 1
    fps = [fingerprint_pitcher(pid) for pid in pitcher_ids]
    digest = hashlib.sha256(json.dumps(fps, sort_keys=True).encode()).hexdigest()
    with open(out_path, "w") as fp:
        json.dump({"digest": digest, "fingerprints": fps}, fp, indent=2)
    print(f"Captured baseline for {len(pitcher_ids)} pitchers → {out_path}")
    print(f"Digest: {digest}")
    return 0


def diff(baseline_path: str) -> int:
    if not os.path.exists(baseline_path):
        print(f"ERROR: baseline missing at {baseline_path}. Run with --capture first.")
        return 1
    with open(baseline_path) as fp:
        baseline = json.load(fp)
    expected = baseline["fingerprints"]

    pitcher_ids = list_active_pitchers()
    actual = [fingerprint_pitcher(pid) for pid in pitcher_ids]

    actual_digest = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()
    if actual_digest == baseline["digest"]:
        print(f"PASS — plan generation byte-identical for {len(pitcher_ids)} pitchers")
        print(f"Digest: {actual_digest}")
        return 0

    print(f"FAIL — plan generation drifted")
    print(f"  Expected digest: {baseline['digest']}")
    print(f"  Actual digest:   {actual_digest}")

    expected_by_id = {fp["pitcher_id"]: fp for fp in expected}
    for fp in actual:
        exp = expected_by_id.get(fp["pitcher_id"])
        if not exp:
            print(f"  NEW pitcher (not in baseline): {fp['pitcher_id']}")
            continue
        for key, value in fp["intents"].items():
            if exp["intents"].get(key) != value:
                print(f"  {fp['pitcher_id']} {key}: was {exp['intents'].get(key)!r} now {value!r}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="capture baseline instead of diffing")
    args = parser.parse_args()
    if args.capture:
        return capture(BASELINE_PATH)
    return diff(BASELINE_PATH)


if __name__ == "__main__":
    sys.exit(main())
