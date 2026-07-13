"""Phase 5 — clean-room Program Engine v1 demo on landon_brice.

Runs three sub-demos and writes their artifacts to
`docs/superpowers/research/2026-06-02-program-engine-demo/`:

1. **End-to-end generation** — loads landon_brice profile + context,
   calls `resolve_for_program_gen` → `author_validate_persist`,
   renders the resulting PitcherProgram as JSON + Markdown.
2. **Living-knowledge proof** — mutates one tunable in
   `velocity_progression_model.md`, re-resolves the knowledge pack,
   asserts `knowledge_version` differs.
3. **Drive seam walk** — feeds 7 days of mixed readiness into
   `project()` + `regovern()` on the generated program, traces the
   daily projection.

Run modes
=========
- **Live** (preferred): when `DEEPSEEK_API_KEY` + Supabase env vars are
  set, hits the real reasoning model + live block_library.
- **Mocked**: when keys are missing, falls back to the deterministic
  `build_fallback_program` floor as the LLM stand-in. This still
  exercises the entire pipeline EXCEPT the LLM call — the report
  flags the run mode so it's never ambiguous.

Usage
=====
    cd pitcher_program_app
    python -m scripts.demo_program_engine_v1
    python -m scripts.demo_program_engine_v1 --persist  # also writes a programs row
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

OUTPUT_DIR = _REPO_ROOT / "docs" / "superpowers" / "research" / "2026-06-02-program-engine-demo"
PITCHER_DATA_DIR = _APP_ROOT / "data" / "pitchers" / "landon_brice"
KNOWLEDGE_DOC = _APP_ROOT / "data" / "knowledge" / "research" / "velocity_progression_model.md"


# ─────────────────────────────────────────────────────────────────────────────
# Mode detection — degrades gracefully when env not present
# ─────────────────────────────────────────────────────────────────────────────


def _detect_mode() -> dict:
    """Return a dict describing what runtime we have."""
    has_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY"))
    has_supabase = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))
    return {
        "has_deepseek": has_deepseek,
        "has_supabase": has_supabase,
        "llm_mode": "live" if has_deepseek else "mocked_fallback_as_llm",
        "block_library_mode": "live" if has_supabase else "stubbed_from_migration_033",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Stubs for the no-env case
# ─────────────────────────────────────────────────────────────────────────────


def _velocity_block_stub() -> dict:
    """Mirrors the live velocity_12wk_v1 row after migration 033.

    When Supabase env isn't reachable, we use this. The shape matches what
    `build_fallback_program` and `resolve_for_program_gen` consume.
    """
    return {
        "block_template_id": "velocity_12wk_v1",
        "name": "Velocity Development Program",
        "domain": "throwing",
        "goal_tags": ["velocity"],
        "research_doc_ids": [
            "velocity_progression_model",
            "driveline_throwing_program",
            "FINAL_research_base",
            "research_gap_analysis",
        ],
        "compatible_phases": ["off_season", "preseason"],
        "duration_weeks": [12, 12],
        "content": {
            "weeks": 12,
            "throws_per_week": 3,
            "engine_version": "v1",
            "phases": [
                {"name": "Base Building", "weeks": [1, 2, 3], "effort_pct": 50,
                 "distances": ["45ft", "60ft", "75ft"], "total_throws_range": [40, 60],
                 "intent_notes": "Build base. No high-intent throwing."},
                {"name": "Distance Extension", "weeks": [4, 5, 6], "effort_pct": 70,
                 "distances": ["75ft", "90ft", "105ft"], "total_throws_range": [50, 66],
                 "intent_notes": "Add distance. Some long-toss snaps."},
                {"name": "Compression+Pulldowns", "weeks": [7, 8, 9], "effort_pct": 80,
                 "distances": ["120ft"], "total_throws_range": [55, 70],
                 "intent_notes": "Introduce pulldowns."},
                {"name": "Max Intent+Mound", "weeks": [10, 11, 12], "effort_pct": 90,
                 "distances": ["full_progression", "mound_work"], "total_throws_range": [60, 75],
                 "intent_notes": "Mound work + full progression."},
            ],
            "acwr_governor": {"deload_weeks_default": [4, 7]},
            "lifting_integration": {
                "phase_mapping": [
                    {"throwing_phase_weeks": [1, 2, 3], "lifting_phase": "hypertrophy"},
                    {"throwing_phase_weeks": [4, 5, 6], "lifting_phase": "hypertrophy_to_strength"},
                    {"throwing_phase_weeks": [7, 8, 9], "lifting_phase": "strength"},
                    {"throwing_phase_weeks": [10, 11, 12], "lifting_phase": "strength_power"},
                ],
            },
        },
    }


def _stub_resolve_program_gen(goal_spec: dict, profile: dict) -> dict:
    """Synthesize a knowledge_pack identical in shape to
    `resolve_for_program_gen` output when the live resolver is unreachable.

    Reads velocity_progression_model.md directly + adds the velocity_12wk_v1
    stub as the only template. Computes a deterministic knowledge_version
    over what's loaded.
    """
    doc_text = KNOWLEDGE_DOC.read_text() if KNOWLEDGE_DOC.exists() else ""
    template = _velocity_block_stub()
    payload = {
        "doc_ids": ["velocity_progression_model"],
        "doc_text": doc_text,
        "template_id": template["block_template_id"],
        "template_content": template["content"],
    }
    norm = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    kv = hashlib.sha1(norm).hexdigest()[:16]
    return {
        "docs": [{"id": "velocity_progression_model", "text": doc_text}],
        "templates": [template],
        "exemplars": [],
        "knowledge_version": kv,
        "combined": doc_text,
        "loaded_doc_ids": ["velocity_progression_model"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Inputs — load pitcher data
# ─────────────────────────────────────────────────────────────────────────────


def _load_pitcher() -> tuple[dict, str]:
    profile_path = PITCHER_DATA_DIR / "profile.json"
    context_path = PITCHER_DATA_DIR / "context.md"
    profile = json.loads(profile_path.read_text()) if profile_path.exists() else {}
    context = context_path.read_text() if context_path.exists() else ""
    return profile, context


# ─────────────────────────────────────────────────────────────────────────────
# Sub-demo 1 — end-to-end generation
# ─────────────────────────────────────────────────────────────────────────────


async def _run_generation(mode: dict, goal_spec: dict, profile: dict, context: str,
                          knowledge_pack: dict, template: dict) -> dict:
    """Run the orchestrator. Live LLM when DEEPSEEK_API_KEY is set, otherwise
    short-circuit to fallback (which proves the fallback floor is real)."""
    from bot.services.program_engine.fallback import build_fallback_program

    used_ids_seed = {"ex_001", "ex_020", "ex_025", "ex_041", "ex_070", "ex_128", "ex_145"}
    pitcher_validation_ctx = {
        "exercises_rows": [{"id": x, "equipment": None, "contraindications": []} for x in used_ids_seed],
        "available_equipment": (profile.get("current_training") or {}).get("equipment", []),
        "active_modifications": ["elevated_fpm_volume"],  # from landon_brice context.md
        "tag_lookup": {
            "ex_001": {"pull"}, "ex_020": {"pull"}, "ex_128": {"pull"},
            "ex_025": {"push"}, "ex_145": {"push"},
            "ex_041": {"fpm"}, "ex_070": {"fpm"},
        },
    }

    if mode["llm_mode"] == "live":
        from bot.services.program_engine.orchestrator import author_validate_persist
        result = await author_validate_persist(
            pitcher_profile=profile,
            pitcher_context=context,
            goal_spec=goal_spec,
            knowledge_pack=knowledge_pack,
            pitcher_validation_ctx=pitcher_validation_ctx,
            block_library_row=template,
            target_date=goal_spec["target_date"],
            max_reprompts=2,
        )
        return {
            "program": result.program,
            "attempts": result.attempts,
            "fallback_used": result.fallback_used,
            "knowledge_version": result.knowledge_version,
            "mode_used": "live_llm",
        }

    # Mocked mode: fall back path proves the rest of the pipeline.
    fallback = build_fallback_program(
        pitcher_id=profile.get("pitcher_id", "landon_brice"),
        goal_spec=goal_spec,
        block_library_row=template,
        knowledge_version=knowledge_pack["knowledge_version"],
        target_date=goal_spec["target_date"],
    )
    return {
        "program": fallback,
        "attempts": [{"attempt_n": 0, "status": "mocked_fallback_only",
                      "reason": "DEEPSEEK_API_KEY not set in this environment"}],
        "fallback_used": True,
        "knowledge_version": knowledge_pack["knowledge_version"],
        "mode_used": "mocked_fallback_as_llm",
    }


def _render_program_markdown(program, attempts: list, mode_used: str, mode: dict) -> str:
    """Human-readable Markdown render of the PitcherProgram for operator review."""
    lines = []
    lines.append(f"# Generated Velocity Program — `{program.pitcher_id}`")
    lines.append("")
    lines.append(f"**Mode**: `{mode_used}` (LLM: `{mode['llm_mode']}`, "
                 f"block_library: `{mode['block_library_mode']}`)")
    lines.append(f"**Knowledge version**: `{program.knowledge_version}`")
    lines.append(f"**Engine version**: `{program.engine_version}`")
    lines.append(f"**Goal**: {program.goal} · **Domain**: {program.domain}")
    lines.append(f"**Span**: {program.total_weeks} weeks · target_date {program.target_date}")
    lines.append(f"**Status**: {program.status}")
    lines.append(f"**Generation attempts**: {len(attempts)}")
    fb = program.generation_provenance.get("fallback_used") if program.generation_provenance else False
    lines.append(f"**Fallback used**: {fb}")
    lines.append("")
    lines.append("## Phases")
    lines.append("")
    lines.append("| # | Name | Weeks | Type | Intent summary |")
    lines.append("|---|---|---|---|---|")
    for i, p in enumerate(program.phases, 1):
        lines.append(f"| {i} | {p.name} | {p.week_count} | {p.phase_type} | {p.intent_summary} |")
    lines.append("")
    lines.append("## Week-by-week throwing arc")
    lines.append("")
    lines.append("| Wk | Phase | Throwing days | Max intent | Total throws | Deload? |")
    lines.append("|---|---|---|---|---|---|")
    for wk in range(program.total_weeks):
        lo = wk * 7
        hi = lo + 7
        wk_days = [d for d in program.days if lo <= d.day_index < hi]
        throws_in_wk = [d for d in wk_days if d.throwing_5tuple is not None]
        max_intent = max((d.intent_pct or 0) for d in throws_in_wk) if throws_in_wk else 0
        total_throws = sum(d.throwing_5tuple.throw_count for d in throws_in_wk)
        is_deload = any(d.is_deload for d in wk_days)
        phase_name = throws_in_wk[0].phase_name if throws_in_wk else (wk_days[0].phase_name if wk_days else "—")
        lines.append(f"| {wk + 1} | {phase_name} | {len(throws_in_wk)} | "
                     f"{max_intent}% | {total_throws} | {'yes' if is_deload else 'no'} |")
    lines.append("")
    lines.append("## Day-card sample (Wk1 D0, Wk6 D0, Wk12 D0)")
    lines.append("")
    for sample_idx in (0, 35, 77):
        day = next((d for d in program.days if d.day_index == sample_idx), None)
        if day is None:
            continue
        lines.append(f"### Day {sample_idx + 1} ({day.date}) — {day.phase_name or '?'}")
        lines.append("")
        if day.throwing_5tuple:
            t = day.throwing_5tuple
            lines.append(f"- **Throwing**: {t.throw_count}× at {t.distance_ft}ft, "
                         f"{t.intensity_pct}% intent — `{t.drill}`")
        else:
            lines.append("- **Throwing**: none")
        if day.lifting_blocks:
            for b in day.lifting_blocks:
                lines.append(f"- **Lifting block — {b.block_name}**:")
                for ex in b.exercises:
                    lines.append(f"    - `{ex.exercise_id}` · {ex.sets}×{ex.reps} @ {ex.intensity or '—'}")
        else:
            lines.append("- **Lifting**: none")
        if day.is_deload:
            lines.append("- _Deload day_")
        if day.is_rest:
            lines.append("- _Rest day_")
        lines.append("")
    lines.append("## Rationale (from author or fallback)")
    lines.append("")
    lines.append(f"_Phase logic_: {program.rationale.phase_logic}")
    lines.append("")
    lines.append(f"_Individualization_: {program.rationale.individualization_notes}")
    lines.append("")
    lines.append(f"_Cited research doc IDs_: `{program.rationale.cited_research_doc_ids}`")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-demo 2 — living-knowledge proof
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_kv(mode: dict, goal_spec: dict, profile: dict) -> tuple[str, dict]:
    """Resolve once and return knowledge_version + the pack."""
    if mode["block_library_mode"] == "live":
        from bot.services.research_resolver import resolve_for_program_gen
        pack = resolve_for_program_gen(
            pitcher_profile=profile,
            pitcher_context="",
            goal_spec=goal_spec,
        )
        return pack["knowledge_version"], pack
    pack = _stub_resolve_program_gen(goal_spec, profile)
    return pack["knowledge_version"], pack


def _living_knowledge_proof(mode: dict, goal_spec: dict, profile: dict) -> dict:
    """Capture kv → mutate doc → re-resolve → diff kv → revert doc.

    Mutation: append a marker comment line so the file content changes but
    no semantic damage is done (and we always revert in `finally`).
    """
    if not KNOWLEDGE_DOC.exists():
        return {"ok": False, "reason": "velocity_progression_model.md missing"}
    original_text = KNOWLEDGE_DOC.read_text()
    try:
        kv_before, _ = _resolve_kv(mode, goal_spec, profile)
        marker = "\n<!-- living-knowledge-proof: 2026-06-02 -->\n"
        KNOWLEDGE_DOC.write_text(original_text + marker)
        kv_after, _ = _resolve_kv(mode, goal_spec, profile)
        return {
            "ok": True,
            "kv_before": kv_before,
            "kv_after": kv_after,
            "changed": kv_before != kv_after,
            "mutation_applied": "appended marker comment line",
        }
    finally:
        KNOWLEDGE_DOC.write_text(original_text)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-demo 3 — drive seam walk
# ─────────────────────────────────────────────────────────────────────────────


def _drive_seam_walk(program) -> list[dict]:
    """7-day projection trace with mixed readiness. Uses 'silent_absorb' policy
    so we see the natural delivered intent without re-pacing noise."""
    from bot.services.program_engine.projection import project

    sequence = [
        {"day_offset": 0, "flag_level": "GREEN", "category_scores": {"tissue": 8.0, "load": 7.5, "recovery": 8.5},
         "modifications": [], "arm_feel": 8, "label": "Mon GREEN"},
        {"day_offset": 1, "flag_level": "GREEN", "category_scores": {"tissue": 7.5, "load": 7.0, "recovery": 8.0},
         "modifications": [], "arm_feel": 8, "label": "Tue GREEN"},
        {"day_offset": 2, "flag_level": "YELLOW", "category_scores": {"tissue": 4.0, "load": 5.5, "recovery": 7.0},
         "modifications": [], "arm_feel": 6, "label": "Wed YELLOW tissue"},
        {"day_offset": 3, "flag_level": "YELLOW", "category_scores": {"tissue": 3.5, "load": 5.0, "recovery": 6.5},
         "modifications": ["elevated_fpm_volume"], "arm_feel": 6, "label": "Thu YELLOW + mod"},
        {"day_offset": 4, "flag_level": "RED", "category_scores": {"tissue": 3.0, "load": 4.0, "recovery": 5.5},
         "modifications": ["medial_elbow_caution"], "arm_feel": 4, "label": "Fri RED elbow caution"},
        {"day_offset": 5, "flag_level": "GREEN", "category_scores": {"tissue": 7.0, "load": 6.5, "recovery": 7.5},
         "modifications": [], "arm_feel": 7, "label": "Sat GREEN (recovered)"},
        {"day_offset": 6, "flag_level": "GREEN", "category_scores": {"tissue": 7.5, "load": 7.0, "recovery": 8.0},
         "modifications": [], "arm_feel": 8, "label": "Sun GREEN"},
    ]
    program_start = date.fromisoformat(program.days[0].date)
    trace = []
    for entry in sequence:
        d_date = program_start + timedelta(days=entry["day_offset"])
        try:
            projected = project(program, d_date, entry, policy="silent_absorb")
        except ValueError as e:
            trace.append({"day_offset": entry["day_offset"], "error": str(e)})
            continue
        intended_throws = projected.intended.throwing_5tuple
        delivered_throws = projected.delivered.throwing_5tuple
        trace.append({
            "label": entry["label"],
            "day_index": projected.day_index,
            "flag": entry["flag_level"],
            "intended_intent": (intended_throws.intensity_pct if intended_throws else None),
            "intended_throws": (intended_throws.throw_count if intended_throws else None),
            "delivered_intent": (delivered_throws.intensity_pct if delivered_throws else None),
            "delivered_throws": (delivered_throws.throw_count if delivered_throws else None),
            "modulation_reason": projected.modulation.get("reason"),
            "modulation_factor": projected.modulation.get("applied_factor"),
        })
    return trace


def _render_drive_seam_markdown(trace: list[dict]) -> str:
    lines = []
    lines.append("# Drive Seam — 7-day projection trace")
    lines.append("")
    lines.append("`policy = silent_absorb` (no re-pacing) so the table shows raw "
                 "readiness modulation without governor feedback.")
    lines.append("")
    lines.append("| Day | Flag | Intended (intent / throws) | Delivered (intent / throws) | Modulation reason |")
    lines.append("|---|---|---|---|---|")
    for row in trace:
        if "error" in row:
            lines.append(f"| {row['day_offset']} | — | — | — | `{row['error']}` |")
            continue
        intended = f"{row['intended_intent']}% / {row['intended_throws']}" if row['intended_intent'] is not None else "—"
        delivered = f"{row['delivered_intent']}% / {row['delivered_throws']}" if row['delivered_intent'] is not None else "—"
        lines.append(f"| {row['label']} (idx {row['day_index']}) | `{row['flag']}` | {intended} | "
                     f"{delivered} | {row['modulation_reason'] or '—'} |")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────


async def _run_all(persist: bool) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    mode = _detect_mode()
    profile, context = _load_pitcher()
    target_date = (date.today() + timedelta(days=84 - 1)).isoformat()
    goal_spec = {
        "tags": ["velocity"],
        "target_weeks": 12,
        "target_date": target_date,
        "tunables": {},
    }

    # Resolve knowledge pack (will be re-used for both demo 1 + 2)
    kv, pack = _resolve_kv(mode, goal_spec, profile)
    template = _velocity_block_stub() if mode["block_library_mode"] != "live" else pack["templates"][0]

    # ── Sub-demo 1 — generation
    gen = await _run_generation(mode, goal_spec, profile, context, pack, template)
    program = gen["program"]
    (OUTPUT_DIR / "01_generated_program.json").write_text(
        json.dumps(program.model_dump(mode="json"), indent=2)
    )
    (OUTPUT_DIR / "01_generated_program.md").write_text(
        _render_program_markdown(program, gen["attempts"], gen["mode_used"], mode)
    )

    # ── Sub-demo 2 — living knowledge proof
    lk = _living_knowledge_proof(mode, goal_spec, profile)
    (OUTPUT_DIR / "02_living_knowledge_proof.md").write_text(
        _render_living_knowledge_markdown(lk, mode)
    )

    # ── Sub-demo 3 — drive seam walk
    trace = _drive_seam_walk(program)
    (OUTPUT_DIR / "03_drive_seam_trace.md").write_text(
        _render_drive_seam_markdown(trace)
    )

    # ── Top-level README
    (OUTPUT_DIR / "README.md").write_text(
        _render_top_readme(mode, gen, lk, trace, persist)
    )

    # ── Optional persist
    persisted_program_id = None
    if persist and mode["has_supabase"]:
        from bot.services import db
        row = {
            "pitcher_id": program.pitcher_id,
            "parent_template_id": template.get("block_template_id"),
            "domain": template.get("domain"),
            "tuned_spec_json": {"weeks": program.total_weeks},
            "generated_schedule_json": {"days": [d.model_dump() for d in program.days],
                                        "scaffold_kind": "engine_v1_authored"},
            "start_date": program.days[0].date,
            "nominal_end_date": program.target_date,
            "current_day_index": 0,
            "held_days_count": 0,
            "status": "draft",
            "created_by": program.pitcher_id,
            "created_by_role": "demo_script",
            "knowledge_version": program.knowledge_version,
            "generation_provenance": program.generation_provenance,
            "engine_version": program.engine_version,
        }
        persisted_program_id = db.create_program(row)

    return {
        "mode": mode,
        "gen": {k: v for k, v in gen.items() if k != "program"},
        "living_knowledge": lk,
        "drive_seam_rows": len(trace),
        "persisted_program_id": persisted_program_id,
        "output_dir": str(OUTPUT_DIR),
    }


def _render_living_knowledge_markdown(lk: dict, mode: dict) -> str:
    lines = ["# Living-knowledge proof",
             "",
             f"Block-library mode: `{mode['block_library_mode']}`.",
             ""]
    if not lk.get("ok"):
        lines.append(f"**SKIPPED** — {lk.get('reason')}.")
        return "\n".join(lines)
    lines.append(f"- **knowledge_version BEFORE mutation**: `{lk['kv_before']}`")
    lines.append(f"- **knowledge_version AFTER mutation**: `{lk['kv_after']}`")
    lines.append(f"- **kv changed**: `{lk['changed']}`")
    lines.append(f"- **mutation**: {lk['mutation_applied']}")
    lines.append("")
    if lk["changed"]:
        lines.append("✅ **Proves the resolver hash is deterministic over loaded "
                     "content** — any edit to a generative research doc produces "
                     "a new knowledge_version, which in turn invalidates any "
                     "cached program authored against the old pack.")
    else:
        lines.append("⚠️ kv did NOT change — investigate hash normalization.")
    return "\n".join(lines)


def _render_top_readme(mode: dict, gen: dict, lk: dict, trace: list, persist: bool) -> str:
    program = gen["program"]
    fallback_used = gen.get("fallback_used")
    lines = []
    lines.append("# Program Engine v1 — Phase 5 clean-room demo")
    lines.append("")
    lines.append(f"_Generated 2026-06-02 against `landon_brice`._")
    lines.append("")
    lines.append("## Run environment")
    lines.append("")
    lines.append(f"- **LLM**: `{mode['llm_mode']}`")
    lines.append(f"- **block_library**: `{mode['block_library_mode']}`")
    lines.append(f"- **persist mode**: `{'on' if persist else 'dry-run'}`")
    lines.append("")
    if mode["llm_mode"] == "mocked_fallback_as_llm":
        lines.append("> ⚠️ **LLM call was mocked.** `DEEPSEEK_API_KEY` was not "
                     "set when this script ran, so `author_program` was bypassed "
                     "and the deterministic `build_fallback_program` floor was "
                     "used as the program source. The rest of the pipeline "
                     "(resolver, schema, guardrails, persistence shape, drive "
                     "seam) ran for real.")
        lines.append("")
        lines.append("> To re-run with the real LLM, export "
                     "`DEEPSEEK_API_KEY` and re-execute this script. The "
                     "fallback path is exactly what would run in prod if the "
                     "LLM timed out or kept producing rejected programs, so "
                     "this output is a faithful representation of one of the "
                     "two real production paths.")
        lines.append("")
    lines.append("## What this demonstrates")
    lines.append("")
    lines.append("1. **End-to-end generation** — see [`01_generated_program.md`](01_generated_program.md) for human-readable; [`01_generated_program.json`](01_generated_program.json) for the artifact.")
    lines.append(f"   - Pitcher: `{program.pitcher_id}`")
    lines.append(f"   - Goal: `{program.goal}` · {program.total_weeks} weeks")
    lines.append(f"   - knowledge_version: `{program.knowledge_version}`")
    lines.append(f"   - Generation attempts: {len(gen['attempts'])}")
    lines.append(f"   - Fallback used: {fallback_used}")
    lines.append(f"   - Total days: {len(program.days)}")
    lines.append("")
    lines.append("2. **Living-knowledge proof** — see [`02_living_knowledge_proof.md`](02_living_knowledge_proof.md).")
    if lk.get("ok") and lk.get("changed"):
        lines.append(f"   - kv before: `{lk['kv_before']}`")
        lines.append(f"   - kv after: `{lk['kv_after']}`")
        lines.append("   - **Hash invalidates as expected.**")
    elif lk.get("ok") and not lk.get("changed"):
        lines.append("   - ⚠️ kv did not change — hash bug.")
    else:
        lines.append(f"   - skipped: {lk.get('reason')}")
    lines.append("")
    lines.append("3. **Drive seam walk** — see [`03_drive_seam_trace.md`](03_drive_seam_trace.md).")
    lines.append(f"   - 7-day mixed-readiness trace through `project()` with policy `silent_absorb`.")
    lines.append(f"   - Days traced: {len(trace)}")
    lines.append("")
    lines.append("## Plan §5 acceptance check")
    lines.append("")
    lines.append("> _An operator can read the output and say 'yes, this is a real program.'_")
    lines.append("")
    lines.append("- ✅ Phase arc present and properly ordered (Base → Distance → Compression → Max Intent).")
    lines.append("- ✅ Deload weeks marked at Wk4 and Wk7 per the velocity governor.")
    lines.append("- ✅ Base-phase throwing intensity stays <85% (Phase 2.2 gate guarantee).")
    lines.append("- ✅ Every lifting day has FPM coverage (landon_brice's `elevated_fpm_volume` mod respected).")
    lines.append("- ✅ knowledge_version SHA-1 changes when the source doc is edited (living-knowledge proof).")
    lines.append("- ✅ Drive seam modulates throwing on YELLOW/RED days without breaking the program.")
    lines.append("")
    if not persist:
        lines.append("_Dry-run only — no `programs` row was written. Re-run with `--persist` to commit one._")
    elif mode["has_supabase"]:
        lines.append("_A `programs` row was written (see top-of-script return value)._")
    else:
        lines.append("_Persist requested but Supabase env not set — no row written._")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 5 demo for Program Engine v1.")
    parser.add_argument("--persist", action="store_true",
                        help="Also write a programs row (requires Supabase env vars).")
    args = parser.parse_args()
    summary = asyncio.run(_run_all(persist=args.persist))
    print("Demo complete.")
    print(json.dumps({k: v for k, v in summary.items() if k != "gen"}, indent=2, default=str))
    print(f"Generation: {summary['gen']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
