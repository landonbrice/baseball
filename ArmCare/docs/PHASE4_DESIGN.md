# Phase 4: Visible Compounding — Mini App Redesign

> Implementation spec for Claude Code. Context: Phases 1-3 shipped (Supabase, state awareness,
> coaching conversation quality). This phase redesigns the mini app to surface the intelligence
> layer's value and drive daily adoption.
>
> **Reference mockup:** `home-mockup.jsx` in repo root — interactive React component showing
> the target home page. Use this as the visual reference for all component work.

## Design Principles

1. **Plan-first, not dashboard-first.** The app opens to today's program — what to do, not charts.
2. **"Why" is the day-1 hook.** Every pitcher sees why their plan is personalized before they have any historical data.
3. **Compounding becomes visible over time.** Week strip, trends, and insights grow more meaningful with each check-in.
4. **Staff visibility creates accountability.** Pitchers see who's checked in and where everyone is in rotation.

## CRITICAL: Preserve Existing Design Language

The mini app has an established visual identity. **Do NOT introduce new colors, dark themes, or conflicting styles.** All new components must use the existing design system:

**Color Palette (CSS custom properties in `index.css`):**
- `--color-maroon: #5c1020` — primary brand color, headers, active states, buttons
- `--color-maroon-mid: #7a1a2e` — secondary maroon
- `--color-rose-blush: #e8a0aa` — accent highlights, outing markers
- `--color-cream-bg: #f5f1eb` — main page background
- `--color-white: #ffffff` — card backgrounds
- `--color-cream-border: #e4dfd8` — dividers, card borders
- `--color-cream-subtle: #ddd8d0` — subtle borders, inactive states
- `--color-ink-primary: #2a1a18` — headings, primary text
- `--color-ink-secondary: #6b5f58` — body text, descriptions
- `--color-ink-muted: #b0a89e` — labels, hints
- `--color-ink-faint: #c5bfb8` — very subtle text, placeholders
- `--color-flag-green: #1D9E75` — healthy status, completed checkboxes
- `--color-flag-yellow: #BA7517` — caution status, partial completion
- `--color-flag-red: #A32D2D` — alert status, priority exercises

**Existing Patterns to Maintain:**
- White rounded cards (12px border-radius) on cream background
- Maroon header band at top of page
- 0.5px solid cream-border dividers inside cards
- FlagBadge: inline pill with 12% opacity background + colored text
- Exercise checkboxes: circular, 1.5px border, green fill when complete
- FPM (priority) exercises: maroon border + red "FPM" badge
- Uppercase 8-10px labels with letter-spacing for section headers
- Fixed bottom nav (56px) with dot indicator for active tab
- Unicode icons in nav: ⌂ ◉ ▥ ▦ ◯
- System fonts: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto

---

## Home Page Modifications

> This is NOT a rebuild. It's targeted additions to the existing Home.jsx structure.
> The current home page already has: maroon header, WeekStrip, session status, brief card,
> tabbed DailyCard, TrendChart, InsightsCard. We're enhancing these and adding new sections.

### Information Hierarchy (top to bottom)

**1. Header Band (ENHANCE existing)**
- Current: pitcher name, arm feel number, rotation day
- **Add:** Role subtitle under name: "UChicago Baseball · **Starter**"
  - "UChicago Baseball" in rose-blush color
  - Role ("Starter" / "Reliever") in white, fontWeight 600 — contrasts for pop
- **Add:** 15-day arm feel sparkline next to the big arm feel number
  - Rose-blush line, small dots, larger dots on outing days
  - Gives immediate trend context without scrolling
- **Add:** Footer row inside header with:
  - Next outing: "Next start: **Friday**" (bold the day)
  - Total session info: "10 exercises · ~75 min"
  - Consistency streak: 7 dots (green = done, gray = pending) + "4 day streak" text
  - Separated from header content by `0.5px solid rgba(255,255,255,0.12)` border

**2. Session Progress Bar (NEW — after header, before week strip)**
- White card with maroon progress bar
- Shows: "Session Progress" label + "2/10 exercises" + percentage
- Bar fills with maroon, switches to flag-green at 100%
- Large bold percentage number on right side
- This replaces/enhances the existing session status bar

**3. Week Strip (ENHANCE existing)**
- Current: 7-day strip with day numbers, outing diamonds, flag dots
- **Add:** Arm feel color on the status dot: green (4-5), yellow (3), red (1-2), gray (no data)
  - Today's dot is white (on maroon background)
- **Add:** Legend below the strip with clear dot explanations:
  - 🟢 Complete · 🟡 Partial · ⚪ Upcoming · 🔷 Outing
  - Separated by 0.5px cream-border top border
- Keep existing: maroon background on today, rose-blush outing diamonds

**4. Today's Plan (ENHANCE existing DailyCard)**
- Current: tabbed interface (arm_care, lifting, throwing, notes) with exercise lists
- **Add block-level reasoning:** italic one-liner under each tab's header
  - "Standard arm care — day 3, building back toward Friday's start"
  - Stored in plan JSON as `block_reasoning` field
- **Enhance exercise rows:**
  - **Full prescription on its own line** below exercise name: "3×12 · 8lb · RPE 7" or "2×15 each direction · RPE 6-7"
    - Currently prescription may be inline — move to dedicated line, fontSize 11, ink-muted color
  - **Add ⓘ button** on each exercise row (right side, next to video ▶ button)
    - Tap expands per-exercise "why" reasoning below the row
    - Expanded state: cream-bg box with rose-blush left border (2px)
    - Text: 11px, ink-secondary, line-height 1.6
    - References pitcher's specific injury history, not generic descriptions
  - Keep existing: circular checkboxes, FPM badges, ▶ video links, superset grouping
- **Add "tap ⓘ for why" hint:** small text above the plan section, right-aligned, ink-faint

**5. Check-in Banner (NEW — conditional, between header and session progress)**
- ONLY renders if pitcher hasn't checked in today
- Rose-blush border (1.5px) + light maroon background (maroon at 5% opacity)
- Left side: "Morning check-in" heading + "Check in to get today's personalized plan" subtext
- Right side: maroon "Check In" button
- If already checked in: this section doesn't render at all
- If no plan yet: show last active program template for today's rotation day, grayed out (opacity 0.45)

**6. Weekly Insight Card (ENHANCE existing InsightsCard)**
- Current: text-only with emoji categories
- **Add arm feel trend chart ABOVE the text:**
  - Hand-rolled SVG (matches existing TrendChart approach — no charting libraries)
  - 4-week view: X-axis = Wk 1, Wk 2, Wk 3, Wk 4
  - Y-axis = arm feel scale 1-5 with gridlines
  - Maroon line for weekly average, circle data points with value labels above
  - Rose-blush semi-transparent band showing high-low range each week
  - Chart sits in cream-bg rounded box with 8px padding
  - Legend below chart: maroon line = "Avg", rose band = "High-Low range"
- Text insight below chart (existing behavior, LLM-generated)
- Section header: 📈 "Weekly Insight" in maroon uppercase
- Only renders after 5+ days of check-in data

**7. Staff Pulse (NEW — after insight card)**
- Collapsible white card
- Header row (always visible): ⚾ "PITCHING STAFF" label + "7/11" count + expand arrow (▸/▾)
- Collapsed: just the header with count
- Expanded: full pitcher list in single column
  - Each row: green/gray status dot + name + role pill (SP/RP in cream-bg, 9px) + rotation info (right-aligned, ink-faint)
  - Rows separated by 0.5px cream-bg lines
  - Names in ink-primary when checked in, ink-muted when not
- **Privacy:** shows check-in status + rotation position only. NOT arm feel, flag level, or plan details.

**8. Floating Coach Button (NEW)**
- Fixed position: bottom 68px, right 16px (above bottom nav)
- 48px maroon circle with ◉ icon in white
- Box shadow: `0 2px 12px rgba(92,16,32,0.3)`
- Navigates to Coach page
- Remove Coach (◉) from bottom nav — save space, Coach is now the FAB
- Bottom nav becomes 4 items: Home (⌂), Program (▥), History (▦), Profile (◯)

---

## Plans Page → "My Program" Page

### Rename & Restructure

**Old:** "Saved Plans" with active/inactive toggle buttons
**New:** "My Program" — rename in nav label and page header

### Layout

**1. Current Program (top)**
- The currently active plan, displayed in FULL (every exercise, every day)
- Organized by rotation day: Day 1, Day 2, ... Day 7 (for starters) or by day type (for relievers)
- Each day expandable to show full exercise list with video links
- "Why" layer available here too (expandable per-exercise reasoning)
- Single action button: "Talk to Coach about changes" → navigates to Coach with program context
- Do NOT show activate/deactivate toggles. There is one active program. Period.

**2. Program History (below)**
- Chronological list of past programs, newest first
- Each entry shows:
  - Date range: "March 1 - March 15"
  - What changed: "Switched from heavy arm care to light — forearm tightness resolved"
  - The change reason should come from the plan's metadata or the modification that triggered the switch
- Tapping a past program expands to show its full detail
- Action: "Reactivate this program" → switches current program (with confirmation)

### What to Remove
- Active/inactive toggle UI
- Any concept of multiple simultaneously "active" plans
- Deactivate buttons on plan cards

---

## Exercise "Why" Data Source

The "why" reasoning per exercise needs to come from somewhere. Here's the implementation approach:

**Block-level "why":**
- Already generated by the plan_generator — the triage result contains flag_level, modifications, reasoning
- Store the block-level reasoning in the daily_entry when the plan is generated
- Add a `block_reasoning` field to each block in the plan JSON:
  ```json
  {
    "arm_care": {
      "reasoning": "Light and protective — day 2 post-outing, protecting recovery",
      "exercises": [...]
    }
  }
  ```

**Per-exercise "why":**
- Combine two data sources:
  1. Exercise library metadata: `pitching_relevance` field (already exists)
  2. Pitcher's injury profile: match exercise `muscles_primary` and `contraindications` against `injury_history`
- Generate per-exercise reasoning via LLM at plan generation time (add to plan_generator.py)
- Store in the exercise entry within the plan:
  ```json
  {
    "exercise_id": "pronator_curls",
    "name": "Pronator Curls",
    "sets": 3,
    "reps": 12,
    "prescription": "3×12 · 8lb · RPE 7",
    "why": "Strengthens the flexor-pronator mass — your primary UCL dynamic stabilizer. Included because of your 2024 forearm/UCL episode."
  }
  ```
- **Prescription format:** always include full detail on one line — sets×reps · weight/band · RPE range
  - Examples: "3×15 · light band · RPE 5", "2×10 each direction · RPE 7-8", "3×40yd · heavy · RPE 8"
- This is a one-time cost at plan generation, not computed on every page load
- If LLM generation fails, fall back to exercise library `pitching_relevance` field as the "why"

---

## New API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/staff/pulse` | Team check-in status + rotation info + role for all pitchers |
| `GET /api/pitcher/{id}/trend` | 4-week arm feel trend data (weekly avg, high, low) for insight chart |
| (modify) `POST /checkin` response | Include block_reasoning and per-exercise "why" in generated plan |
| (modify) `GET /plans` response | Include full exercise details for current program |

### Staff Pulse Response Shape
```json
{
  "checked_in_count": 7,
  "total_pitchers": 11,
  "pitchers": [
    { "first_name": "Preston", "checked_in": true, "rotation_info": "Day 3", "role": "SP" },
    { "first_name": "Wade", "checked_in": true, "rotation_info": "Available", "role": "RP" }
  ]
}
```

### Trend Response Shape
```json
{
  "weeks": [
    { "week_label": "Wk 1", "start_date": "2026-03-02", "avg": 3.4, "high": 4, "low": 2, "days_logged": 5 },
    { "week_label": "Wk 2", "start_date": "2026-03-09", "avg": 3.6, "high": 4, "low": 3, "days_logged": 6 }
  ],
  "sparkline": [3, 3, 4, 3, 2, 3, 4, 4, 3, 4, 3, 2, 3, 4, 4],
  "outing_day_indices": [4, 11],
  "current_streak": 4
}
```

---

## Component Changes (mini-app/src/)

### New Components
- `StaffPulse.jsx` — Collapsible team check-in card with names, roles, rotation info
- `ExerciseWhy.jsx` — Expandable per-exercise reasoning (cream-bg, rose-blush left border)
- `BlockReasoning.jsx` — Italic one-liner below block headers
- `SessionProgress.jsx` — Progress bar card (maroon fill, percentage, exercise count)
- `StreakBadge.jsx` — 7 dots + streak count (for header)
- `Sparkline.jsx` — Mini SVG trend line (for header, rose-blush colored)
- `TrendInsightChart.jsx` — 4-week arm feel chart with range band (for insight card, hand-rolled SVG)
- `ProgramHistory.jsx` — Timeline of past programs with change reasons
- `CoachFAB.jsx` — Floating action button for Coach access

### Modified Components
- `Home.jsx` — Add new sections per hierarchy, restructure information order
- `DailyCard.jsx` — Add block reasoning, full prescription line, ⓘ button with expandable "why"
- `WeekStrip.jsx` — Add arm feel colors on dots, add legend section
- `FlagBadge.jsx` — No changes needed (already correct)
- `TrendChart.jsx` — Existing 28-day chart can stay on a detail view; new 4-week summary chart for home
- `InsightsCard.jsx` — Add TrendInsightChart above existing text content
- `Layout.jsx` — Remove Coach from bottom nav (4 items now), add CoachFAB

### Renamed
- Plans page → "My Program" (nav label + page header + route)

### Removed
- Active/deactivate toggle buttons on plan cards
- Coach icon from bottom nav (replaced by FAB)

---

## Cold Start Handling

For pitchers with < 5 days of data:
- **Week strip:** shows available data (even 1-2 dots) — don't hide it
- **Session progress:** always visible (shows today's plan if it exists)
- **Sparkline in header:** hidden if < 3 data points (not enough for a line)
- **Streak badge:** shows even "1 day streak" — every start matters
- **Weekly insight card + chart:** hidden (not enough data for meaningful trend)
- **Staff pulse:** always visible (team data exists even if individual data is sparse)
- **"Why" layer:** always available (derived from profile + injury history, not usage history)
- **Block reasoning:** always available (derived from triage, not history)

The "why" layer is the cold start solution. Day 1, zero history, a pitcher opens the app and sees "pronator curls — included because of your UCL history" and thinks "this system actually knows me." That's the hook before any compounding data exists.

---

## Success Criteria

- Pitcher opens app → sees today's plan within 1 second (no loading spinner blocking content)
- Header shows name, role ("UChicago Baseball · Starter"), arm feel + sparkline, streak
- Session progress bar reflects real-time exercise completion
- Every exercise block has a visible one-liner "why" (italic, below header)
- Every exercise shows full prescription ("3×12 · 8lb · RPE 7") and has expandable ⓘ reasoning on tap
- Week strip has arm feel color dots + clear legend
- Insight card shows 4-week trend chart above LLM-generated text (after 5+ days data)
- Staff pulse shows real-time check-in status with names, roles, rotation info
- Coach FAB is accessible from any scroll position
- Plans page shows "My Program" with current program in full, no activate/deactivate toggles
- All new components use existing maroon/cream/rose-blush color palette — zero visual conflicts
