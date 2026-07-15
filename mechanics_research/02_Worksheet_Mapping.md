# Worksheet Mapping — `Mechanics_Rebuild_Worksheet.xlsx`

The end-state of this research is a populated workbook (the `.xlsx` the original briefs
reference). The agents produce text/CSV; this file documents how that maps into the
workbook so the paste step is mechanical. (The workbook itself is not committed here — it's
the human-facing destination; these files are the machine-generated source.)

## Sheet: `Drill Library` (rows 7+)
Paste `outputs/drill_library_deduped.csv` starting at row 7. Columns, in order:

| Col | Header | Source field |
|-----|--------|--------------|
| A | Drill / Video name | `drill_or_video_name` |
| B | Primary cue | `primary_cue` |
| C | Layer | `layer` |
| D | Progression level | `progression_level` |
| E | Equipment | `equipment` |
| F | Description | `description` |
| G | Sets × reps | `sets_x_reps` |
| H | Source | `source` |
| I | Source URL | `source_url` |
| J | Timestamp | `timestamp` |
| K | Phase to start | `phase_to_start` |
| L | Density score | `density_score` |
| M | Sources count | `sources_count` (added by Agent 5) |
| N | Notes | `notes` |

## Sheet: `Video Catalog` (rows 5+)
One row per source video (not per drill). Pull from the four raw agent CSVs
(`outputs/agent{1..4}_*.csv`), de-duplicated by `source_url`:

| Col | Header | Source |
|-----|--------|--------|
| A | Video / article title | `source` |
| B | Channel / site | agent (Bauer / Tread / Cressey / Driveline) |
| C | URL | `source_url` |
| D | Primary cue(s) covered | union of `primary_cue` for that URL |
| E | Best timestamp | `timestamp` of highest-density row |
| F | Density | max `density_score` for that URL |

## Sheet: `Cue Programs`
Paste the four markdown tables from `outputs/cue_programs.md`, one block per cue
(Staying Closed, Hip Rotation, Arm Path, Release). Each block = a 4–6 week progression with
week / cue word / drills / equipment / sets×reps.

## Sheet: `Velocity Framework` (if present)
Paste `outputs/velocity_framework.md` (conservative year-1 weighted-ball + CNS protocol).

## Phase legend (shared across sheets)
`phase_to_start` values map to the throwing build:
- **Phase 3** — Pattern / constraint work, plyo balls, no full-effort throwing.
- **Phase 4** — Baseballs + light weighted, intro intent.
- **Phase 5** — Baseballs primarily, building intent.
- **Phase 6** — Transfer: bullpens, live BP, max-intent unlocked (year-1 ceiling lifts here).
