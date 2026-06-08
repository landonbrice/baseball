# Mechanics Research Agent Briefs (Landon Brice build)

> Folded-in, parameterized copy of the original five-agent brief. The generic "target
> pitcher profile" has been replaced by a pointer to `00_Pitcher_Dossier_LandonBrice.md`
> so the agents filter for **Landon's actual fault chain** (hip-shoulder separation +
> arm spiral, lead-leg-block / front-side as the load-bearing fix).
>
> Reusable as a template: swap the dossier for a different pitcher and the five prompts
> re-aim automatically. Kept **separate** from the `pitcher_program_app/` codebase.

Five agents compile pitching-mechanics content into a structured drill library + video
catalog. Agents 1–4 run **in parallel** (independent). Agent 5 (synthesizer) merges them.

---

## Context for All Agents (shared)

**Target pitcher:** see `00_Pitcher_Dossier_LandonBrice.md` (the single source of truth for
relevance). In short: RHP starter, ~88 mph, advanced lifter, flexor-pronator / medial-elbow
history → **conservative load year**. The two keys are **hip-shoulder separation** and the
**arm spiral**; the **lead leg block / front side** is the most important single feature.

**Fault chain to filter against (rank content by how directly it fixes these):**
- Good drop, **no rotate** — drop→rotate transition fails.
- **Back hip leaks** (never clears/closes).
- **Front hip swings open early / lead leg lands open** → no separation window.
- **Shoulders fly open**, trunk not neutral at landing.
- **Push arm action** — force never spirals up to the arm.
- Target model: **glove + lead leg together, rotate late → back-hip drive → lead-leg block
  pulls torso→shoulder→arm** (whip, not push) → release off the fingers.

**Four target cues — every piece of content gets tagged against these** (Landon priority in parens):
1. **Staying Closed** (P1) — hip-shoulder separation, glove-side discipline, glove-and-lead-leg-together, delayed front side, lead leg block, trunk lean/neutral.
2. **Hip Rotation** (P2) — leg lift, hip drift, back-hip drive/clearing, front-hip timing, trail-leg drive, lead-hip timing.
3. **Arm Path** (P3) — hand-break timing, scap load, layback at foot strike, elbow leads forearm, whip vs push, release extension.
4. **Release** (P4) — pronation timing, wrist position, finger placement, spin axis, finger drive.
   - (A fifth tag, **Velocity / CNS**, is used for arm-speed / weighted-ball / CNS-firing content; **Diagnostic** is used for assessment content.)

**Four layers — every piece of content gets tagged by layer:**
- **Layer 1 — Diagnosis:** video assessment, identifying flaws.
- **Layer 2 — Pattern:** constraint-led drills (plyo balls, towel, walking windups) — no full-effort throwing.
- **Layer 3 — Loading:** weighted balls, long toss, intent training — adds force to pattern.
- **Layer 4 — Transfer:** bullpens, live BP, game application.

**Anti-drift instruction (all agents):** If content is general fitness, hitting, mental
game, baseball culture, business/podcast banter, recruiting/showcase, or college/MLB news —
**SKIP IT**. If it's pitching mechanics but doesn't touch Landon's fault chain (§above),
deprioritize hard. Quality over coverage.

**Volume constraint:** Return **20–40 rows**. If more found, rank by `density_score` ×
relevance-to-Landon and return the top 40.

**Output schema (all agents, CSV):**

```csv
drill_or_video_name,primary_cue,layer,progression_level,equipment,description,sets_x_reps,source,source_url,timestamp,phase_to_start,density_score,notes
```

- `primary_cue` ∈ {Arm Path, Staying Closed, Hip Rotation, Release, Velocity / CNS, Diagnostic}
- `layer` ∈ {1 - Diagnosis, 2 - Pattern, 3 - Loading, 4 - Transfer}
- `progression_level` ∈ {1–5} (1 = entry, 5 = advanced)
- `equipment` = comma-separated list
- `sets_x_reps` = e.g. "3 x 8" or "8 throws"
- `timestamp` = "mm:ss-mm:ss" of the key segment (use "" if a blog/article)
- `phase_to_start` ∈ {Phase 3, Phase 4, Phase 5, Phase 6}
- `density_score` ∈ {1–5} (1 = thin, 5 = packed)
- `notes` = cue word, common mistake, pairing suggestion, **and a `relevance:` tag noting
  which Landon fault it addresses** (e.g. `relevance: fixes early front-side fly-open`)

**CSV hygiene:** quote any field containing a comma; one row per drill; header row first.

---

## AGENT 1 — Trevor Bauer YouTube Compiler

```
ROLE: Compile Trevor Bauer's free YouTube content on pitching mechanics, drills, weighted
balls, pitch design, and velocity development into the CSV schema.

CONTEXT: Use the shared "Context for All Agents" above. Filter for Landon's fault chain —
weight Staying Closed (P1) and Hip Rotation (P2) above Arm Path/Release.

SOURCES TO MINE:
- Trevor Bauer main channel: https://www.youtube.com/@TrevorBauer
- Momentum (Bauer's company) uploads
- Bauer Outage clips ONLY where pitching-mechanics-specific
- Bauer guest spots on pitching channels (Tread, Driveline) — de-prioritize vs his own channel

PRIORITIZE: drill demonstrations with clear instruction; Bauer explaining what a cue means
and why; named drills (he names many — "Pivot Pickoff," "Walking Windup," "Long Pong");
weighted-ball protocols; pitch-design (release/spin/axis); breakdowns of his own delivery —
ESPECIALLY anything on staying closed, hip-shoulder separation, front-side/lead-leg block,
and converting push→whip arm action.

EXCLUDE: training-day vlogs, business/Momentum commentary, game/start recaps, pranks/comedy,
recruiting, anything older than 8 years.

OUTPUT: CSV per schema. Use Bauer's own drill names. Include the key-segment timestamp.
RETURN: 20–40 rows. One video with 5 distinct drills → 5 rows.

WRITE your CSV to: /home/user/baseball/mechanics_research/outputs/agent1_bauer.csv
```

---

## AGENT 2 — Tread Athletics Free Content Compiler  ★ highest expected relevance

```
ROLE: Compile Tread Athletics' free content (YouTube + blog) — especially front-side
mechanics, lead leg block, hip-shoulder separation, and remote development.

CONTEXT: shared context above. THIS AGENT IS THE MOST IMPORTANT FOR LANDON — his headline
fault (front side flies open early, no lead-leg block, lost separation) is exactly Tread's
signature content area. Mine it deeply.

SOURCES TO MINE:
- Tread Athletics YouTube: https://www.youtube.com/@TreadAthletics
- Tread blog: https://treadathletics.com (free articles only — skip paid program pages)
- Tread podcast clips where mechanics-specific
- Tread social (X/@TreadHQ, TikTok/@tread_athletics) drill threads where a concrete drill is shown

PRIORITIZE: the "Front Side" series; LEAD LEG BLOCK drills (their best content — capture
every variation); hip-shoulder separation training (counter-rotation, band-tension-on-back-hip
constraints); "stay closed / late front side" cues; plyo-ball progressions; before/after
case studies. Capture lead-leg-block weight-room exercises too (lead hip flexion, lead hip IR,
hip airplanes, rotational KB swing, split-stance MB taps, ipsilateral cable row, 3D strap
rotations) and tag them Hip Rotation / Staying Closed.

EXCLUDE: paid program/product pages, pure "sign up" content, athlete profiles w/o
instruction, recruiting.

SPECIAL TAG: Tread sequences drills (Level 1/2/3). Capture the level in progression_level
and note the series name in `notes`.

OUTPUT: CSV per schema. Note Tread progression-series membership in `notes`.
RETURN: 20–40 rows.

WRITE your CSV to: /home/user/baseball/mechanics_research/outputs/agent2_tread.csv
```

---

## AGENT 3 — Cressey Sports Performance Compiler

```
ROLE: Compile Eric Cressey's free content on the strength / mobility / movement-quality
prerequisites that ENABLE the mechanics — not drills, the underlying physical capacity.

CONTEXT: shared context above. For Landon, weight: (a) T-spine + rib-cage / trunk control
that lets him keep the trunk neutral while hips rotate (separation prerequisite); (b) hip
mobility + hip IR/ER that lets the back hip clear and the front hip post (lead-leg-block
prerequisite); (c) scapular control for a clean arm path; (d) flexor-pronator / medial-elbow
durability work given his history.

SOURCES TO MINE:
- Cressey Sports Performance YouTube: https://www.youtube.com/@CresseySportsPerformance
- Eric Cressey blog: https://ericcressey.com (free articles)
- Cressey appearances on pitcher-specific channels (Tread, Driveline)

PRIORITIZE: shoulder mobility/stability (scap control → arm path); T-spine mobility (→
staying closed + separation); hip mobility / hip IR for pitchers (→ hip rotation + lead-leg
block); lead-leg-block / front-side from a strength-coach lens; posterior chain; cuff +
elbow health (esp. flexor-pronator); common physical limitations that force mechanical
compensations.

EXCLUDE: general fitness, non-pitcher content, product reviews, business/philosophy.

TAGGING NOTE: most Cressey content maps to Diagnostic (1) or Pattern (2). In `notes`,
specify the exact prerequisite (e.g. "T-spine extension limitation," "hip IR deficit,"
"scap upward-rotation deficit") and which Landon fault it unlocks.

OUTPUT: CSV per schema. `equipment` field is critical here (band, foam roller, cable, DBs).
RETURN: 20–40 rows.

WRITE your CSV to: /home/user/baseball/mechanics_research/outputs/agent3_cressey.csv
```

---

## AGENT 4 — Driveline Free Content Compiler

```
ROLE: Compile Driveline Baseball's free content on mechanics, plyo-ball training,
weighted-ball protocols, kinematic sequencing, and pitch design.

CONTEXT: shared context above. For Landon, over-index on kinematic-sequencing content
(pelvis → trunk → arm; how separation is created and timed) and plyo-ball constraint drills
that train staying closed / front-side. Respect the conservative-load constraint (see §below).

SOURCES TO MINE:
- Driveline YouTube: https://www.youtube.com/@DrivelineBaseball
- Driveline blog: https://www.drivelinebaseball.com/blog (free articles only)
- Driveline open-access research papers
- Driveline-affiliated coaches where content is free

PRIORITIZE: plyo-ball progression videos (flagship — Pivot Pickoff, Rocker, Reverse Throw,
Half-Kneel, etc. — capture exact name, ball weight in oz, progression level, tag Layer 2);
weighted-ball protocol explanations; KINEMATIC SEQUENCING content (this directly explains
Landon's separation/spiral problem); pitch-design (spin axis, release point, spin
efficiency); velocity-development science; recovery/overuse research; open-access papers.

EXCLUDE: paid program/product pages, "sign up for our gym," marketing testimonials,
hitter content.

CONSERVATIVE-LOAD FILTER: Landon is in a conservative build year (flexor-pronator history).
Capture overload protocols for completeness but TAG them clearly in `notes` as
"year-2 / not-now" if they involve 7oz+ overload, pulldowns, or sustained max intent.
Prefer underload (3–4oz) CNS work and ≤6oz.

OUTPUT: CSV per schema. Use Driveline's exact drill names; note if a drill is part of their
published throwing-program sequence.
RETURN: 20–40 rows.

WRITE your CSV to: /home/user/baseball/mechanics_research/outputs/agent4_driveline.csv
```

---

## AGENT 5 — Synthesizer / Drill Compiler

```
ROLE: Synthesize Agents 1–4 into three deliverables, focused on Landon's fault chain.

CONTEXT: shared context above + 00_Pitcher_Dossier_LandonBrice.md.

INPUT: the concatenated CSV at
  /home/user/baseball/mechanics_research/outputs/99_combined_raw.csv
(≈80–160 rows from the four agents).

DELIVERABLE 1 — DEDUPLICATED DRILL LIBRARY
Merge all rows. Deduplicate drills appearing in multiple sources; for each unique drill keep
the BEST 1–2 source videos (highest density_score). Output one row per unique drill. Drills
with the same name but different equipment/progression are DISTINCT (e.g. "Pivot Pickoff 4oz"
≠ "Pivot Pickoff 6oz"). Add a column `sources_count` = number of agents that surfaced it
(1–4); 3–4 = higher confidence. Keep the `relevance:` note. Sort so Staying Closed +
Hip Rotation (Landon's P1/P2) and lead-leg-block drills surface first.
WRITE to: /home/user/baseball/mechanics_research/outputs/drill_library_deduped.csv

DELIVERABLE 2 — FOUR CUE PROGRAMS
For each cue (Staying Closed, Hip Rotation, Arm Path, Release) produce a 4–6 week
progression: 2–3 drills/week, sequenced by progression_level (start 1 → end 4–5), a clear
cue word per week, equipment matched to phase (Phase 3 = plyo balls; Phase 4 = baseballs +
light weighted; Phase 5+ = baseballs primarily). Lead with Staying Closed and Hip Rotation
since those are Landon's keys. Markdown table per cue.
WRITE to: /home/user/baseball/mechanics_research/outputs/cue_programs.md

DELIVERABLE 3 — VELOCITY LAYER FRAMEWORK
Synthesize "Velocity / CNS" + Layer-3 content into: a YEAR-1 CONSERVATIVE weighted-ball
protocol (NO 7oz+ overload, NO pulldowns, NO max intent during this build); a CNS-firing
protocol; underweight-ball (3–4oz) recommendations for arm speed without medial-elbow
stress; and intent-training notes (delayed to Phase 6 minimum). Markdown.
WRITE to: /home/user/baseball/mechanics_research/outputs/velocity_framework.md

QUALITY GATE: "If a coach ran only these drills, in this sequence, for 18 weeks, would
Landon improve on hip-shoulder separation, the lead-leg block, and the push→spiral arm
action?" If not, add a "## Gaps" section to cue_programs.md naming what's missing.
```

---

## Deployment / run order

1. Run Agents 1–4 in parallel; each writes its own CSV to `outputs/`.
2. Concatenate the four CSVs → `outputs/99_combined_raw.csv` (dedupe headers).
3. Run Agent 5 against the combined file; it writes the three deliverables.
4. Worksheet population (optional, manual): paste `drill_library_deduped.csv` into the
   `Drill Library` sheet (rows 7+), source videos into `Video Catalog` (rows 5+), and the
   Deliverable-2 tables into `Cue Programs`. See `02_Worksheet_Mapping.md`.

**Quality checks before populating the worksheet:**
- Every row has a non-blank cue tag and layer tag.
- Every row has a resolving `source_url`.
- No paid-content references.
- No year-1 violations (no 7oz+ overload, no pulldowns, no max-intent before Phase 6).
