# Mechanics Research Project — Landon Brice

A standalone, multi-agent research project that compiles free pitching-mechanics content
(Bauer · Tread · Cressey · Driveline) into a structured drill library, four cue programs,
and a conservative-year velocity framework — all aimed at **one pitcher's** specific fault
chain: lost **hip-shoulder separation** and a **push (vs spiral) arm action** driven by an
early-opening front side and a leaking back hip.

> **Scope boundary:** this directory is intentionally **separate** from
> `pitcher_program_app/` (the Pitcher Training Intelligence app). It does not read or write
> the app's Supabase schema, triage, or program-builder pipeline. It's a research
> deliverable that a human (or a later, deliberate integration) consumes — not app code.

## Files

| File | What it is |
|------|------------|
| `00_Pitcher_Dossier_LandonBrice.md` | Per-pitcher context: the fault chain, the target model, cue priorities, conservative-load constraint. **The relevance filter for every agent.** |
| `01_Agent_Briefs.md` | The five agent prompts (Bauer / Tread / Cressey / Driveline / Synthesizer), folded-in and parameterized for Landon. Reusable as a template. |
| `02_Worksheet_Mapping.md` | How the outputs map into the `Mechanics_Rebuild_Worksheet.xlsx` end-state. |
| `outputs/` | Machine-generated results (see below). |

## Outputs (`outputs/`)

| File | Produced by | Contents |
|------|-------------|----------|
| `agent1_bauer.csv` | Agent 1 | Bauer YouTube drills/videos |
| `agent2_tread.csv` | Agent 2 | Tread front-side / lead-leg-block content (highest relevance) |
| `agent3_cressey.csv` | Agent 3 | Cressey physical-prerequisite work |
| `agent4_driveline.csv` | Agent 4 | Driveline plyo / sequencing / weighted-ball |
| `99_combined_raw.csv` | concat step | All four agent CSVs merged (Agent 5 input) |
| `drill_library_deduped.csv` | Agent 5 | Deliverable 1 — deduped drill library |
| `cue_programs.md` | Agent 5 | Deliverable 2 — four 4–6 week cue progressions |
| `velocity_framework.md` | Agent 5 | Deliverable 3 — conservative year-1 velocity framework |

## How to run

1. Run Agents 1–4 in parallel (each writes its own CSV to `outputs/`).
2. Concatenate → `outputs/99_combined_raw.csv` (single header).
3. Run Agent 5 against the combined file → three deliverables.
4. (Optional, manual) Paste into `Mechanics_Rebuild_Worksheet.xlsx` per `02_Worksheet_Mapping.md`.

## The pitcher in one paragraph

Landon Brice — RHP starter, ~88 mph, advanced lifter, flexor-pronator / medial-elbow history
(treat as a conservative build year). He starts closed and gets a good drop, but can't
convert the drop into rotation: his back hip leaks while his front hip swings open early and
the lead leg lands open, so his shoulders fly open and he loses hip-shoulder separation.
With no separation and no front-side brace, force never spirals up the chain — he pushes the
ball. The fix: glove + lead leg travel together and rotate late, back hip drives, the lead
leg blocks, and the brace pulls torso → shoulder → arm into a whip. Everything here is
ranked by how directly it serves that fix.
