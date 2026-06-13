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

## ★ The curated program (`curated/`) — start here

The 119-drill library was the **data layer**. The `curated/` folder is the **curation pass**:
the 2–3 highest-leverage drills per fault, the biggest coaching laws/cues, and a single
turn-key artifact — built by a second 3-agent pass (curation + protocols, in parallel, then
an HTML assembler).

| File | What it is |
|------|------------|
| **`curated/program.html`** | **The deliverable.** One self-contained HTML page — 3 priority-ordered area cards (Staying Closed → Hip Rotation → Arm Path/Spiral), each with a keystone drill + 2 supports + 1 prereq, cue chips, the laws behind it, "don't overcorrect" callouts, a conservative-load guardrail banner, and a 4-phase week plan. Opens in any browser; print-friendly; zero external dependencies. |
| `curated/agent1_curated_drills.md` | Curation layer — keystone + 2 support + 1 thin prereq per area (13 items), Cressey corrected to prereq-only; every money drill is Bauer/Tread/Driveline. |
| `curated/agent3_protocols_cues.md` | Protocols/cues/guardrails layer — the biggest laws per area, external cue words, year-1 conservative-load guardrails, common mistakes. |

Release was dropped this round; the three areas are ordered by Landon's worst diagnostic
self-scores (glove-side = 1, separation = 2, hip-explosion = 2).

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

## The linear program (master deliverable)

**`Mechanics_Rebuild_Worksheet_LandonBrice.xlsx`** is the assembled, runnable program — the
synthesizer outputs structured into the worksheet's 8 sheets:

| Sheet | State |
|-------|-------|
| README · Diagnostic Framework · Self-Filming · Velocity Layer | Pre-filled (Landon's real self-scores + the conservative-load protocol) — left intact |
| **Drill Library** | Populated with all **119 deduped drills** (+ Density / Notes columns) |
| **Cue Programs** | All bracketed placeholders replaced with **real drills** (Arm Path / Staying Closed Wk7–12, Hip Rotation Wk8–13, Release Wk9–14) |
| **Video Catalog** | **107 unique source videos/articles**, deduped by URL, with cues-covered + density |
| **Weekly Integration** | The **linear spine** — each week Wk7→Wk20 names the exact drills + sets, front-loading Staying Closed + Hip Rotation, layering Arm Path from Wk9, holding Release to Wk12, plus a Phase-5/6 bullpen **transfer ladder** and re-test/re-film checkpoints at Wk6/12/18 |

The diagnostic self-scores in the workbook (glove-side-at-foot-strike = 1, pelvis-shoulder
differential = 2, hip-explosion-sequence = 2) independently confirm Staying Closed + Hip
Rotation as the worst cues, which is why the linear program sequences them first.

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
