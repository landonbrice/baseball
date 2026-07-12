# Golden Programs — recovered source data

> Recovered 2026-07-12 from Google Drive (the repo copies in `past_arm_programs/` had been
> macOS **alias files**, not real spreadsheets, since they were first committed — see the
> Program Engine design spec §10 prereq #1 and the recon dossier).

These are the two "crown-jewel" quantified throwing macrocycles the Program Engine's
velocity knowledge pack and ACWR load-math calibration are built from.

| File | Source (Drive file id) | Contents |
|---|---|---|
| `golden_return_to_mound_8wk.csv` / `.xlsx` | `1g3EDOPnNScfonDEikj6IpVrT2P16NHfv` ("Return to mound progression - approx 8 weeks (4).xlsx", 2024-02-26) | ~8-week return-to-mound progression; day-by-day (distance_ft, throws, intensity, drill), per-day totals + volume |
| `golden_ramp_up_bullpen_12wk.csv` | `1dIQTaulVnAM4pUlP7BOmFZf815N6kfBk` ("Ramp up with Bullpen ramp up  (1).xlsx", 2024-05-02) | 12-week ramp-up → bullpen macrocycle; day-by-day 5-tuples, per-day totals, weekly volume totals, pulldown/bullpen phase gates |

## Notes / caveats

- The `.xlsx` for return-to-mound was recovered from Drive with a regenerated
  `[Content_Types].xml` (the original's copy of that boilerplate part didn't survive
  transfer; all data-bearing parts are byte-identical to the Drive original and the
  workbook opens cleanly in openpyxl/Excel).
- The ramp-up program is committed as **CSV extraction only** (values, not the original
  binary). Extraction was checksum-verified against the sheet's own per-day totals and
  weekly volume rows: every day reconciles except **Week 6 Day 1, where the original
  spreadsheet itself states 81 total throws but its rows sum to 82** — original preserved
  as stated, discrepancy noted here. To restore the original binary, download the Drive
  file above into `past_arm_programs/`.
- `past_arm_programs/Ramp up with Bullpen ramp up  (1).xlsx` is **still a macOS alias**
  (1,108 bytes) — do not try to parse it; use the CSV here instead.
- CSV schema: `week, day, distance_ft, throws, intensity, drill_or_note,
  day_total_throws, volume`. Rows with `day = WEEK TOTAL` carry the weekly volume in
  `volume`. Intensity is a 0–1 fraction of max intent.
- These files are **knowledge content** (living layer): the Program Engine's resolver and
  the load-math golden-curve fixtures should treat them as the source of truth for the
  velocity ramp shape. The hand-written summaries in `data/templates/throwing_ramp_up.md`
  and `data/templates/return_to_mound.md` are lossy pre-spec approximations superseded by
  these extractions.
