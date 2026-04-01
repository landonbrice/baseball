# Day Phases: Dynamic Warmup + Post-Throw Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dynamic warmup as the first block in every daily plan, expand post-throw recovery from 2 exercises to an intensity-scaled protocol, and wire post-throw arm feel into the recovery selection.

**Architecture:** The warmup is template-driven (not exercise-pool-driven) — `dynamic_warmup.json` already exists with 7 blocks. The plan generator reads it, picks an activation option based on context, conditionally includes FPM addon, and injects it as a new `warmup` block in the plan output. Post-throw recovery is also template-driven — a new `post_throw_protocols.json` defines 3 tiers (light/medium/full) scaled to throwing intensity. The DailyCard renders both as new collapsible blocks. Post-throw feel (already captured) triggers a protocol recommendation but does not regenerate the plan — the scaled protocol is generated at plan time based on throwing day type.

**Tech Stack:** Python (FastAPI/plan_generator), React (DailyCard.jsx), Supabase (exercises table), JSON templates

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `data/templates/dynamic_warmup.json` | Exists | Warmup template with 7 blocks, 2 activation options, FPM addon |
| `data/templates/post_throw_protocols.json` | **Create** | 3-tier post-throw recovery protocols (light/medium/full) |
| `bot/services/plan_generator.py` | Modify | Load warmup template, pick activation, inject `warmup` block; load post-throw protocol, select tier, replace 2-exercise post-throw |
| `bot/services/checkin_service.py` | Modify | Pass new `warmup` field through to daily_entry storage |
| `bot/services/db.py` | Modify | Add `warmup` to `_DAILY_ENTRY_COLUMNS` whitelist |
| `bot/prompts/plan_generation_structured.md` | Modify | Tell LLM about warmup block existence (so narrative references it) |
| `mini-app/src/components/DailyCard.jsx` | Modify | Add `warmup` to BLOCKS, render warmup block with checklist exercises |
| `api/routes.py` | No change | Plan already flows through existing `/checkin` and `/chat` endpoints |

---

### Task 1: Create Post-Throw Recovery Protocols Template

**Files:**
- Create: `pitcher_program_app/data/templates/post_throw_protocols.json`

This template defines 3 tiers of post-throw recovery scaled to throwing intensity. Exercises use IDs from the existing library where possible. Movement flows (stretches) don't need IDs — they render as checklist items.

- [ ] **Step 1: Create the template file**

```json
{
  "template_id": "post_throw_protocols_v1",
  "description": "Scaled post-throw recovery protocols. Tier selected based on throwing day type intensity.",
  "tier_mapping": {
    "recovery": "light",
    "recovery_short_box": "light",
    "hybrid_b": "medium",
    "hybrid_a": "full",
    "bullpen": "full",
    "game": "full",
    "no_throw": null
  },
  "tiers": {
    "light": {
      "label": "Light Recovery Flush",
      "description": "Minimal flush after low-stress throwing. J-Band cooldown + upward tosses.",
      "estimated_duration_min": 6,
      "exercises": [
        { "exercise_id": "ex_096", "name": "J-Band Forward Fly", "rx": "1x10 (light, slow)", "order": 1 },
        { "exercise_id": "ex_097", "name": "J-Band Reverse Fly", "rx": "1x10 (light, slow)", "order": 2 },
        { "exercise_id": "ex_099", "name": "J-Band External Rotation", "rx": "1x10 (light, slow)", "order": 3 },
        { "exercise_id": "ex_120", "name": "Post-Throw Upward Tosses", "rx": "2x15 (2kg black or 1kg green)", "order": 4 },
        { "exercise_id": "ex_064", "name": "Band Pullaparts", "rx": "2x15", "order": 5 }
      ]
    },
    "medium": {
      "label": "Standard Recovery Flush",
      "description": "Post-throw recovery after moderate throwing. Full J-Band cooldown + posterior shoulder + forearm flush.",
      "estimated_duration_min": 10,
      "exercises": [
        { "exercise_id": "ex_096", "name": "J-Band Forward Fly", "rx": "1x10 (light, slow)", "order": 1 },
        { "exercise_id": "ex_097", "name": "J-Band Reverse Fly", "rx": "1x10 (light, slow)", "order": 2 },
        { "exercise_id": "ex_098", "name": "J-Band Internal Rotation", "rx": "1x10 (light, slow)", "order": 3 },
        { "exercise_id": "ex_099", "name": "J-Band External Rotation", "rx": "1x10 (light, slow)", "order": 4 },
        { "exercise_id": "ex_100", "name": "J-Band Bicep Curl", "rx": "1x10 (light, slow)", "order": 5 },
        { "exercise_id": "ex_101", "name": "J-Band Tricep Extension", "rx": "1x10 (light, slow)", "order": 6 },
        { "exercise_id": "ex_120", "name": "Post-Throw Upward Tosses", "rx": "2x15 (2kg black or 1kg green)", "order": 7 },
        { "exercise_id": "ex_064", "name": "Band Pullaparts", "rx": "2x15", "order": 8 },
        { "exercise_id": "ex_039", "name": "DB Wrist Flexion Curl", "rx": "1x15 (light)", "order": 9 },
        { "exercise_id": "ex_040", "name": "DB Wrist Extension Curl", "rx": "1x15 (light)", "order": 10 },
        { "name": "Sleeper Stretch", "rx": "2x30 sec each side", "order": 11 }
      ]
    },
    "full": {
      "label": "Full Recovery Flush",
      "description": "Complete post-throw recovery after high-intent throwing. Full J-Band cooldown, forearm flush, posterior shoulder, thoracic mobility.",
      "estimated_duration_min": 15,
      "exercises": [
        { "exercise_id": "ex_096", "name": "J-Band Forward Fly", "rx": "1x10 (light, slow)", "order": 1 },
        { "exercise_id": "ex_097", "name": "J-Band Reverse Fly", "rx": "1x10 (light, slow)", "order": 2 },
        { "exercise_id": "ex_098", "name": "J-Band Internal Rotation", "rx": "1x10 (light, slow)", "order": 3 },
        { "exercise_id": "ex_099", "name": "J-Band External Rotation", "rx": "1x10 (light, slow)", "order": 4 },
        { "exercise_id": "ex_100", "name": "J-Band Bicep Curl", "rx": "1x10 (light, slow)", "order": 5 },
        { "exercise_id": "ex_101", "name": "J-Band Tricep Extension", "rx": "1x10 (light, slow)", "order": 6 },
        { "exercise_id": "ex_120", "name": "Post-Throw Upward Tosses", "rx": "2x15 (2kg black or 1kg green)", "order": 7 },
        { "exercise_id": "ex_064", "name": "Band Pullaparts", "rx": "2x20", "order": 8 },
        { "exercise_id": "ex_039", "name": "DB Wrist Flexion Curl", "rx": "2x15 (light)", "order": 9 },
        { "exercise_id": "ex_040", "name": "DB Wrist Extension Curl", "rx": "2x15 (light)", "order": 10 },
        { "exercise_id": "ex_041", "name": "Full Pronation", "rx": "1x15 (light band)", "order": 11 },
        { "name": "Sleeper Stretch", "rx": "2x30 sec each side", "order": 12 },
        { "name": "Cross-Body Posterior Shoulder Stretch", "rx": "2x30 sec each side", "order": 13 },
        { "name": "Thoracic Rotation on Wall", "rx": "1x10 each side", "order": 14 },
        { "name": "Standing Lat Stretch", "rx": "2x20 sec each side", "order": 15 }
      ]
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/data/templates/post_throw_protocols.json
git commit -m "feat: add tiered post-throw recovery protocol templates"
```

---

### Task 2: Plan Generator — Inject Warmup Block

**Files:**
- Modify: `pitcher_program_app/bot/services/plan_generator.py` (around lines 40-100 and 280-320)

The warmup block is loaded from `dynamic_warmup.json`, the activation option is selected, and the FPM addon is conditionally included. The block is added to the plan result as a new `warmup` key.

- [ ] **Step 1: Add warmup builder function**

Add this function near the other `_build_*` helper functions (around line 880, before `_resolve_throwing_phases`):

```python
def _build_warmup_block(pitcher_profile: dict, rotation_day: int, triage_result: dict) -> dict:
    """Build dynamic warmup block from template.

    Selects activation option based on context:
    - Scap focus (Option 2) on upper-body / pull days (day 3, 4)
    - Cuff focus (Option 1) on throwing-heavy or lower-body days (day 0, 1, 2, 5, 6)
    FPM addon auto-included for pitchers with UCL or forearm history.
    """
    try:
        warmup_template = load_template("dynamic_warmup.json")
    except FileNotFoundError:
        logger.warning("dynamic_warmup.json not found")
        return None

    sequence = warmup_template.get("sequence", [])
    if not sequence:
        return None

    # Select activation option
    scap_days = {3, 4}  # Upper body / pull emphasis
    use_scap = rotation_day in scap_days
    activation_label = "Activation — Option 2 (Scap Focus)" if use_scap else "Activation — Option 1 (Cuff Focus)"
    skip_label = "Activation — Option 1 (Cuff Focus)" if use_scap else "Activation — Option 2 (Scap Focus)"

    # Check injury history for FPM addon
    injuries = pitcher_profile.get("injury_history", [])
    injury_areas = {(inj.get("area") or "").lower() for inj in injuries}
    needs_fpm = bool(injury_areas & {"medial_elbow", "ucl", "forearm", "flexor", "pronator"})
    fpm_label = "Additional Band Addons — Flexor Prime (optional)"

    # Build exercise list from selected blocks
    exercises = []
    for block in sequence:
        block_name = block.get("block_name", "")

        # Skip the non-selected activation option
        if block_name == skip_label:
            continue

        # Skip FPM addon if pitcher doesn't need it
        if block_name == fpm_label and not needs_fpm:
            continue

        for ex in block.get("exercises", []):
            exercises.append({
                "exercise_id": ex.get("exercise_id"),
                "name": ex.get("name", ""),
                "rx": ex.get("prescription", ""),
                "block": block_name,
            })

    return {
        "label": "Dynamic Warmup",
        "estimated_duration_min": warmup_template.get("duration_min", 12),
        "activation_type": "scap" if use_scap else "cuff",
        "includes_fpm": needs_fpm,
        "exercises": exercises,
    }
```

- [ ] **Step 2: Call warmup builder in `generate_plan()`**

In `generate_plan()`, after loading the arm care template (around line 94), add:

```python
    # Build dynamic warmup block
    warmup_block = _build_warmup_block(profile, rotation_day, triage_result)
```

- [ ] **Step 3: Add `warmup` to all plan return paths**

There are 3 return statements in `generate_plan()`:

**Return 1 — LLM failure fallback (around line 225):** Add `"warmup": warmup_block,`

**Return 2 — Successful LLM parse (around line 288):** Add `"warmup": warmup_block,`

**Return 3 — Unparseable LLM fallback (around line 309):** Add `"warmup": warmup_block,`

Each return dict gets the same line added:
```python
"warmup": warmup_block,
```

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/plan_generator.py
git commit -m "feat: inject dynamic warmup block into plan generation"
```

---

### Task 3: Plan Generator — Replace Post-Throw with Tiered Protocol

**Files:**
- Modify: `pitcher_program_app/bot/services/plan_generator.py` (the `_build_throwing_plan` and `_resolve_throwing_phases` functions)

Replace the hardcoded 2-exercise post-throw in `jband_routine_v1.post_throw` with the appropriate tier from `post_throw_protocols.json`.

- [ ] **Step 1: Add post-throw protocol loader**

Add a function near the other builders:

```python
def _select_post_throw_protocol(throwing_day_type: str) -> dict | None:
    """Select tiered post-throw recovery protocol based on throwing intensity.

    Returns a phase dict with exercises, or None for no_throw days.
    """
    try:
        protocols = load_template("post_throw_protocols.json")
    except FileNotFoundError:
        logger.warning("post_throw_protocols.json not found")
        return None

    tier_mapping = protocols.get("tier_mapping", {})
    tier_key = tier_mapping.get(throwing_day_type)
    if not tier_key:
        return None

    tier = protocols["tiers"].get(tier_key)
    if not tier:
        return None

    return {
        "phase_name": f"Post-Throw Recovery — {tier['label']}",
        "description": tier["description"],
        "exercises": [
            {
                "exercise_id": ex.get("exercise_id"),
                "name": ex["name"],
                "rx": ex["rx"],
                "order": ex.get("order"),
            }
            for ex in tier["exercises"]
        ],
    }
```

- [ ] **Step 2: Modify `_resolve_throwing_phases` to use tiered post-throw**

In `_resolve_throwing_phases()` (line ~886), find where it resolves `jband_routine_v1.post_throw` template_ref phases. Change the logic so that when a phase has `template_ref` containing `post_throw`, it substitutes the tiered protocol instead.

Current logic resolves `template_ref: "jband_routine_v1.post_throw"` → the 2-exercise block from `jband_routine.json`.

New logic: when we encounter a post_throw template_ref, call `_select_post_throw_protocol(day_type_key)` and use its exercises instead. The `day_type_key` needs to be passed into `_resolve_throwing_phases`.

Updated signature:
```python
def _resolve_throwing_phases(day_type_template: dict, jband: dict, day_type_key: str = "") -> list:
```

In the loop where `template_ref` is resolved, add:
```python
if "post_throw" in template_ref:
    tiered = _select_post_throw_protocol(day_type_key)
    if tiered:
        resolved_phases.append(tiered)
        continue
    # Fall through to original jband post_throw if protocol not found
```

- [ ] **Step 3: Update the call site for `_resolve_throwing_phases`**

In `_build_throwing_plan()` where `_resolve_throwing_phases` is called, pass the `day_type_key`:
```python
phases = _resolve_throwing_phases(day_type_template, jband, day_type_key=day_type_key)
```

- [ ] **Step 4: Commit**

```bash
git add pitcher_program_app/bot/services/plan_generator.py
git commit -m "feat: replace static post-throw with tiered recovery protocol"
```

---

### Task 4: Storage Layer — Pass Warmup Through to Daily Entry

**Files:**
- Modify: `pitcher_program_app/bot/services/db.py` (line ~116)
- Modify: `pitcher_program_app/bot/services/checkin_service.py` (line ~205)

- [ ] **Step 1: Add `warmup` to db.py column whitelist**

In `db.py`, add `"warmup"` to `_DAILY_ENTRY_COLUMNS`:

```python
_DAILY_ENTRY_COLUMNS = {
    "pitcher_id", "date", "rotation_day", "days_since_outing", "pre_training",
    "plan_narrative", "morning_brief", "plan_generated", "actual_logged",
    "bot_observations", "arm_care", "lifting", "throwing", "warmup", "notes",
    "completed_exercises", "soreness_response",
}
```

- [ ] **Step 2: Add Supabase column**

Run this migration via the Supabase MCP:
```sql
ALTER TABLE daily_entries ADD COLUMN IF NOT EXISTS warmup jsonb;
```

- [ ] **Step 3: Add `warmup` to checkin_service.py entry dict**

In `checkin_service.py` `process_checkin()`, in the entry dict (around line 205), add after the `throwing` line:

```python
"warmup": plan_result.get("warmup") if plan_result else None,
```

- [ ] **Step 4: Also handle the API /chat checkin path**

In `api/routes.py`, find the `/chat` endpoint's checkin handler where it builds the entry similarly. Add the same `warmup` passthrough. Search for where `plan_result.get("throwing")` is used in the chat endpoint and add `warmup` alongside it.

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/bot/services/db.py pitcher_program_app/bot/services/checkin_service.py pitcher_program_app/api/routes.py
git commit -m "feat: add warmup column to daily_entries and pass through storage"
```

---

### Task 5: LLM Prompt — Reference Warmup Block

**Files:**
- Modify: `pitcher_program_app/bot/prompts/plan_generation_structured.md`

The LLM doesn't generate the warmup — it's template-driven. But the LLM should know it exists so the `morning_brief` and `notes` can reference it naturally (e.g., "Start with your dynamic warmup, then...").

- [ ] **Step 1: Add warmup context to the prompt**

After the "Exercise Volume Requirements" section (around line 111), add:

```markdown
### Dynamic Warmup (System-Generated)
- A dynamic warmup block is automatically prepended to every plan. You do NOT generate it.
- The warmup includes: movement prep, lunge complex, dynamic movement, ground mobility, and an activation block (cuff or scap focus).
- Reference it naturally in the morning_brief or notes (e.g., "Start with your dynamic warmup, then hit arm care...").
- Do NOT include warmup exercises in arm_care or lifting blocks — they are separate.
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/bot/prompts/plan_generation_structured.md
git commit -m "feat: add warmup reference to LLM plan generation prompt"
```

---

### Task 6: DailyCard — Render Warmup Block

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/DailyCard.jsx`

Add `warmup` as the first block in the BLOCKS array. The warmup block renders like arm_care/lifting — a collapsible card with checkable exercises. Exercises without `exercise_id` render as checklist items (no library resolution needed).

- [ ] **Step 1: Add warmup to BLOCKS constant**

Change the BLOCKS array (line 17):

```javascript
const BLOCKS = [
  { key: 'warmup', emoji: '\uD83D\uDD25', label: 'Dynamic Warmup' },
  { key: 'arm_care', emoji: '\uD83D\uDCAA', label: 'Arm Care' },
  { key: 'lifting', emoji: '\uD83C\uDFCB\uFE0F', label: 'Lifting' },
  { key: 'throwing', emoji: '\u26BE', label: 'Throwing' },
];
```

- [ ] **Step 2: Add warmup to blockData resolution**

In the `blockData` object (line 61), add:

```javascript
const blockData = {
  warmup: entry.warmup || plan_generated?.warmup,
  arm_care: entry.arm_care || plan_generated?.arm_care,
  lifting: entry.lifting || plan_generated?.lifting,
  throwing: resolveThrowingData(),
};
```

- [ ] **Step 3: Handle exercises without exercise_id in ExerciseItem**

In the `ExerciseItem` component, exercises without an `exercise_id` (movement flows from the warmup) need to still render with a name and rx. The current code already handles this — `resolveExercise` returns null, and `exerciseObj` falls back to `{ name: ex.name }`. But the completion toggle needs a stable key.

In `SupersetList`, update the key and ID handling for exercises without `exercise_id`:

```javascript
const exId = ex.exercise_id || `flow_${ex.name?.replace(/\s+/g, '_').toLowerCase()}`;
```

Use `exId` where `ex.exercise_id` is currently used for:
- `completed[exId]`
- `onToggle(exId, ...)`
- `expandedWhy[exId]`
- The `key` prop

- [ ] **Step 4: Group warmup exercises by block name**

The warmup data has a `block` field on each exercise (e.g., "Get Moving", "Lunge Complex"). Render these as sub-headers within the warmup card, similar to how throwing phases work.

In `ExerciseBlock`, when `blockKey === 'warmup'`, group exercises by their `block` field and render group labels:

```javascript
// Inside ExerciseBlock, after resolving allEx:
if (blockKey === 'warmup' && allEx.length > 0) {
  // Group by block field
  const groups = [];
  let currentBlock = null;
  for (const ex of allEx) {
    if (ex.block !== currentBlock) {
      currentBlock = ex.block;
      groups.push({ label: currentBlock, exercises: [ex] });
    } else {
      groups[groups.length - 1].exercises.push(ex);
    }
  }

  return (
    <div style={{ background: 'var(--color-white)', borderRadius: 12, overflow: 'hidden' }}>
      {/* Header — same as other blocks */}
      <div style={{ padding: '10px 14px', borderBottom: '0.5px solid var(--color-cream-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14 }}>{emoji}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-ink-primary)' }}>{label}</span>
            {duration && <span style={{ fontSize: 10, color: 'var(--color-ink-faint)' }}>{duration} min</span>}
          </div>
          <span style={{ fontSize: 11, color: doneCount === allEx.length && allEx.length > 0 ? 'var(--color-flag-green)' : 'var(--color-ink-muted)', fontWeight: 600 }}>
            {doneCount}/{allEx.length}
          </span>
        </div>
      </div>
      {/* Grouped exercise list */}
      <div style={{ padding: '4px 14px 10px' }}>
        {groups.map((g, gi) => (
          <div key={gi}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--color-ink-muted)', textTransform: 'uppercase', letterSpacing: 0.5, padding: '6px 0 2px' }}>
              {g.label}
            </div>
            <SupersetList
              exercises={g.exercises}
              exerciseMap={exerciseMap}
              slugMap={slugMap}
              completed={completed}
              onToggle={onToggle}
              expandedWhy={expandedWhy}
              onToggleWhy={onToggleWhy}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/DailyCard.jsx
git commit -m "feat: render warmup block with grouped exercises in DailyCard"
```

---

### Task 7: DailyCard — Enhanced Post-Throw Phase Rendering

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/DailyCard.jsx`

The post-throw phase now has 5-15 exercises instead of 2. It's already rendered as a collapsible phase in the ThrowingBlock. The only change needed: the post-throw phase should be visually distinguished (it's the "what to do after you're done throwing" phase, not part of the throwing itself).

- [ ] **Step 1: Style the post-throw phase differently**

In the `ThrowingBlock` phase rendering loop (around line 258), detect the post-throw phase and give it a distinct background:

```javascript
const isPostThrow = (phase.phase_name || '').toLowerCase().includes('post-throw');
```

In the phase header div, conditionally apply a green-tinted background:
```javascript
background: isPostThrow ? 'rgba(29, 158, 117, 0.06)' : 'var(--color-cream-bg)',
```

- [ ] **Step 2: Commit**

```bash
git add pitcher_program_app/mini-app/src/components/DailyCard.jsx
git commit -m "feat: visually distinguish post-throw recovery phase"
```

---

### Task 8: Verify End-to-End

- [ ] **Step 1: Build the mini-app**

```bash
cd pitcher_program_app/mini-app && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 2: Verify template loading**

```bash
cd pitcher_program_app && python -c "
import json
with open('data/templates/post_throw_protocols.json') as f:
    p = json.load(f)
    print(f'Tiers: {list(p[\"tiers\"].keys())}')
    for k, v in p['tiers'].items():
        print(f'  {k}: {len(v[\"exercises\"])} exercises, ~{v[\"estimated_duration_min\"]} min')
with open('data/templates/dynamic_warmup.json') as f:
    w = json.load(f)
    print(f'Warmup blocks: {len(w[\"sequence\"])}')
    total_ex = sum(len(b.get(\"exercises\", [])) for b in w['sequence'])
    print(f'Total warmup exercises: {total_ex}')
"
```

Expected:
```
Tiers: ['light', 'medium', 'full']
  light: 5 exercises, ~6 min
  medium: 11 exercises, ~10 min
  full: 15 exercises, ~15 min
Warmup blocks: 7
Total warmup exercises: 26
```

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: day phases — dynamic warmup + tiered post-throw recovery"
git push origin main
```

---

## What Changes Where (Summary)

### Backend (Plan Generation)
- `generate_plan()` now returns a `warmup` dict alongside `arm_care`, `lifting`, `throwing`
- Warmup is template-driven: `dynamic_warmup.json` → activation pick (cuff vs scap) + conditional FPM
- Post-throw recovery is template-driven: `post_throw_protocols.json` → tier selected by throwing day type
- The LLM does NOT generate warmup or post-throw exercises — it only references them in narrative

### Storage
- New `warmup` JSONB column on `daily_entries` table
- `_DAILY_ENTRY_COLUMNS` whitelist updated
- `checkin_service.py` passes `warmup` through to storage

### Frontend (DailyCard)
- New `warmup` block renders first (before arm care)
- Warmup exercises grouped by block name (Get Moving, Lunge Complex, etc.)
- Exercises without `exercise_id` render as checklist items with generated keys
- Post-throw phase has green-tinted background to distinguish from throwing
- Post-throw now has 5-15 exercises instead of 2

### No Changes
- No new API endpoints
- No changes to the check-in flow or triage
- PostThrowFeel component unchanged (already captures arm feel after throwing)
- Exercise pool (`exercise_pool.py`) unchanged — warmup and post-throw are template-driven
