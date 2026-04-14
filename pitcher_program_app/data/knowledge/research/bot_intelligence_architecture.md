---
id: bot_intelligence_architecture
title: Bot Intelligence Architecture Reference
keywords: [bot, architecture, context, retrieval, knowledge, pitcher, profile, log, conversation, memory, system]
type: system_reference
applies_to:
  - any
triggers:
  - reference
phase: any
priority: reference
contexts:
  - coach_chat
summary: >
  Documents the bot's context growth and knowledge retrieval architecture — per-pitcher
  context files, conversation persistence, and how intelligence accumulates over time.
---

# Bot Intelligence Architecture: Context Growth + Knowledge Retrieval

---

## LAYER 1: PER-PITCHER CONTEXT FILES (Growing .md or .json)

Each pitcher gets a living context file that grows over time. This is NOT just a log of workouts — it's an evolving understanding of the individual.

### What Goes Into the Context File Automatically
The bot appends to this after every interaction:

```
# Pitcher Context: [Name]
## Last Updated: 2026-03-14

### Profile (from intake — relatively static)
- Role: Starter, 7-day rotation
- Throws: R
- Injury history: Medial elbow tightness March 2024, resolved via dry needling + pronator work
- Known limitations: Limited left hip IR (~28°)
- Current maxes: Trap bar DL 315, Front squat 225

### Active Status (updated daily/per-interaction)
- Days since last outing: 3
- Last outing: 78 pitches, arm feel 7/10 post-game
- Current arm feel: 4
- Current flag level: GREEN
- WHOOP recovery today: 62%
- Active modifications: Elevated FPM volume (UCL history flag)

### Longitudinal Patterns (bot-generated observations)
- Arm feel trend: Averaging 3.8 over last 4 outings (stable)
- Arm feel typically dips to 3 on Day 1, recovers to 4 by Day 2
- Grip strength subjectively lower after 80+ pitch outings
- Responds well to cross-body stretch for posterior tightness
- Has asked about compression sleeves 2x — tends to feel "tight" on Day 1
- Front squat progressing well: 205 → 215 → 225 over 6 weeks
- Sleep averaging 6.8 hours (below 8hr target — flagged)

### Interaction Memory (key Q&A the bot should remember)
- 2026-02-20: Asked about ice after outing. Bot explained evidence against, 
  pitcher was skeptical. Follow up if he asks again.
- 2026-03-01: Reported "weird tingling in pinky" after bullpen. Bot flagged 
  potential ulnar nerve irritation, recommended reducing ulnar deviation 
  volume and monitoring. Resolved by 03-05.
- 2026-03-10: Asked about adding weighted ball work. Bot advised against 
  adding during competitive season without coach input.
```

### Why .md Over .json for Context Files
The context file needs to be readable by the LLM as natural language, not just structured data. A .md file with sections is:
- Easy for the LLM to parse and reason against
- Human-readable if a coach or trainer wants to review it
- Flexible enough to capture unstructured observations
- Searchable with simple text matching

The daily LOG stays as .json (structured data for trend analysis). 
The CONTEXT FILE is .md (narrative understanding for reasoning).

### What Triggers Context Updates
- Every post-outing check-in → update active status + log arm feel trend
- Every completed workout → update progression data
- Every Q&A interaction → if the question reveals something about the pitcher 
  (injury concern, new symptom, preference), add to context
- Weekly bot self-review → generate "longitudinal patterns" section based on 
  accumulated log data

---

## LAYER 2: KNOWLEDGE BASE RETRIEVAL (for answering questions)

When a pitcher asks a question, the bot follows this decision tree:

```
PITCHER ASKS QUESTION
        │
        ▼
 Is the answer in the research base?
        │
   ┌────┴────┐
   YES       NO
   │         │
   ▼         ▼
 Retrieve    Is this a common baseball 
 + apply     S&C question?
 to their    │
 context     ├── YES → Search web (Cressey, 
             │         Reinold, Driveline, PubMed)
             │         → Evaluate evidence quality
             │         → Answer the pitcher
             │         → IF high-quality finding:
             │            add to knowledge base
             │
             ├── NO (personal/medical) →
             │   "That's outside what I can 
             │    advise on. Talk to [trainer]."
             │
             └── UNCLEAR → Ask clarifying question
```

### The Knowledge Base Has Three Tiers

**Tier 1: Core Research Base (FINAL_research_base.md)**
- Curated, evidence-graded, reviewed by you
- This is the "textbook" the bot trusts completely
- Bot cites this tier with high confidence
- Updated manually when new evidence emerges

**Tier 2: Extended Knowledge (accumulated from web searches)**
- When the bot searches for an answer and finds good evidence
- Stored in a separate `extended_knowledge.md` file
- Tagged with source, date retrieved, and evidence quality
- Bot cites this tier with moderate confidence + source attribution
- Example: pitcher asks about blood flow restriction for biceps tendinopathy → 
  bot searches, finds a 2025 study, answers, and stores the finding

**Tier 3: Anecdotal / Practice-Based (from interactions)**
- Observations from the pitcher's own experience
- "Last time I used a lax ball on my forearm before throwing, my arm felt great"
- Stored in the pitcher's context file, not the global knowledge base
- Bot uses this for personalization but NOT as evidence for other pitchers
- Example: "Based on your experience, lax ball work before throwing has 
  correlated with better arm feel for you. Want to include that today?"

---

## LAYER 3: REAL-TIME QUESTION HANDLING (the actual conversation flow)

### Example 1: "Should I wear a compression sleeve?"

```
Bot internal process:
1. Check research base → Find: limited evidence on compression sleeves 
   for acute recovery, some evidence for warmth/proprioceptive benefit
2. Check pitcher context → This pitcher has UCL history, reports tightness 
   on Day 1 post-outing, has asked about this before
3. Check current status → Day 1 post-outing, arm feel 3

Bot response:
"There's not strong evidence that compression sleeves accelerate tissue 
recovery, but some pitchers find the warmth and proprioceptive feedback 
helpful for that Day 1 tightness you tend to get. Given your history with 
medial elbow stuff, wearing one for comfort is fine — just don't use it as 
a substitute for your FPM work and cross-body stretch today. If the 
tightness is sharper than usual or localized to a specific spot, let me 
know and we should talk about whether to flag it."

Bot context update:
→ Append to interaction memory: "2026-03-14: Asked about compression 
   sleeve again (3rd time). Arm feel 3, Day 1. Provided evidence-based 
   response. Monitor if tightness pattern is worsening."
→ Longitudinal note: "Pitcher consistently reports tightness on Day 1. 
   Pattern is stable but worth monitoring if arm feel dips below 3."
```

### Example 2: "My arm doesn't feel great, what about doing a lax ball right now?"

```
Bot internal process:
1. This is a REAL-TIME symptom + intervention question
2. Check current status → What day of rotation? What's arm feel? Any flags?
3. Check research base → Soft tissue mobilization: moderate evidence for 
   acute symptom relief, no evidence of harm when done correctly on forearm/
   posterior shoulder. Avoid directly on medial elbow if UCL history.
4. Check pitcher context → UCL history. Where does it not feel great?

Bot response:
"Before I suggest anything — where specifically doesn't it feel great? 
Is it the usual Day 1 general tightness, or is it more localized?"

[Pitcher responds: "Mostly forearm, general tightness"]

"Lax ball on the forearm flexors is fine for that — work the belly of the 
muscle, not directly on the medial elbow. Spend 60-90 seconds per side, 
moderate pressure. Follow it with some light wrist flexion/extension 
(2x10, no weight) to restore ROM. 

One thing to keep in mind — you had that medial elbow episode last year, 
so if the tightness is more toward the inside of the elbow rather than 
the muscle belly, skip the lax ball and just do light band work + cross-body 
stretch instead. And let me know how it feels after."

Bot context update:
→ Log: arm feel concern on Day 1, forearm tightness (general, not localized)
→ Recommended: lax ball forearm + light wrist flexion/extension
→ Flag for follow-up: check arm feel tomorrow
```

### Example 3: "I saw a video about isometric mid-range holds for tendon health — should I add those?"

```
Bot internal process:
1. Check research base → Isometrics for tendon health: not currently in base
2. This is a KNOWLEDGE GAP → trigger web search
3. Search: "isometric training tendon health baseball pitchers"
4. Find: moderate evidence for isometric loading in tendinopathy management 
   (Rio et al., Cook & Purdam tendon continuum model). Not pitcher-specific 
   but mechanistically sound.
5. Evaluate: relevant to this pitcher? Check context → no current tendon issues

Bot response:
"Good find — there's moderate evidence that isometric holds can help with 
tendon pain management and potentially tendon adaptation. The research is 
mostly on patellar and Achilles tendons, not pitcher-specific, but the 
mechanism applies. 

That said, you don't have an active tendon issue right now, so adding 
isometrics as a preventive measure is reasonable but low-priority compared 
to your current FPM and scap work. If you want to experiment, try 
3x30-second isometric wrist flexion holds at ~70% effort on Day 3 and 
Day 5 and see how it feels. We can track it."

Bot knowledge update:
→ Add to extended_knowledge.md:
  Topic: Isometric training for tendon health
  Evidence level: Moderate (non-pitcher-specific)
  Key source: Rio et al. 2015, Cook & Purdam tendon continuum
  Application: Potential adjunct for forearm/wrist tendon capacity
  Date retrieved: 2026-03-14

Bot context update:
→ Pitcher showed interest in isometric holds. If added, track response.
```

---

## IMPLEMENTATION NOTES

### File Structure Addition to Project
```
/data
  /pitchers
    pitcher_001.json          ← Structured profile (intake data, maxes, etc.)
    pitcher_001_context.md    ← Growing narrative context (NEW)
    pitcher_001_log.json      ← Daily structured log entries
  /knowledge
    FINAL_research_base.md    ← Tier 1: Curated core knowledge
    extended_knowledge.md     ← Tier 2: Bot-discovered knowledge (NEW)
    exercise_library.json     ← Exercise database
```

### Context Growth Rules
1. **Append, don't overwrite.** The context file is additive. Old observations 
   stay (they're useful for pattern detection).
2. **Summarize periodically.** Every 2 weeks, the bot generates a "summary 
   update" that condenses the longitudinal patterns section to prevent the 
   file from growing unbounded.
3. **Flag, don't diagnose.** When the bot notices a concerning pattern 
   (arm feel declining over 3 weeks, sleep consistently below 7 hours), 
   it flags it to the pitcher AND notes it in context. It does NOT diagnose.
4. **Separate personal anecdotes from evidence.** If a pitcher says "ice 
   works for me," the bot stores that as a personal preference in THEIR 
   context file, not in the global knowledge base. It can accommodate the 
   preference while noting the evidence.

### Web Search Rules for Knowledge Expansion
1. Only search when the question can't be answered from Tier 1 or Tier 2
2. Prioritize: PubMed, Cressey blog, Driveline blog, Reinold blog, ASMI
3. Avoid: random forum posts, supplement company blogs, unattributed content
4. Always evaluate evidence quality before storing
5. Never add to Tier 1 automatically — Tier 2 only, with source and date
6. If a Tier 2 finding gets referenced 3+ times, flag it for manual review 
   and potential promotion to Tier 1

### What the Bot Should NEVER Do
- Provide definitive medical advice ("you definitely should/shouldn't...")
- Use one pitcher's personal data to advise another pitcher
