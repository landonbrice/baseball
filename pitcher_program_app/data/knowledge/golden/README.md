# Golden program reference assets

These are the human-authored crown-jewel programs the Program Engine treats as content/exemplars. They are **editable** (the living-knowledge layer reads them at generation time) and **never compiled into Python**. Edit a file → next generation reflects the change.

## Files

| File | Origin | What it is |
|---|---|---|
| `the_program.xlsx` | Repo (`past_arm_programs/The Program  (1).xlsx`) | 7-tab type-matrix: Inseason 7-Day Split Options 1+2 (Day 0…6 session-type rotation), plus content libraries — Dynamic Warmup, Post Throw Stretch, Arm Care Light, Arm Care Heavy, Plyocare (6-level ladder), Dugout Routines |
| `maintenance_plan.xlsx` | Pitcher upload 2026-06-01 (`2026-05-26_program.xlsx`; identical SHA-1 to the repo copy) | 2-day Maintenance Plan (Day A / Day B): Soft Tissue / Mobilize / Activate / Pre-throw / Pre-hitting blocks. 1.7MB = embedded exercise photos. Pitcher-specific (`landon_brice`) arm-care + activation routine. |
| `periodized_lifting.xlsx` | Pitcher upload 2026-06-01 (newer 43KB version; supersedes the 35KB `2026-05-26_lifting.xlsx` in the repo) | 3-phase periodized lifting program: **Phase 1 Hypertrophy** (begins 6wk post-op, 50-75% 1RM, 30s rest), **Phase 2 Strength** (Wk9+, 80-90% 1RM, 60-120s rest), **Phase 3 Strength-Power** (Wk13+, 87-95% 1RM, 2-5 min rest). Day 1 Posterior Chain / Day 2 Push-Pull. RIR-based set/rep schemes. |
| `pitching_program_final.pdf` | Repo (`past_arm_programs/PITCHING-PROGRAM-FINAL.pdf`) | 36pp: day-type vocabulary (Recovery / Hybrid A / Hybrid B / Velo / Plyo Velo / WB Mound Velo / Mound Velo / Short Box / Game Day / No Throw) + named phase macrocycles (Velocity → Pitch Design Base Line → Shape → Execution → In-season reliever block) + RIR-based lifting tables. |

## Known gap — two macrocycle xlsx are Drive aliases

Two files that were enumerated in the recon dossier (`docs/superpowers/research/2026-05-31-program-engine-recon.md` Front 5) exist in `pitcher_program_app/past_arm_programs/` only as **macOS Drive aliases** (1-2 KB stubs that point at Google Drive, not real xlsx). openpyxl reports `BadZipFile: File is not a zip file`.

| Missing file | Drive-alias size | What it contains (per recon) |
|---|---|---|
| `Ramp up with Bullpen ramp up  (1).xlsx` | 1108 B | 12-week ramp: daily `(distance, throws, intent, drill, daily total, G load units, %increase, ACWLR)`. ACWLR + %increase columns scaffolded but EMPTY — the human ACWR governor mental model. |
| `Return to mound progression - approx 8 weeks (4).xlsx` | 1192 B | 9-week RTT: daily 5-tuple grid. Pulldowns first Wk3; bullpen ramp 15→20→25→30→40→45→50 Wks 5-9; margin notes "Probable live ABs" Wk7, "Probable clearance" Wk8. |

### Recoverability

- **Weekly G curve (12 weeks, `Ramp up with Bullpen`) is recoverable** from the recon dossier — transcribed verbatim: `6960 → 9194 → 10935 → 10375 → 12049 → 13516 → 12090 → 12960 → 13620 → … → 14616`. 3-up-1-down deload undulation (Wk4 + Wk7 dips). The Phase 2 ACWR governor uses this as its regression fixture, with provenance "extracted from recon dossier 2026-05-31".
- **Full daily 5-tuple grid is NOT recoverable** without the raw xlsx. Phase 2's load function calibrates against the weekly curve + one verified daily anchor (`Wk1D1: 40 throws @ 0.5 intent, 45ft → G≈2145`) — sufficient for invariant validation, not for fine-grained daily calibration.

### How to close the gap

On a machine that has the Drive-aliased files: Finder → right-click each `.xlsx` → "Show Original" → save the resolved file outside the Drive folder (e.g. Desktop) → drop them into this directory under the canonical names `ramp_up_with_bullpen_12wk.xlsx` and `return_to_mound_9wk.xlsx`. Task 0.3 can then re-extract the daily 5-tuples for richer calibration.

## How to read these

- **Python:** `openpyxl.load_workbook(path, data_only=True)` for the xlsx; `pdfplumber` or `pypdf` for the PDF. The Program Engine resolver (Task 1.3) wraps these in `_load_golden_exemplars()` and returns structured rows.
- **Humans:** open in Excel/Numbers/Google Sheets. Edits flow into the next program generation via the `knowledge_version` hash in `bot/services/research_resolver.resolve_for_program_gen` (Task 1.3).

## Conventions

- File names are snake_case, no spaces, no parens.
- No version suffixes in filenames — git history is the version.
- New goldens should land here with provenance noted in this README.
