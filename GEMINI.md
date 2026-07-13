# Agent Onboarding — Pitcher Training Intelligence

> This file is read by the Gemini CLI. Codex reads AGENTS.md (same content); Claude Code
> reads CLAUDE.md. All three converge on the same two rules below.

## Rule 1 — Read the briefs first, in this order
1. `/PROJECT_VISION.md` — the light brief: goals, generation constitution, the honest
   problem list, distilled conventions. Start here.
2. `/CLAUDE.md` — the deep reference: architecture, completed phases, gotchas, schema.
3. `/MISSION_CONTROL.html` + `/docs/sprints/` — live status and the primed sprint queue.

## Rule 2 — Update Mission Control when you finish meaningful work
`/MISSION_CONTROL.html` is the shared, human-viewable build-state dashboard. Landon reads it
to see where the project is; every agent (Claude, Codex, Gemini) is responsible for keeping
it truthful.

- Edit ONLY the JSON between `<!--MISSION-DATA-START-->` and `<!--MISSION-DATA-END-->`.
  Never touch the HTML/CSS/JS renderer.
- After landing a feature/fix/decision: bump `meta.updated` + `meta.updated_by`, adjust the
  relevant workstream (`pct`/`status`/`next`), prepend a `log` entry (≤140 chars), and
  add/resolve `risks` and `decisions` as reality changes.
- Validate before committing:
  `python3 -c "import json,re;s=open('MISSION_CONTROL.html').read();json.loads(re.findall(r'DATA-START-->(.*?)<!--MISSION',s,re.S)[-1]);print('OK')"`
- Full protocol (status vocabularies, pruning rules) is in the comment block at the top of
  `MISSION_CONTROL.html`.

## Current division of labor
Check the dashboard's Workstreams section for what's active and what the next step of each
lane is, and the Risks section for landmines (e.g. the engine's LLM path is unproven; a
legacy `programs.py` still runs per check-in). Don't start a new lane without logging it.
