# Phase 2: Exercise Swap UI + Model-Aware Pool

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline exercise swapping (Approach D — reason pills + alternatives) to the lifting block, wire it to the pitcher training model so swaps persist as preferences/equipment constraints, and make the exercise pool builder model-aware.

**Architecture:** New backend endpoints (`/alternatives`, `/swap-exercise`) query the exercise library filtered by the pitcher's model (preferences, equipment, injuries). The React `ExerciseSwap` component renders inline in `DailyCard` on each lifting exercise. Fast path ("just swap it") returns pre-computed alternatives instantly; learning path ("no equipment") records constraints. The exercise pool builder gains three new scoring inputs from `pitcher_training_model`.

**Tech Stack:** Python/FastAPI (backend), React (frontend), Supabase (Postgres)

**Spec:** `docs/superpowers/specs/2026-04-01-pitcher-model-plan-quality-design.md` (System 2)

---

### Task 1: Add Alternative-Finding Logic

**Files:**
- Create: `pitcher_program_app/bot/services/exercise_alternatives.py`

This module finds suitable replacement exercises for a given exercise, filtered by pitcher constraints.

- [ ] **Step 1: Create the alternatives module**

```python
"""Find alternative exercises for inline swapping.

Given an exercise and a pitcher's context, returns 3-4 alternatives
from the same category with overlapping muscle groups, filtered by
injury contraindications, equipment constraints, and preferences.
"""

import logging
from bot.services.db import get_exercises, get_training_model, get_daily_entry

logger = logging.getLogger(__name__)

# Cache exercise library in memory (same pattern as exercise_pool.py)
_EXERCISE_CACHE = None


def _load_exercises() -> list:
    global _EXERCISE_CACHE
    if _EXERCISE_CACHE is None:
        _EXERCISE_CACHE = get_exercises()
    return _EXERCISE_CACHE


def find_alternatives(
    exercise_id: str,
    pitcher_id: str,
    date: str,
    rotation_day: int = 0,
    max_results: int = 4,
) -> list[dict]:
    """Find alternative exercises for the given exercise.

    Returns up to max_results alternatives sorted by match quality.
    Each result is a dict with: exercise_id, name, rx, match_reason, tag, youtube_url.
    """
    library = _load_exercises()
    model = get_training_model(pitcher_id)
    preferences = model.get("exercise_preferences") or {}
    equipment = set(model.get("equipment_constraints") or [])

    # Find the source exercise
    source = None
    for ex in library:
        if ex["id"] == exercise_id:
            source = ex
            break
    if not source:
        return []

    source_category = source.get("category", "")
    source_muscles = set(source.get("muscles_primary") or [])
    day_key = f"day_{rotation_day}"

    # Get today's plan to exclude exercises already in it
    today_entry = get_daily_entry(pitcher_id, date) or {}
    plan = today_entry.get("plan_generated") or {}
    today_ids = set()
    for block_key in ("arm_care", "lifting"):
        block = plan.get(block_key) or {}
        for ex in (block.get("exercises") or []):
            today_ids.add(ex.get("exercise_id", ""))
    # Also check exercise_blocks (legacy format)
    for block in (plan.get("exercise_blocks") or []):
        for ex in (block.get("exercises") or []):
            today_ids.add(ex.get("exercise_id", ""))

    # Get recent exercise IDs (last 7 days) for freshness scoring
    from bot.services.db import get_daily_entries
    recent_entries = get_daily_entries(pitcher_id, limit=7)
    recent_ids = set()
    for ent in recent_entries:
        for eid in (ent.get("completed_exercises") or {}).keys():
            recent_ids.add(eid)

    # Get injury areas for contraindication filtering
    from bot.services.context_manager import load_profile
    profile = load_profile(pitcher_id)
    injuries = profile.get("injury_history") or []
    injury_areas = set()
    for inj in injuries:
        area = (inj.get("area") or "").lower()
        if area:
            injury_areas.add(area)

    # Build contraindication set from injury areas
    conditions = set()
    for area in injury_areas:
        if "elbow" in area or "forearm" in area or "ucl" in area:
            conditions.update(["acute_low_back", "ucl_history"])
        if "back" in area or "lumbar" in area:
            conditions.update(["acute_low_back", "lumbar_disk_issues"])
        if "oblique" in area:
            conditions.add("oblique_strain")
        if "shoulder" in area or "labrum" in area:
            conditions.add("shoulder_impingement")

    # Filter candidates
    candidates = []
    for ex in library:
        eid = ex["id"]
        # Must be same category
        if ex.get("category") != source_category:
            continue
        # Skip self
        if eid == exercise_id:
            continue
        # Skip if already in today's plan
        if eid in today_ids:
            continue
        # Skip contraindicated
        contras = set(ex.get("contraindications") or [])
        if contras & conditions:
            continue
        # Skip if rotation day is in avoid list
        usage = ex.get("rotation_day_usage") or {}
        if day_key in (usage.get("avoid") or []):
            continue
        # Skip if equipment constraint matches
        # Equipment constraints are stored as "no_<equipment>" strings
        # We check if the exercise name or tags suggest that equipment
        ex_name_lower = (ex.get("name") or "").lower()
        ex_tags = set(ex.get("tags") or [])
        skip_equip = False
        for constraint in equipment:
            # constraint format: "no_landmine", "no_cable_machine", "no_nordic_bench"
            equip_word = constraint.replace("no_", "").replace("_", " ")
            if equip_word in ex_name_lower:
                skip_equip = True
                break
        if skip_equip:
            continue

        candidates.append(ex)

    # Score candidates
    def score_candidate(ex):
        eid = ex["id"]
        ex_muscles = set(ex.get("muscles_primary") or [])
        muscle_overlap = len(source_muscles & ex_muscles)

        pref = preferences.get(eid, "neutral")
        pref_score = 2 if pref == "prefer" else (1 if pref == "neutral" else 0)

        fresh = eid not in recent_ids
        usage = ex.get("rotation_day_usage") or {}
        recommended = day_key in (usage.get("recommended") or [])

        return (muscle_overlap, pref_score, fresh, recommended)

    candidates.sort(key=score_candidate, reverse=True)
    top = candidates[:max_results]

    # Format results
    results = []
    for i, ex in enumerate(top):
        ex_muscles = set(ex.get("muscles_primary") or [])
        overlap = source_muscles & ex_muscles
        if overlap:
            match_reason = f"Same muscles — {', '.join(sorted(overlap))}"
        else:
            match_reason = f"Same category — {source_category.replace('_', ' ')}"

        # Get prescription for the exercise
        rx_data = ex.get("prescription") or {}
        # Use strength as default intent
        phase = rx_data.get("strength") or rx_data.get("hypertrophy") or rx_data.get("endurance") or {}
        if phase.get("sets") and phase.get("reps"):
            rx = f"{phase['sets']}x{phase['reps']}"
        else:
            rx = "3x8"

        results.append({
            "exercise_id": ex["id"],
            "name": ex.get("name", ex["id"]),
            "rx": rx,
            "match_reason": match_reason,
            "tag": "Best match" if i == 0 else None,
            "youtube_url": ex.get("youtube_url"),
        })

    return results
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/bot/services/exercise_alternatives.py
git commit -m "feat: add exercise alternative-finding logic for swap UI"
```

---

### Task 2: Add Swap and Alternatives API Endpoints

**Files:**
- Modify: `pitcher_program_app/api/routes.py`

- [ ] **Step 1: Add the alternatives endpoint**

At the end of the exercises section in `routes.py` (after the `/exercises/slugs` endpoint, around line 1060), add:

```python
@router.get("/exercises/{exercise_id}/alternatives")
async def get_exercise_alternatives(
    exercise_id: str,
    request: Request,
    pitcher_id: str = Query(...),
    date: str = Query(None),
    reason: str = Query(None),
):
    """Return 3-4 alternative exercises for inline swapping."""
    _require_pitcher_auth(request, pitcher_id)
    from bot.services.exercise_alternatives import find_alternatives
    from bot.services.context_manager import load_profile

    profile = load_profile(pitcher_id)
    flags = profile.get("active_flags") or {}
    rotation_day = flags.get("days_since_outing", 0)

    if not date:
        from datetime import datetime
        from bot.config import CHICAGO_TZ
        date = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")

    alternatives = find_alternatives(
        exercise_id=exercise_id,
        pitcher_id=pitcher_id,
        date=date,
        rotation_day=rotation_day,
    )
    return {"alternatives": alternatives}
```

- [ ] **Step 2: Add the swap endpoint**

After the alternatives endpoint, add:

```python
@router.post("/pitcher/{pitcher_id}/swap-exercise")
async def swap_exercise(pitcher_id: str, request: Request):
    """Swap an exercise in today's plan and record in pitcher model."""
    _require_pitcher_auth(request, pitcher_id)
    body = await request.json()

    date = body.get("date")
    from_id = body.get("from_exercise_id")
    to_id = body.get("to_exercise_id")
    reason = body.get("reason", "preference")
    source = body.get("source", "inline_swap")

    if not all([date, from_id, to_id]):
        raise HTTPException(status_code=400, detail="date, from_exercise_id, to_exercise_id required")

    from bot.services.db import (
        get_daily_entry, upsert_daily_entry, get_training_model,
        upsert_training_model, get_exercise,
    )

    # 1. Update daily_entries — replace exercise in plan_generated
    entry = get_daily_entry(pitcher_id, date)
    if not entry:
        raise HTTPException(status_code=404, detail="No entry for this date")

    plan = entry.get("plan_generated") or {}
    replacement_ex = get_exercise(to_id)
    if not replacement_ex:
        raise HTTPException(status_code=404, detail=f"Exercise {to_id} not found")

    # Find and replace in lifting block
    swapped = False
    lifting = plan.get("lifting") or {}
    for ex in (lifting.get("exercises") or []):
        if ex.get("exercise_id") == from_id:
            ex["exercise_id"] = to_id
            ex["name"] = replacement_ex.get("name", to_id)
            # Get prescription from the replacement exercise
            rx_data = replacement_ex.get("prescription") or {}
            phase = rx_data.get("strength") or rx_data.get("hypertrophy") or rx_data.get("endurance") or {}
            if phase.get("sets") and phase.get("reps"):
                ex["prescribed"] = f"{phase['sets']}x{phase['reps']}"
                if phase.get("intensity"):
                    ex["prescribed"] += f" @ {phase['intensity']}"
            ex["rx"] = ex.get("prescribed", ex.get("rx", "3x8"))
            ex["swapped_from"] = from_id
            swapped = True
            break

    # Also check exercise_blocks (legacy format)
    if not swapped:
        for block in (plan.get("exercise_blocks") or []):
            for ex in (block.get("exercises") or []):
                if ex.get("exercise_id") == from_id:
                    ex["exercise_id"] = to_id
                    ex["name"] = replacement_ex.get("name", to_id)
                    rx_data = replacement_ex.get("prescription") or {}
                    phase = rx_data.get("strength") or rx_data.get("hypertrophy") or rx_data.get("endurance") or {}
                    if phase.get("sets") and phase.get("reps"):
                        ex["prescribed"] = f"{phase['sets']}x{phase['reps']}"
                    ex["rx"] = ex.get("prescribed", ex.get("rx", "3x8"))
                    ex["swapped_from"] = from_id
                    swapped = True
                    break
            if swapped:
                break

    if not swapped:
        raise HTTPException(status_code=404, detail=f"Exercise {from_id} not found in today's plan")

    # Save updated plan
    entry["plan_generated"] = plan
    upsert_daily_entry(pitcher_id, entry)

    # 2. Update pitcher_training_model
    model = get_training_model(pitcher_id)

    # Append to swap history (keep last 30)
    swap_history = model.get("recent_swap_history") or []
    swap_history.append({
        "date": date,
        "from_id": from_id,
        "to_id": to_id,
        "reason": reason,
        "source": source,
    })
    if len(swap_history) > 30:
        swap_history = swap_history[-30:]

    # Update equipment constraints if reason is no_equipment
    equipment = list(model.get("equipment_constraints") or [])
    if reason == "no_equipment":
        from_ex = get_exercise(from_id)
        if from_ex:
            ex_name = (from_ex.get("name") or "").lower().replace(" ", "_")
            constraint = f"no_{ex_name}"
            if constraint not in equipment:
                equipment.append(constraint)

    # Check if exercise has been swapped away 3+ times → dislike
    preferences = dict(model.get("exercise_preferences") or {})
    swap_away_count = sum(1 for s in swap_history if s.get("from_id") == from_id)
    if swap_away_count >= 3 and preferences.get(from_id) != "dislike":
        preferences[from_id] = "dislike"

    # Update weekly state
    week_state = model.get("current_week_state") or {}
    days = week_state.get("days") or []
    today_day = None
    for d in days:
        if d.get("date") == date:
            today_day = d
            break
    if today_day:
        swaps = today_day.get("exercises_swapped") or []
        swaps.append({"from": from_id, "to": to_id})
        today_day["exercises_swapped"] = swaps

    model["recent_swap_history"] = swap_history
    model["equipment_constraints"] = equipment
    model["exercise_preferences"] = preferences
    model["current_week_state"] = week_state
    upsert_training_model(pitcher_id, model)

    return {
        "status": "swapped",
        "from_exercise_id": from_id,
        "to_exercise_id": to_id,
        "updated_plan": plan,
    }
```

- [ ] **Step 3: Commit**

```bash
git add pitcher_program_app/api/routes.py
git commit -m "feat: add /alternatives and /swap-exercise API endpoints"
```

---

### Task 3: Add Frontend API Functions for Swap

**Files:**
- Modify: `pitcher_program_app/mini-app/src/api.js`

- [ ] **Step 1: Add fetchAlternatives and swapExercise functions**

At the end of `api.js` (after the last export), add:

```javascript
/**
 * Fetch alternative exercises for swapping.
 */
export async function fetchAlternatives(pitcherId, exerciseId, date, initData = null) {
  const params = new URLSearchParams({ pitcher_id: pitcherId });
  if (date) params.append('date', date);
  return fetchApi(`/api/exercises/${exerciseId}/alternatives?${params}`, initData);
}

/**
 * Swap an exercise in today's plan.
 */
export async function swapExercise(pitcherId, date, fromExerciseId, toExerciseId, reason, initData = null) {
  return postApi(`/api/pitcher/${pitcherId}/swap-exercise`, {
    date,
    from_exercise_id: fromExerciseId,
    to_exercise_id: toExerciseId,
    reason,
    source: 'inline_swap',
  }, initData);
}
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/mini-app/src/api.js
git commit -m "feat: add fetchAlternatives and swapExercise API functions"
```

---

### Task 4: Create ExerciseSwap Component

**Files:**
- Create: `pitcher_program_app/mini-app/src/components/ExerciseSwap.jsx`

This is the Approach D swap UI — reason pills, alternatives panel, swapped state.

- [ ] **Step 1: Create the component**

```jsx
import { useState, useCallback } from 'react';
import { fetchAlternatives, swapExercise } from '../api';

const REASONS = [
  { key: 'no_equipment', label: 'No equipment' },
  { key: 'doesnt_feel_right', label: "Doesn't feel right" },
  { key: 'preference', label: 'Just swap it' },
];

/**
 * Inline exercise swap UI (Approach D — Coach Hybrid).
 *
 * Fast path: "Just swap it" → instant alternatives, no LLM.
 * Learning path: "No equipment" / "Doesn't feel right" → records reason, shows alternatives.
 *
 * Props:
 *   exerciseId - current exercise ID
 *   exerciseName - display name
 *   pitcherId - pitcher ID
 *   date - plan date (YYYY-MM-DD)
 *   initData - Telegram auth
 *   onSwap(toExercise) - callback after successful swap
 *   onCancel() - callback to close swap UI
 */
export default function ExerciseSwap({ exerciseId, exerciseName, pitcherId, date, initData, onSwap, onCancel }) {
  const [step, setStep] = useState('reasons'); // reasons | loading | alternatives | swapping
  const [alternatives, setAlternatives] = useState([]);
  const [selectedReason, setSelectedReason] = useState(null);
  const [error, setError] = useState(null);

  const handleReason = useCallback(async (reason) => {
    setSelectedReason(reason);
    setStep('loading');
    setError(null);
    try {
      const result = await fetchAlternatives(pitcherId, exerciseId, date, initData);
      setAlternatives(result.alternatives || []);
      setStep('alternatives');
    } catch (err) {
      setError('Failed to load alternatives');
      setStep('reasons');
    }
  }, [pitcherId, exerciseId, date, initData]);

  const handleSwap = useCallback(async (alt) => {
    setStep('swapping');
    try {
      await swapExercise(pitcherId, date, exerciseId, alt.exercise_id, selectedReason, initData);
      onSwap({
        exercise_id: alt.exercise_id,
        name: alt.name,
        rx: alt.rx,
        prescribed: alt.rx,
        youtube_url: alt.youtube_url,
        swapped_from: exerciseId,
        swapped_from_name: exerciseName,
      });
    } catch (err) {
      setError('Swap failed — try again');
      setStep('alternatives');
    }
  }, [pitcherId, date, exerciseId, exerciseName, selectedReason, initData, onSwap]);

  return (
    <div style={{ marginTop: 8, marginLeft: 32 }}>
      {/* Reason pills */}
      {step === 'reasons' && (
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {REASONS.map((r) => (
              <button
                key={r.key}
                onClick={() => handleReason(r.key)}
                style={{
                  padding: '6px 11px', borderRadius: 18,
                  border: '1.5px solid #e4dfd8', background: '#ffffff',
                  fontSize: 12, color: '#6b5f58', cursor: 'pointer',
                  fontWeight: 500,
                }}
              >
                {r.label}
              </button>
            ))}
            <button
              onClick={onCancel}
              style={{
                padding: '6px 11px', borderRadius: 18,
                border: '1.5px solid #e4dfd8', background: 'transparent',
                fontSize: 12, color: '#b0a89e', cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
          {error && <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 6 }}>{error}</div>}
        </div>
      )}

      {/* Loading */}
      {step === 'loading' && (
        <div style={{
          padding: 12, borderRadius: 10, background: '#f5f1eb',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 9,
            border: '2px solid #5c1020', borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: '#6b5f58' }}>Finding alternatives...</span>
        </div>
      )}

      {/* Alternatives list */}
      {step === 'alternatives' && (
        <div style={{
          padding: '10px 12px', borderRadius: 10,
          background: '#f5f1eb', border: '1px solid #e4dfd8',
        }}>
          <div style={{
            fontSize: 11, fontWeight: 600, color: '#b0a89e',
            marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5,
          }}>
            Swap with
          </div>
          {alternatives.length === 0 && (
            <div style={{ fontSize: 12, color: '#6b5f58' }}>No alternatives available</div>
          )}
          {alternatives.map((alt, i) => (
            <div
              key={alt.exercise_id}
              onClick={() => handleSwap(alt)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
                borderBottom: i < alternatives.length - 1 ? '1px solid #e4dfd840' : 'none',
                cursor: 'pointer',
              }}
            >
              <div style={{
                width: 28, height: 28, borderRadius: 14,
                background: i === 0 ? '#1D9E7515' : '#5c102008',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, color: i === 0 ? '#1D9E75' : '#5c1020', flexShrink: 0,
              }}>
                {i === 0 ? '\u2605' : '\u21BB'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: '#2a1a18' }}>{alt.name}</span>
                  {alt.tag && (
                    <span style={{
                      fontSize: 9, padding: '1px 6px', borderRadius: 8,
                      background: '#1D9E7515', color: '#1D9E75', fontWeight: 600,
                    }}>{alt.tag}</span>
                  )}
                </div>
                <div style={{ fontSize: 11, color: '#b0a89e' }}>
                  {alt.rx} &middot; {alt.match_reason}
                </div>
              </div>
            </div>
          ))}
          {error && <div style={{ fontSize: 11, color: '#A32D2D', marginTop: 6 }}>{error}</div>}
          <button
            onClick={onCancel}
            style={{
              marginTop: 8, padding: '4px 10px', borderRadius: 12,
              border: '1px solid #e4dfd8', background: 'transparent',
              fontSize: 11, color: '#b0a89e', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {/* Swapping in progress */}
      {step === 'swapping' && (
        <div style={{
          padding: 12, borderRadius: 10, background: '#f5f1eb',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 9,
            border: '2px solid #5c1020', borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: '#6b5f58' }}>Swapping...</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/ExerciseSwap.jsx
git commit -m "feat: add ExerciseSwap component (Approach D swap UI)"
```

---

### Task 5: Wire Swap UI into DailyCard

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/DailyCard.jsx`

This task adds the swap button to each exercise in the lifting block and handles the swap flow.

- [ ] **Step 1: Add imports and swap state**

At the top of `DailyCard.jsx`, add the import (after existing imports):

```javascript
import ExerciseSwap from './ExerciseSwap';
```

- [ ] **Step 2: Add swap state and handler to the component**

Inside the `DailyCard` function body (after the `handleToggle` callback, around line 40), add:

```javascript
const [swappingExerciseId, setSwappingExerciseId] = useState(null);
const [swappedExercises, setSwappedExercises] = useState({}); // { exerciseId: { from_name, ... } }

const handleSwapComplete = useCallback((exerciseId, newExercise) => {
  setSwappedExercises(prev => ({
    ...prev,
    [newExercise.exercise_id]: {
      swapped_from_name: newExercise.swapped_from_name,
    },
  }));
  setSwappingExerciseId(null);

  // Update local entry data to reflect the swap
  if (entry?.plan_generated?.lifting?.exercises) {
    const exercises = entry.plan_generated.lifting.exercises;
    const idx = exercises.findIndex(e => e.exercise_id === exerciseId);
    if (idx >= 0) {
      exercises[idx] = { ...exercises[idx], ...newExercise };
    }
  }
}, [entry]);
```

- [ ] **Step 3: Modify ExerciseItem to show swap button on lifting exercises**

Find the `ExerciseItem` component inside `DailyCard.jsx` (around line 513). It currently renders each exercise row. You need to:

1. Add a `blockType` prop to `ExerciseItem` and pass it from the parent
2. Add a swap button that appears only for `blockType === 'lifting'` and `!readOnly`
3. Show `ExerciseSwap` component when this exercise is being swapped
4. Show "Swapped" badge and "was: ..." line for swapped exercises

In the `ExerciseItem` component, add after the YouTube link button (around line 583) and before the closing `</div>` of the row:

```jsx
{/* Swap button — lifting only */}
{blockType === 'lifting' && !readOnly && !isCompleted && swappingExerciseId !== exerciseId && (
  <button
    onClick={(e) => { e.stopPropagation(); setSwappingExerciseId(exerciseId); }}
    style={{
      padding: '3px 8px', borderRadius: 12,
      border: '1px solid #e4dfd8', background: '#f5f1eb',
      fontSize: 10, color: '#6b5f58', cursor: 'pointer',
      fontWeight: 500, marginLeft: 4, flexShrink: 0,
    }}
  >
    Swap
  </button>
)}
```

After the exercise row div (but still inside the exercise item container), add the swap UI and swapped indicator:

```jsx
{/* Swap UI */}
{swappingExerciseId === exerciseId && (
  <ExerciseSwap
    exerciseId={exerciseId}
    exerciseName={exercise.name}
    pitcherId={pitcherId}
    date={entry?.date}
    initData={initData}
    onSwap={(newEx) => handleSwapComplete(exerciseId, newEx)}
    onCancel={() => setSwappingExerciseId(null)}
  />
)}

{/* Swapped indicator */}
{swappedExercises[exerciseId] && (
  <div style={{
    marginLeft: 32, marginTop: 2, fontSize: 10,
    color: '#b0a89e', fontStyle: 'italic',
  }}>
    was: {swappedExercises[exerciseId].swapped_from_name}
  </div>
)}
```

- [ ] **Step 4: Pass blockType through the rendering chain**

In the section where `ExerciseItem` is called from within the block rendering logic (inside `SupersetList` or the block map), pass the block type. Find where exercises are rendered for each block (around lines 92-134 where the BLOCKS array is mapped). The `blockType` value should be the block key (`'warmup'`, `'arm_care'`, `'lifting'`, `'throwing'`).

Where `ExerciseItem` is rendered, add `blockType={blockKey}` prop. The exact location depends on the rendering chain — look for where `ExerciseItem` is instantiated and add the prop.

- [ ] **Step 5: Add CSS keyframe for spinner animation**

Add to `mini-app/index.html` or the existing global CSS, the spin animation if not already present:

```css
@keyframes spin {
  to { transform: rotate(360deg); }
}
```

Check if this already exists in the project (search for `@keyframes spin`). If it does, skip this step.

- [ ] **Step 6: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/DailyCard.jsx
git commit -m "feat: wire ExerciseSwap into DailyCard lifting block"
```

---

### Task 6: Make Exercise Pool Model-Aware

**Files:**
- Modify: `pitcher_program_app/bot/services/exercise_pool.py`

The exercise pool builder currently selects exercises based on freshness and rotation day recommendations. It now also needs to filter by equipment constraints and exercise preferences from the pitcher training model.

- [ ] **Step 1: Update `build_exercise_pool` to accept and use the training model**

The function signature at line 67 stays the same (it receives `pitcher_profile` which has `active_flags` attached). We need to load the training model inside the function.

After the line that loads the exercise library (around line 92: `exercises = _load_exercises()`), add:

```python
# Load pitcher training model for preferences and constraints
from bot.services.db import get_training_model
pitcher_id = pitcher_profile.get("pitcher_id", "")
training_model = get_training_model(pitcher_id) if pitcher_id else {}
preferences = training_model.get("exercise_preferences") or {}
equipment_constraints = set(training_model.get("equipment_constraints") or [])
```

- [ ] **Step 2: Add equipment constraint filtering to the eligibility loop**

In the eligibility filter loop (around lines 99-138), after the existing skip checks (contraindications, rotation_day_usage.avoid, modification_flags), add:

```python
# Skip if equipment constraint matches
if equipment_constraints:
    ex_name_lower = (ex.get("name") or "").lower()
    skip_equip = False
    for constraint in equipment_constraints:
        equip_word = constraint.replace("no_", "").replace("_", " ")
        if equip_word in ex_name_lower:
            skip_equip = True
            break
    if skip_equip:
        continue
```

- [ ] **Step 3: Update `_pick` to incorporate preference scoring**

Replace the `_pick` function (lines 217-230) with a version that also scores by preference:

```python
def _pick(pool: list, n: int, recent_ids: set, day_key: str,
          preferences: dict = None) -> list:
    """Pick n exercises from pool, preferring fresh, recommended, and preferred."""
    if not pool or n <= 0:
        return []
    prefs = preferences or {}

    def score(ex):
        usage = ex.get("rotation_day_usage") or {}
        recommended = day_key in (usage.get("recommended") or [])
        fresh = ex["id"] not in recent_ids
        pref = prefs.get(ex["id"], "neutral")
        pref_score = 2 if pref == "prefer" else (1 if pref == "neutral" else 0)
        return (pref_score, fresh, recommended, random.random())

    ranked = sorted(pool, key=score, reverse=True)
    return ranked[:n]
```

- [ ] **Step 4: Pass preferences to all `_pick` calls**

Find all calls to `_pick()` in the file. There should be ~4 calls (for compounds, accessories, core, explosive). Add `preferences=preferences` to each call. For example:

```python
selected_compounds = _pick(compounds, n_compound, recent_exercise_ids, day_key, preferences=preferences)
selected_accessories = _pick(accessories, n_accessory, recent_exercise_ids, day_key, preferences=preferences)
selected_core = _pick(core, n_core, recent_exercise_ids, day_key, preferences=preferences)
```

And for the explosive pick:

```python
selected_explosive = _pick(plyo_candidates, explosive_count, recent_exercise_ids, day_key, preferences=preferences)
```

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/exercise_pool.py
git commit -m "feat: make exercise pool model-aware (preferences + equipment constraints)"
```

---

### Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add swap endpoints to API section**

Find the API Endpoints section in CLAUDE.md. After the Mobility line, add:

```markdown
**Swap:** `GET /exercises/{id}/alternatives`, `POST /pitcher/{id}/swap-exercise`
```

- [ ] **Step 2: Update Exercise Selection section**

Find the "### Exercise Selection" section. Add a bullet at the end:

```markdown
- **Model-aware filtering**: exercise_preferences ("dislike" → deprioritized), equipment_constraints (hard filter), swap history (3+ swaps away → auto-dislike)
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add swap endpoints and model-aware pool to CLAUDE.md"
```

---

## Summary: What Phase 2 Achieves

1. **`/exercises/{id}/alternatives` endpoint** — returns 3-4 smart alternatives filtered by category, muscles, injuries, equipment, preferences
2. **`/swap-exercise` endpoint** — swaps exercise in plan, records in pitcher model (swap history, preferences, equipment constraints)
3. **`ExerciseSwap` component** — Approach D UI with reason pills, alternatives panel, instant swap
4. **Model-aware exercise pool** — `build_exercise_pool` now filters by equipment constraints and scores by preferences
5. **Swap button in DailyCard** — appears on lifting exercises only, with swapped state indicator

## Dependencies on Phase 1

- Reads/writes `pitcher_training_model` (created in Phase 1)
- Uses `get_training_model()` and `upsert_training_model()` from `db.py` (added in Phase 1)
- `exercise_preferences`, `equipment_constraints`, `recent_swap_history` columns (created in Phase 1)
