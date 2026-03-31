# Pitcher Training Intelligence — Project Vision

> Last updated: 2026-03-31
> Status: Phases 1-8 complete (WHOOP, adoption push, dynamic exercise pool). Next: The Ledger, periodization, exercise progression curves.

## What This Is

A training intelligence system for the UChicago pitching staff. Each pitcher gets personalized daily programs (lifting, arm care, recovery, throwing), evidence-based Q&A, and longitudinal tracking — driven by their individual profile, injury history, biometric context, and conversation history.

The system has three layers:
- **Bot (Telegram)** — The conversational input layer. Morning check-ins, post-outing reports, free-text Q&A. This is where the coaching relationship lives.
- **Mini App (React)** — The value/visibility layer. See your program, track completion, view your trajectory over time. This is where compounding becomes tangible.
- **Intelligence Engine (Python/FastAPI)** — Triage, plan generation, knowledge retrieval, progression analysis. The thinking that connects input to output.

---

## Current State (March 28, 2026)

### What's Built and Working

**Intelligence layer — strong and hardened.** Check-in pipeline saves data before plan generation (no data loss on LLM failure). Partial-save-then-upsert pattern. Template fallback when LLM fails. Rotation day only increments after successful check-in. Extended time-off handling uses lift preference for template selection. Rest day preference enforced at both template and prompt level.

**Notifications — live.** Morning check-ins (pitcher's preferred time), 6pm evening follow-up if unanswered, Sunday 6pm weekly summary with LLM coaching narrative. All scheduled from Supabase, not filesystem.

**Visible compounding — shipped.**
- Arm feel trend chart (4 weeks), sparkline, consistency streak, week dots
- LLM-generated weekly coaching narrative (Sunday, cached, displayed on Home)
- Enhanced progression observations (positive + negative patterns)
- Toast notifications for success/error across the app
- Stale plan detection + banners on Home

**Data layer — durable.** Supabase Postgres. Zero filesystem dependencies for pitcher data. Column whitelist in db.py prevents schema mismatch errors. Chicago timezone throughout.

**All bugs from prior sprint resolved:**
- Check-in pipeline failures (soreness_response column, error handling, rotation drift)
- All 10 timezone bugs fixed (CHICAGO_TZ everywhere)
- Notifications never firing (JSON filesystem → Supabase migration)
- Rest day preference ignored
- Rotation day wrong for extended time-off
- Silent error handling (toast system added)
- CoachFAB badge not rendering
- Dead code removed (ChatBar, NextOutingPicker, TrendChart)

### What's Built Since March 28

- **WHOOP integration** — COMPLETE. Full OAuth pipeline, daily pulls, biometric triage, WhoopCard UI.
- **Adoption push** — COMPLETE. Personalized `/start`, contextual morning notifications, arm feel buttons → full check-in.
- **Dynamic exercise pool** — COMPLETE. 95-exercise library drives selection. Variety across weeks. Injury-aware.
- **Onboarding flow** — COMPLETE. `/start` shows personalized intro + auto check-in prompt.

### What's Not Yet Built

1. **The Ledger** — Modification history visualization. Data exists in `plan_generated.modifications_applied`. Needs frontend timeline on Profile.
2. **Periodization** — No multi-week phases. Exercise pool adds variety but training intent is rotation-day-fixed, not block-progression-aware.
3. **Exercise progression curves** — Volume/intensity trends for key lifts over time.
4. **Coach dashboard** — Staff-facing view of team readiness, flags, trends.
5. **Truncated JSON repair** — LLM sometimes cuts off mid-JSON. `finish_reason` surfaced but no repair logic.

### What's Intentionally Out of Scope

- Mechanical/pitching instruction (coaches own this)
- Medical diagnosis (system flags concerns → tells pitcher to see trainer)
- Supplement recommendations
- Nutrition programming

---

## Sprint History

### Sprint 1: Foundation → Visible Compounding (March 2026)

**Phase 1: Supabase Migration** — COMPLETE
All pitcher data in Supabase. db.py service layer, context_manager.py Supabase-backed, chat_messages table, JSON fallback available.

**Phase 2: State Awareness** — COMPLETE
Cross-platform conversation history, morning status endpoint, check-in state queryable, bot adapts to yesterday's data.

**Phase 3: Coaching Conversation Quality** — COMPLETE
Adaptive check-in flow, smart defaults, context-aware prompts, extended time-off acknowledgment, rest day respected.

**Phase 4: Visible Compounding** — COMPLETE
Arm feel trend chart, consistency streak, LLM weekly narrative, enhanced observations, toast system, stale plan detection.

**Phase 5: Polish & Adoption** — COMPLETE
CLAUDE.md updated, all broken flows fixed, notifications live, dead code removed, error handling improved.

### Sprint 2: Biometric Intelligence + Adoption (March 29-31, 2026)

**Phase 6: WHOOP Integration** — COMPLETE
Full biometric pipeline: per-pitcher OAuth PKCE linking, daily 6am pull, recovery/HRV/sleep/strain into triage + plan gen + weekly narrative. WhoopCard on Home. Smart cache re-pulls when core metrics null.

**Phase 7: Adoption Push** — COMPLETE
Personalized `/start` (injury-aware intro + auto check-in), contextual morning notifications (yesterday's arm feel, WHOOP as conversational sentence), morning arm feel buttons enter full ConversationHandler, human evening follow-up. Fixed `post_init` not firing on Railway (scheduler was silently dead). Handler registration consolidated into single `register_handlers()` function.

**Phase 8: Dynamic Exercise Pool** — COMPLETE
`exercise_pool.py` selects 7-8 lifting exercises from the 95-exercise Supabase library per session. Filters by day focus, rotation_day_usage, injury contraindications, modification_flags. Prefers exercises not used in last 7 days. LLM personalizes prescriptions but cannot hallucinate IDs. Explicit lift preference always honored (overrides rotation day).

**Key fixes shipped:**
- `day_key` NameError in plan gen fallback path
- `timedelta` missing import in morning notification
- `run.py` handler registration mismatch (commands silently missing on Railway)
- Re-check-in button for same-day testing (upserts, no rotation drift)
- Exercise ID validation strips LLM-hallucinated IDs before minimum-count check

---

## Next Sprint: Program Intelligence

### Phase 9: The Ledger (Modification History)
**Goal:** Show each pitcher a timeline of every adaptation the system has made for them. Make the coaching relationship visible.

- Surface `modifications_applied` from daily entries as a timeline on Profile
- Group by category (injury-related, fatigue-based, preference-based)
- Link to the daily plan where each modification was applied

### Phase 10: Periodization Layer
**Goal:** Multi-week training structure. Exercise pool adds variety but not progressive phases.

- Phase/block schema (4-week cycles: hypertrophy → strength → power → deload)
- Training intent auto-advances based on week-in-block
- Cumulative load tracking (28-day volume trends, not just 7-day)
- Auto-deload triggers (cumulative fatigue, sustained low arm feel, WHOOP recovery trends)

### Phase 11: Exercise Progression Curves
**Goal:** Track volume/intensity trends for key lifts over time. Surface to pitcher.

- Completion data already logged (`completed_exercises` in daily_entries)
- Need: prescribed vs. actual tracking, weight progression over weeks
- Mini-app visualization: per-exercise trend lines

---

## Future Considerations (Post-Sprint)

- **Coach dashboard** — Staff-facing view showing team readiness, flag levels, concerning trends
- **Truncated JSON repair** — Salvage partial LLM responses instead of falling back to template
- **Generalization** — Multi-team support, configurable templates, white-label potential
- **Outing data integration** — Trackman/Rapsodo pitch tracking data alongside subjective reports
- **The Trajectory** — Season arc view with recovery fingerprinting and predictive insights

---

## Success Metrics

1. **Data durability** — Zero risk of data loss on redeploy ✅
2. **State coherence** — Bot and mini app share the same view ✅
3. **Check-in quality** — Interaction feels like talking to a coach ✅
4. **Visible progress** — Pitchers reference their trend data unprompted (tracking)
5. **Daily active check-ins** — Target: 6+ of 12 pitchers daily (in progress)
6. **Biometric accuracy** — WHOOP-informed triage replaces self-reported defaults (next)
