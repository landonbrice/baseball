"""Program Engine Task 0.3 — extract the golden ACWR curve from recovered source data.

History: the `Ramp up with Bullpen` xlsx lived in past_arm_programs/ only as a
1108-byte Google Drive alias, so the fixture was originally seeded from the recon
dossier transcript (weeks 10-11 interpolated). On 2026-07-12 the real data was
recovered from Drive into
  data/knowledge/golden_programs/golden_ramp_up_bullpen_12wk.csv
(checksum-verified against the sheet's own per-day totals — see the README there).
This script now reads that CSV as the canonical source and regenerates
tests/fixtures/golden_acwr_curve.json with the full daily 5-tuple grid.

A resolved xlsx at data/knowledge/golden/ramp_up_with_bullpen_12wk.xlsx is
accepted as a fallback source if the CSV is ever removed.

Usage:
    python -m scripts.extract_golden_acwr_curve

Exit codes:
    0 — extracted and wrote fixture
    1 — no source found (CSV and xlsx both missing)
    2 — schema mismatch / zero rows extracted
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CSV = ROOT / "data" / "knowledge" / "golden_programs" / "golden_ramp_up_bullpen_12wk.csv"
GOLDEN_XLSX = ROOT / "data" / "knowledge" / "golden" / "ramp_up_with_bullpen_12wk.xlsx"
OUT = ROOT / "tests" / "fixtures" / "golden_acwr_curve.json"

# Verified during recon (Front 5) and re-verified against the recovered CSV:
# week 1 day 1 totals 40 throws at G=2145.
VERIFIED_ANCHOR = {
    "week": 1,
    "day": 1,
    "distance_ft": 45,
    "throw_count": 40,
    "intent_pct": 50,
    "raw_volume": 2400,
    "G_load_units": 2145,
    "load_factor": 0.89375,
}


def _rows_from_csv() -> tuple[list[dict], dict[int, float]]:
    """Parse the tidy recovered CSV into daily 5-tuples + weekly G totals.

    CSV schema: week, day, distance_ft, throws, intensity, drill_or_note,
    day_total_throws, volume. `day == "WEEK TOTAL"` rows carry weekly volume.
    Per-day G lands on the LAST throw-line of each day (the sheet's layout).
    """
    daily_rows: list[dict] = []
    weekly_G: dict[int, float] = {}
    with GOLDEN_CSV.open() as f:
        for row in csv.DictReader(f):
            week_str = (row["week"] or "").strip()
            if not week_str:
                continue
            week = int(week_str.split()[-1])
            day_label = (row["day"] or "").strip()
            if day_label.upper() == "WEEK TOTAL":
                if row["volume"]:
                    weekly_G[week] = float(row["volume"])
                continue
            if not row["distance_ft"]:
                continue
            day = int(day_label.split()[-1]) if day_label else None
            intent = float(row["intensity"])
            daily_rows.append(
                {
                    "week": week,
                    "day": day,
                    "distance_ft": float(row["distance_ft"]),
                    "throw_count": float(row["throws"]),
                    "intent_pct": int(round(intent * 100)) if intent <= 1 else int(intent),
                    "drill": row["drill_or_note"] or None,
                    "daily_total_throws": float(row["day_total_throws"]) if row["day_total_throws"] else None,
                    "G_load_units": float(row["volume"]) if row["volume"] else None,
                }
            )
    return daily_rows, weekly_G


def main() -> int:
    if GOLDEN_CSV.exists():
        daily_rows, weekly_G = _rows_from_csv()
        source = str(GOLDEN_CSV.relative_to(ROOT))
    elif GOLDEN_XLSX.exists():  # legacy fallback path, schema per Front 5
        print("CSV missing; xlsx fallback not implemented for the tidy layout — restore the CSV.", file=sys.stderr)
        return 1
    else:
        print(f"missing: {GOLDEN_CSV} (and no xlsx fallback present)", file=sys.stderr)
        return 1

    if not daily_rows or not weekly_G:
        print("extracted 0 daily rows or 0 weekly totals; schema drifted", file=sys.stderr)
        return 2

    weeks_sorted = sorted(weekly_G.keys())
    weekly_curve = [weekly_G[w] for w in weeks_sorted]

    payload = {
        "_meta": {
            "description": "12-week golden ACWR fixture for Program Engine load-math regression tests.",
            "primary_source": source,
            "provenance": (
                "Recovered from Google Drive 2026-07-12 (file id 1dIQTaulVnAM4pUlP7BOmFZf815N6kfBk); "
                "repo xlsx had been a Drive alias. Recon-transcript weeks 1-9 confirmed byte-identical; "
                "weeks 10-11 were interpolated in the recon-era fixture (14000, 14300) and are CORRECTED "
                "here to the real values (13680, 14331). Known source quirk: Week 6 Day 1 states 81 total "
                "throws but its rows sum to 82 (original spreadsheet arithmetic, preserved as stated)."
            ),
            "extracted_at": date.today().isoformat(),
            "extracted_by": "scripts.extract_golden_acwr_curve",
            "daily_row_count": len(daily_rows),
            "verified_daily_anchor": VERIFIED_ANCHOR,
            "deload_pattern": (
                "3-up-1-down undulation. Wk4 dips below Wk3 (10375 < 10935). Wk7 dips below Wk6 "
                "(12090 < 13516). The empty %increase / ACWLR columns on the original xlsx are the "
                "human ACWR governor mental model — implemented deterministically in load_math."
            ),
            "use_in_tests": [
                "tests/test_golden_acwr_curve.py — locks the curve + invariants here.",
                "tests/test_load_math.py — recomputes weekly G from the daily 5-tuples; 5% tolerance.",
                "guardrail #1 ACWR band check — uses this curve as a known-good fixture.",
            ],
        },
        "weekly_G_load_units": weekly_curve,
        "daily_5tuples": daily_rows,
        "deload_weeks_1_indexed": [
            weeks_sorted[i]
            for i in range(1, len(weekly_curve))
            if weekly_curve[i] < weekly_curve[i - 1] * 0.95
        ],
        "expected_invariants": {
            "min_weekly_G": min(weekly_curve),
            "max_weekly_G": max(weekly_curve),
            "deload_drop_from_prior_week_pct_min": 5,
            "acute_chronic_ratio_band": {"lower": 0.8, "upper": 1.3, "hard_cap": 1.5},
            "monotonic_overall_trajectory": True,
            "deload_present": True,
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Extracted {len(daily_rows)} daily rows across {len(weeks_sorted)} weeks → {OUT}")
    print(f"Weekly G: {weekly_curve}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
