"""Program Engine v1 — LLM-forward generation, deterministic guardrails, living knowledge.

See docs/superpowers/specs/2026-05-31-program-engine-design.md for the design,
docs/superpowers/plans/2026-06-01-program-engine-v1.md for the implementation plan.

Public surface lives in submodules:
- schemas.py — PitcherProgram, Day, Phase, Throwing5Tuple, LiftingBlock (Task 1.1)
- author.py — LLM-forward authoring (Task 3.1)
- guardrails.py — validate → repair → reject orchestrator (Task 2.4)
- load_math.py — ACWR governor + load formulas (Task 2.1)
- structural_invariants.py — deload, monotonic, pull:push, FPM (Task 2.2)
- content_invariants.py — equipment, contraindications, exercise IDs (Task 2.3)
- fallback.py — deterministic safe-fallback floor (Task 2.5)
- projection.py — project(program, date, readiness) (Task 4.1)
- governor.py — regovern(program, signal, policy) (Task 4.2)
- render.py — text/json/markdown artifact renderer (Task 5.2)

Wired in flag-off by default behind PROGRAM_ENGINE_V1; see feature_flag.py.
"""
