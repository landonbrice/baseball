# Phase 1: Trajectory-Aware Triage — Design Spec

> Written: 2026-04-18
> Direction doc: `DIRECTION_Phase1_Trajectory_Aware_Triage.md`
> Status: Approved design — pending implementation plan

---

## Problem

The current triage engine (`bot/services/triage.py`, ~300 lines) makes purely point-in-time
decisions using flat yellow-trigger counting. Three failures:

1. **No trajectory awareness.** Arm feel 5 after dropping from 9 over three days gets the
   same flag as arm feel 5 that's been stable all week.
2. **No rotation context.** Arm feel 5 on Day 1 post-outing (expected soreness) is treated
   the same as arm feel 5 on Day 5 (red flag).
3. **Flat trigger accumulation.** "Bad sleep + mild forearm tightness" produces the same RED
   as "UCL sensation + grip drop." At 12 active pitchers this creates unacceptable false-positive
   rates that will only grow.

## Decisions Made

| Question | Decision | Rationale |
|----------|----------|-----------|
| Sprint 1a prerequisite | **Skip** — build trend logic directly into Phase 1 | Sprint 1a was standalone metadata; Phase 1 absorbs it. No throwaway module. |
| Rotation day semantics | **Increment until new outing logged.** No assumption of thrown. | If a pitcher doesn't log, the system shouldn't guess. UChicago scraper for auto-detection is a separate follow-up. |
| Reliever pitch count missing | **Default to "heavy" bucket** (25+) when count unknown | Safer assumption. Pitch count is reliably tracked but can be absent. |
| Baseline storage | **JSONB in `pitcher_training_model.baseline_snapshot`** with 24h TTL + outing-triggered invalidation | Cross-request reuse without new tables. Plan says no new Supabase tables. |
| arm_clarification migration | **Clean up and move into triage()** | Triage owns all flag decisions. Current override in checkin_service L131-142 is a workaround. |
| Branch strategy | **Git worktree** at `../Baseball-phase1` on `phase1-trajectory-triage` | Main stays clean for prod. Worktree enables isolated Telegram testing via dev bot token. |
| Rollout strategy | **Hard cutover** — new scoring goes live when Slice 3 merges | The whole point is the new system is more correct. No shadow mode needed. |
| Stall detection threshold | **Only flag below expected** — stall fires only if flat/declining value is below floor | Prevents false positives from consistent reporters (e.g., pitcher always reports 7). |
| Baseline query timing | **Inline in check-in** — query runs during process_checkin() | Simple, guarantees fresh data. 24h cache means heavy query runs at most once/day/pitcher. |
| Trajectory messaging | **Transparent callout** — reasoning explicitly says "dropped from 8 to 6 over 4 days" | Builds trust, educates pitchers. No gaming concern outweighs transparency. |
| Reliever appearance count | **Use game_scraper data** — query team_games for appearances this week | More reliable than self-reported. game_scraper already tracks this. |
| Start proximity | **Fold into load score** — days-to-start becomes a load input (+2 for 0-1 days, +1 for 2 days) | Compounds with tissue concerns via interaction rules. Cleaner than separate post-check. |
| Golden snapshot tests | **Hand-crafted fixtures** — 15-20 deterministic scenarios covering every code path | No prod dependency, version-controlled, covers: instant RED, 2-trigger RED, 1-trigger YELLOW, modified green, green, start proximity. |
| Reliever rotation counting | **Any appearance = 1 rotation** for tier purposes | Simple, maps to how relievers work. 3 appearances = tier 3 eligibility. |

---

## Architecture

### Files Touched

| File | Change | Risk |
|------|--------|------|
| `bot/services/triage.py` | **Rewrite.** Expanded signature, 3-category scoring, recovery curves, trajectory. | High — core logic |
| `bot/services/baselines.py` | **New.** Baseline computation, caching, recovery curve lookup. | Low — isolated |
| `data/constraint_defaults/population_baselines.yaml` | **New.** Population-level defaults. | Low — data only |
| `bot/services/checkin_service.py` | **Modified.** Assembles recent history, fetches baseline, calls new triage, removes arm_clarification override. | Med — caller path |
| `bot/services/db.py` | **Modified.** Add `baseline_snapshot` to training model read/write. | Low — additive |
| Supabase migration | `ALTER TABLE pitcher_training_model ADD COLUMN baseline_snapshot JSONB DEFAULT '{}'::jsonb;` | Low — additive DDL |

### Data Flow

```
check-in arrives
  |
  v
checkin_service.process_checkin()
  |-- fetch last 14d daily_entries (for recent_arm_feel + recent_history)
  |-- baselines.get_or_refresh(pitcher_id, daily_entries_history)
  |     |-- if baseline_snapshot missing, stale (>24h), or new outing since last compute:
  |     |     recompute from daily_entries, write to pitcher_training_model.baseline_snapshot
  |     |-- else: return cached snapshot
  |-- triage(arm_feel, sleep_hours, pitcher_profile,
  |         ...,
  |         recent_arm_feel=[{date, arm_feel, rotation_day}, ...],  # last 7d
  |         recent_history=[{full daily entry}, ...],                # last 14d
  |         pitcher_baseline={tier, rotation_day_baselines, ...},
  |         arm_clarification="expected_soreness" | "concerned" | None,
  |         whoop_strain_yesterday=float)
  |     |
  |     |-- [INTERNAL] compute trajectory metrics (absorbed Sprint 1a)
  |     |     rate_of_change, persistence, slope
  |     |-- [INTERNAL] evaluate recovery curve (starter vs reliever)
  |     |     stall, pace, late-rotation readiness, cross-week slope
  |     |-- [INTERNAL] compute tissue / load / recovery scores (0-10 each)
  |     |-- [INTERNAL] apply interaction rules -> flag_level
  |     |-- return existing shape + additive fields:
  |           category_scores: {tissue, load, recovery}
  |           trajectory_context: {recovery_curve_status, chronic_drift, trend_flags}
  |           baseline_tier: 1 | 2 | 3
  |
  v
plan_generator consumes triage result unchanged (no modifications)
```

### Backward Compatibility Contract

1. **Output shape is additive.** `flag_level`, `modifications`, `alerts`, `protocol_adjustments`,
   `reasoning` all preserved with identical semantics.
2. **No-new-args call = identical output.** When `recent_arm_feel`, `recent_history`,
   `pitcher_baseline`, and `arm_clarification` are all None/absent, the rewritten triage
   produces byte-identical results to the current implementation.
3. **Plan generator untouched.** It reads `flag_level` + `modifications` — those don't change.
4. **New fields are additive.** `category_scores`, `trajectory_context`, `baseline_tier` are
   extras that downstream consumers can optionally use.
5. **Golden snapshot tests.** Before rewriting, capture current triage output for representative
   scenarios across all 12 pitchers. Assert the rewrite matches when called without new args.

---

## Three-Category Scoring System

(Full scoring tables are in `DIRECTION_Phase1_Trajectory_Aware_Triage.md` and are the source
of truth. Summary here for quick reference.)

### Category 1: Tissue Score (0-10, highest priority)

Direct arm/body stress indicators. **Only category that can independently produce RED.**

Key inputs: absolute arm feel (weighted by severity), deviation from rotation-day expected,
recovery curve violations (stall/pace/late-rotation), chronic drift, forearm tightness
(by severity), UCL sensation, grip drop, consecutive low days, arm_clarification,
absorbed Sprint 1a signals (rate-of-change, persistence, slope).

### Category 2: Load Score (0-10)

Training demand. High load alone doesn't shut down — narrows safety margin.

Key inputs: pitch count from last outing, days since outing, reliever appearances/week
(from game_scraper/team_games), WHOOP strain, lifting volume spike, **start proximity**
(0-1 days to start = +2, 2 days = +1 — folded into load score rather than separate post-check).

### Category 3: Recovery Score (0-10)

Systemic readiness. Poor recovery alone produces MODIFIED GREEN, never RED.

Key inputs: sleep hours, WHOOP recovery, HRV drop, sleep performance, energy.

### Interaction Rules

These replace the current "count yellow triggers" logic entirely.

| Flag | Condition | Key difference from current system |
|------|-----------|-------------------------------------|
| RED | TISSUE >= 7 | Standalone — severe tissue signal |
| RED | TISSUE >= 4 AND LOAD >= 4 | Tissue + demand compound |
| RED | TISSUE >= 4 AND recovery curve stall + pace below floor | Tissue + body not recovering |
| YELLOW | TISSUE >= 3 | Any meaningful tissue signal alone |
| YELLOW | LOAD >= 4 AND RECOVERY >= 4 | High demand + poor recovery (no tissue needed) |
| YELLOW | chronic_drift active | Slow decline over weeks |
| YELLOW | Recovery curve stall (Day N <= Day N-1, N >= 3) | Body not bouncing back |
| MODIFIED GREEN | RECOVERY >= 3 alone | Poor readiness, no tissue/load concern |
| MODIFIED GREEN | LOAD >= 3 alone | Moderate demand context |
| MODIFIED GREEN | TISSUE 1-2 | Very mild tissue awareness |
| GREEN | All below thresholds | |

**Critical change:** Two recovery signals (bad sleep + low WHOOP) = MODIFIED GREEN, not RED.
Two tissue signals = YELLOW or RED by severity. Categories are NOT interchangeable.

---

## Recovery Curve Model

### Starter (7-day rotation)

Population defaults; individual baselines override when available.

| Rotation Day | Floor | Expected |
|-------------|-------|----------|
| Day 0 | n/a | n/a (game day) |
| Day 1 | 4 | 6 |
| Day 2 | 5 | 7 |
| Day 3 | 6 | 8 |
| Day 4 | 7 | 8 |
| Day 5 | 6 | 9 |
| Day 6 | 6 | 9 |

### Reliever

Three curves indexed by intensity:
- **Heavy** (25+ pitches): Day 1 [4,6], Day 2 [6,8], Day 3+ [7,9]
- **Light** (<25 pitches): Day 1 [6,8], Day 2+ [7,9]
- **Extended rest** (5+ days): any day [7,9]

### Detection Rules

- **Stall:** Day N <= Day N-1 for N >= 3 post-outing AND value is below floor = +2 tissue.
  Day 1->2 flatline tolerated. Flat-at-good-value (above floor) does NOT trigger stall.
- **Reversal:** Day N < Day N-1 (any day) AND new value is below floor = +3 tissue.
- **Pace:** arm_feel < floor = +1 per point below floor.
- **Late-rotation readiness:** Day 5-6 with arm_feel < 6 = +2 tissue.
- **Cross-week slope:** current rotation recovery slope < 0.7x average of prior 3+ rotations = +2 tissue.

### Expected Soreness Integration

- `arm_clarification = "expected_soreness"` AND rotation day <= 2: reduce TISSUE by 2.
  Does NOT reset recovery curve tracking.
- `arm_clarification = "concerned"`: +3 TISSUE, always escalates.

---

## Dynamic Baseline System

### Three Tiers

| Tier | Data Required | Behavior |
|------|---------------|----------|
| 1 — Population | < 1 full rotation | Population defaults, trajectory informational only, +2 tolerance band |
| 2 — Low-confidence | 1-2 rotations | 50/50 blend, trajectory can escalate to MODIFIED GREEN/YELLOW, +1 tolerance |
| 3 — High-confidence | 3+ rotations | Individual data dominates, full authority, tight thresholds |

### Baseline Snapshot Schema (stored in `pitcher_training_model.baseline_snapshot`)

```json
{
  "tier": 2,
  "rotation_day_baselines": {
    "1": {"mean": 6.2, "sd": 1.1, "n": 8},
    "2": {"mean": 7.4, "sd": 0.9, "n": 7}
  },
  "overall_mean": 7.1,
  "overall_sd": 1.3,
  "rotations_completed": 2,
  "total_check_ins": 18,
  "rolling_14d_mean": 6.8,
  "prior_14d_mean": 7.3,
  "chronic_drift": 0.5,
  "drift_threshold": 1.0,
  "drift_flagged": false,
  "computed_at": "2026-04-18T09:00:00-05:00",
  "last_outing_date": "2026-04-15"
}
```

### Cache Invalidation

Recompute when:
- `baseline_snapshot` is missing or empty
- `computed_at` is > 24 hours old
- A new outing has been logged since `last_outing_date`

### Chronic Drift Calculation

```
drift = 28d_mean - rolling_14d_mean
threshold = max(1.0, 0.75 * 28d_sd)
if drift > threshold: flag active, +2 tissue
```

Minimum 14 check-in days before drift computation fires.

---

## Sparse Data Handling

1. Rotation day advances by calendar regardless of check-in.
2. Trajectory signals require 3+ data points in last 7 days. Fewer = null, fall back to
   point-in-time scoring.
3. Recovery curve stall detection needs previous day's arm_feel. Missing = skip stall check.
   Pace detection (vs. floor) still fires since it only needs today's value.
4. Baseline tier based on check-in count, not calendar days.
5. Missing data is never treated as zero or as a flag. Excluded from calculations.

---

## What Moves from checkin_service Into Triage

### Current arm_clarification override (checkin_service.py L131-142)

```python
# CURRENT — to be removed:
if arm_clarification == "expected_soreness" and arm_feel <= 4:
    if triage_result["flag_level"] == "red":
        triage_result["flag_level"] = "yellow"
        triage_result["reasoning"] += " ... downgraded from red."
    triage_result.setdefault("modifications", []).append("expected_soreness_override")
elif arm_clarification == "concerned":
    if triage_result["flag_level"] == "green":
        triage_result["flag_level"] = "yellow"
        triage_result["reasoning"] += " ... upgraded to yellow."
```

### New behavior (inside triage):

- `expected_soreness` on rotation day <= 2: -2 from tissue score (integrated into scoring,
  not a post-hoc override). Recovery curve tracking continues.
- `concerned`: +3 to tissue score (always escalates via scoring, not a flag flip).
- Both produce reasoning entries explaining the adjustment.

This is cleaner because the scoring system handles it proportionally rather than
binary flag flipping.

---

## Ship Plan: 4 Slices

### Slice 1: Foundation

**Creates:** `data/constraint_defaults/population_baselines.yaml`, `bot/services/baselines.py`
**Migrates:** `baseline_snapshot` JSONB column on `pitcher_training_model`
**Tests:** Unit tests for baseline computation with fixture data (all 3 tiers), recovery curve
lookup, chronic drift calculation, cache invalidation logic.
**Risk:** Low. No triage changes, no caller changes. Purely additive.

### Slice 2: Triage Rewrite

**Rewrites:** `bot/services/triage.py` — 3-category scoring, interaction rules, recovery curve
evaluation, trajectory computation, arm_clarification integration.
**Contract:** All new args optional with defaults. No-new-args call = identical output (golden snapshots).
**Tests:** Golden snapshots for backward compat. New tests for each acceptance criterion in the
direction doc (scoring scenarios, interaction rules, recovery curve detection, sparse data).
**Risk:** Medium. Core decision logic changes. Golden snapshots are the safety net.

### Slice 3: Wire Into checkin_service

**Modifies:** `bot/services/checkin_service.py` — assemble `recent_arm_feel` and `recent_history`
from Supabase, fetch/refresh baseline, pass new args to triage, remove arm_clarification override.
**Modifies:** `bot/services/db.py` — baseline_snapshot read/write in training model functions.
**Tests:** Integration tests with realistic Supabase fixture data.
**Risk:** Medium. This is where the new triage goes live. The golden snapshot guarantee from
Slice 2 means the worst case is "new args produce unexpected flag" — rollback = don't pass new args.

### Slice 4: Observability

**Adds:** Log category_scores, baseline_tier, recovery curve status per check-in.
**Extends:** `pre_training` JSONB in `daily_entries` to include `category_scores` and `baseline_tier`.
**Optional:** Expose category breakdown in mini-app "why" sheet (non-blocking sugar).
**Risk:** Low. Additive logging only.

---

## What's Explicitly Punted

- UChicago schedule/pitch-count scraper for outing auto-detection (separate sprint)
- Category score visualization in coach dashboard
- Per-pitcher baseline admin inspection command
- Phase 4 science refinement of YAML values (Cressey/Driveline/Tread data)
- trend_detection.py standalone module (Sprint 1a never shipped — nothing to deprecate)
- Modifications to plan_generator.py (untouched per direction doc)

---

## Source of Truth Hierarchy

1. `DIRECTION_Phase1_Trajectory_Aware_Triage.md` — scoring tables, thresholds, interaction rules
2. `CLAUDE.md` lines 150-160 — 1-10 scale thresholds (arm feel, energy)
3. This spec — architecture, slicing, decisions
4. Implementation plan (to be generated) — file-level task breakdown
