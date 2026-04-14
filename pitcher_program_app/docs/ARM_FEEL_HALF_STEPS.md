# Arm Feel Half-Steps: 1–5 in 0.5 Increments

> Status: Planning
> Created: 2026-04-01
> Priority: Medium — quality-of-life improvement driven by pitcher feedback

## Problem

Pitchers report the 1–5 integer scale feels too coarse. The most common friction point is the 3–4 gap: "my arm feels better than a 3 but not quite a 4." The displayed number on the home screen then feels inaccurate, which erodes trust in the system.

## Solution

Expand arm feel from 5 integer options (1, 2, 3, 4, 5) to 9 half-step options (1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5). Store as float internally. No scale change (still out of 5), just finer resolution.

## Design Decisions

**Triage thresholds stay put initially.** The existing boundaries (`<= 2` red, `<= 3` yellow, `>= 4` green) remain unchanged at launch. Half-steps land naturally between existing buckets. Adjust thresholds later once real half-step data shows where pitchers actually cluster.

**LLM text classification stays on integers.** When the LLM classifies a free-text arm report ("forearm's a little tight"), keep it mapping to whole numbers. Half-steps are only available through direct button/slider input. This avoids inconsistent classification from vague language.

**Historical data needs no migration.** Existing integer values (3, 4, etc.) are valid floats. No backfill required.

---

## What Changes, By Layer

### Telegram Bot (`bot/`)

| Area | What Changes |
|------|-------------|
| **Morning check-in buttons** (`handlers/daily_checkin.py`) | Keyboard expands from 5 buttons to 9, likely across 2 rows |
| **Outing arm feel buttons** (`handlers/post_outing.py`) | Same button expansion for post-outing arm feel |
| **Arm report classification prompt** (`handlers/daily_checkin.py`) | Keep on 1–5 integers — no change needed unless we decide otherwise |
| **Acknowledgment logic** (`handlers/daily_checkin.py`) | `_build_arm_acknowledgment()` threshold checks may need review |
| **Triage rules** (`services/triage.py`) | Review all `<=` / `>=` comparisons — keep thresholds unchanged but confirm no exact-equality checks break |
| **Triage LLM** (`services/triage_llm.py`) | Prompt text says "/5" — works with decimals, but review for integer assumptions |
| **Checkin service** (`services/checkin_service.py`) | Expected soreness threshold (`arm_feel <= 2`) — review |
| **Plan generator** (`services/plan_generator.py`) | Context strings like "Arm feel: 4/5" — works with floats, no change needed |
| **Progression analysis** (`services/progression.py`) | Multiple threshold comparisons for recovery analysis, trend flagging — review each |
| **Context manager** (`services/context_manager.py`) | Display strings — works with floats |

### API (`api/`)

| Area | What Changes |
|------|-------------|
| **Type casts in routes.py** | 4–6 instances of `int(arm_feel)` must become `float(arm_feel)` — these will silently truncate 3.5 → 3 if missed |
| **Trend calculations** (`routes.py`) | Already uses averages — works with floats |
| **Weekly aggregation** (`routes.py`) | Already appends to lists and averages — works with floats |

### Mini-App (`mini-app/`)

| Area | What Changes |
|------|-------------|
| **Coach.jsx** | Outing arm feel buttons: expand `[1,2,3,4,5].map()` to half-steps |
| **PostThrowFeel.jsx** | Post-throw feel buttons: same expansion |
| **Home.jsx** | Arm feel display (the big number) — works with floats, but consider formatting (show "3.5" not "3.500") |
| **WeekStrip.jsx** | Color threshold logic uses exact equality (`=== 3`) — must change to range comparisons |
| **SeasonTimeline.jsx** | Point coloring thresholds — review |
| **TrendInsightChart.jsx** | Grid lines at `[1,2,3,4,5]` — optional: add minor gridlines at 0.5s |
| **Sparkline.jsx** | Renders numeric values — works with floats |
| **SleepScatter.jsx** | If arm feel is an axis — works with floats |

### Database (Supabase)

| Area | What Changes |
|------|-------------|
| **`daily_entries` table** | `arm_feel` column — verify it's numeric/float, not integer |
| **`active_flags` table** | `current_arm_feel` — same check |
| **No data migration needed** | Existing integers are valid floats |

### Data Files (`data/`)

| Area | What Changes |
|------|-------------|
| **Pitcher profiles** (`data/pitchers/*/profile.json`) | Read-only fallback — no migration needed, integers are valid |
| **Daily logs** (`data/pitchers/*/daily_log.json`) | Same — no migration needed |
| **Seed scripts** (`scripts/seed_test_data.py`) | Threshold logic in test data generation — update |

---

## UX Considerations

**Telegram keyboard layout** — 9 buttons across 2 rows:
```
[ 1 ] [ 1.5 ] [ 2 ] [ 2.5 ] [ 3 ]
[ 3.5 ] [ 4 ] [ 4.5 ] [ 5 ]
```
Test on actual phone screen for tap target size.

**Mini-app buttons** — Consider a slider with snap points instead of 9 discrete buttons. Slider gives the same data but feels more natural for "how does your arm feel" than picking from a grid.

**Display formatting** — Show "3.5" not "3.5000". Integers should still display as "4" not "4.0".

---

## Risk Areas

1. **Triage threshold calibration** — Biggest judgment-call area. Start with existing thresholds, adjust with data.
2. **Silent `int()` truncation** — Easy to miss one cast in routes.py. Grep for all `int(` near arm_feel.
3. **Telegram button density** — 9 buttons may feel cramped. Needs real-device testing.
4. **LLM classification consistency** — If extended to half-steps later, "kinda sore" might bounce between 2.5 and 3 across days.

---

## What Does NOT Change

- Scale remains 1–5 (not switching to 1–10)
- Triage logic structure (green/yellow/red) unchanged
- Aggregation, averages, trend charts — all handle floats already
- Historical data — valid as-is
- Arm care / throwing / lifting templates — no arm feel dependency
- WHOOP integration — independent of arm feel scale
