# Pitcher Training Intelligence — Project Vision

> Last updated: 2026-03-28
> Status: Phases 1-5 complete. Adoption push in progress. Next: WHOOP integration + The Ledger.

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

### What's Not Yet Built

1. **WHOOP integration** — Schema fields exist but no API calls. Sleep defaults to self-reported. This is the next major feature. See WHOOP_INTEGRATION_PLAN.md.
2. **The Ledger** — Modification history visualization. Data exists in `plan_generated.modifications_applied` on every daily entry. Needs frontend to surface it.
3. **Exercise progression curves** — Volume/intensity trends for key lifts over time.
4. **Coach dashboard** — Staff-facing view of team readiness, flags, trends.
5. **Onboarding flow** — Guided first-time experience (pieces exist but aren't connected).

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

---

## Next Sprint: Biometric Intelligence + The Ledger

### Phase 6: WHOOP Integration
See `WHOOP_INTEGRATION_PLAN.md` for full technical plan.

**Goal:** Replace self-reported sleep with real biometric data. Make triage accuracy based on actual recovery scores, HRV, and sleep quality.

### Phase 7: The Ledger (Modification History)
**Goal:** Show each pitcher a timeline of every adaptation the system has made for them. Make the coaching relationship visible.

- Surface `modifications_applied` from daily entries as a timeline on Profile or Home
- Group by category (injury-related, fatigue-based, preference-based)
- Link to the daily plan where each modification was applied

### Phase 8: Adoption Push
**Goal:** Get 6+ of 12 pitchers checking in daily.

- In-person onboarding with 2-3 pitchers
- Morning notification → check-in → plan → evening follow-up loop
- Weekly narrative as the "payoff" visible every Sunday

---

## Future Considerations (Post-Sprint)

- **Coach dashboard** — Staff-facing view showing team readiness, flag levels, concerning trends
- **Exercise progression curves** — Volume/intensity trends for key lifts over time
- **Generalization** — Multi-team support, configurable templates, white-label potential
- **Push notifications** — Mini app push for morning check-in reminder
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
