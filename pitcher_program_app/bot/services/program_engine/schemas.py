"""Program Engine v1 — canonical content shape (Task 1.1).

The `PitcherProgram` Pydantic models below are the single source of truth for
the program artifact: the LLM is prompted to emit JSON that parses into them
(Task 3.1), guardrails consume them (Tasks 2.1–2.5), the projection seam reads
them (Task 4.1), and the renderer formats them (Task 5.2).

## Additive over `programs.generated_schedule_json`

Migration 020 fixed the existing day shape on `programs`:
    {day_index: int, template_key: str, date: str, anchor_kind?: str}

The v1 engine extends that ADDITIVELY:
    - intent_pct: 0–100, optional (rest days = null)
    - throwing_5tuple: optional ThrowingFiveTuple block
    - lifting_blocks: optional list of LiftingBlock
    - phase_name: str
    - is_deload: bool

Existing readers (program_runtime, program_anchoring, mini-app cards) keep
working because they only touch the original four keys. New readers (the
renderer, the projection, the guardrails) pick up the new keys.

## Schema documentation

See `pitcher_program_app/docs/program_engine_content_schema.md` for the
human-facing schema doc with worked examples.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Atoms
# ─────────────────────────────────────────────────────────────────────────────


class ThrowingFiveTuple(BaseModel):
    """One throwing exposure on one day — matches the golden xlsx schema verbatim.

    The empty `%increase`/`ACWLR` columns on the `Ramp up with Bullpen` xlsx
    operate against this row shape (recon dossier Front 5).
    """

    model_config = ConfigDict(extra="forbid")

    distance_ft: int = Field(..., ge=0, le=400, description="Max distance for this exposure in feet.")
    throw_count: int = Field(..., ge=0, le=200, description="Number of throws.")
    intensity_pct: int = Field(..., ge=0, le=100, description="Average intent, 0–100. Wk1D1 anchor: 50%.")
    drill: str = Field(..., min_length=1, description="Free-text drill name; resolved via exercise_alias only for the throwing-exercise types.")
    note: Optional[str] = Field(default=None, description="Coach cueing prose; not parsed.")


class LiftingExercise(BaseModel):
    """One lifting exercise reference inside a LiftingBlock.

    `exercise_id` is the canonical id from the live `exercises` table (resolved
    via `bot.services.exercise_alias.resolve_alias` at content-author time).
    Phase 2.3 (guardrail #7) re-verifies every id at validation time so any
    drift between generation and the live library fails hard.
    """

    model_config = ConfigDict(extra="forbid")

    exercise_id: str = Field(..., pattern=r"^ex_\d{3}$", description="Canonical id, e.g. ex_004.")
    sets: int = Field(..., ge=1, le=10)
    reps: str = Field(
        ...,
        min_length=1,
        description='Reps as freeform string to accept ranges + RIR notation: "8", "8-10", "3 each leg", "2X10 each direction".',
    )
    intensity: Optional[str] = Field(
        default=None,
        description='Load prescription: "50-75% 1RM", "2RIR", "BW", or null when implicit.',
    )
    rest_s: Optional[int] = Field(default=None, ge=0, le=600)
    superset_group: Optional[str] = Field(
        default=None,
        pattern=r"^[A-Z][0-9]?$",
        description='Optional superset tag like "A1"/"A2"/"B1" — matches The Program.xlsx convention.',
    )
    note: Optional[str] = None


class LiftingBlock(BaseModel):
    """A named lifting block (e.g. "Block 1: Posterior Chain") containing 2–6 exercises.

    Mirrors the periodized_lifting.xlsx schema (Block 1/2/3/4 columns) and is
    additive to the existing `plan_generated.exercise_blocks[*]` shape so the
    legacy DailyCard renderer would still find a `block_name`.
    """

    model_config = ConfigDict(extra="forbid")

    block_name: str = Field(..., min_length=1, max_length=60)
    exercises: list[LiftingExercise] = Field(..., min_length=1, max_length=8)


# ─────────────────────────────────────────────────────────────────────────────
# Day — the projection unit
# ─────────────────────────────────────────────────────────────────────────────


AnchorKind = Literal["calendar_relative", "scheduled_throw_relative", "phase_boundary"]


class Day(BaseModel):
    """One day in the program's projected schedule.

    The four required fields below are the migration-020 contract — readers
    that only know the legacy shape must keep working. All extension fields
    are optional; the renderer / guardrails / projection seam consume them.
    """

    model_config = ConfigDict(extra="forbid")

    # Required (legacy contract; do not break)
    day_index: int = Field(..., ge=0, description="0-based day index within the program.")
    template_key: str = Field(
        ...,
        min_length=1,
        description='Legacy rotation key (e.g. "day_3") OR engine-v1 native key (e.g. "wk2_d3_velo"). Phase 3 uses native keys; legacy keys remain for fallback path.',
    )
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date.")
    anchor_kind: Optional[AnchorKind] = None

    # Engine-v1 additive fields
    phase_name: Optional[str] = Field(default=None, max_length=60)
    intent_pct: Optional[int] = Field(default=None, ge=0, le=100)
    is_deload: bool = False
    is_rest: bool = False
    throwing_5tuple: Optional[ThrowingFiveTuple] = None
    lifting_blocks: list[LiftingBlock] = Field(default_factory=list)
    day_focus: Optional[str] = Field(
        default=None,
        max_length=120,
        description='One-line summary (e.g. "Velocity intent — pulldowns + heavy lift"). Authoritative at write time per Plan 6 A1.5.',
    )
    cues: list[str] = Field(default_factory=list, description="Coach cueing prose to surface in the daily-plan-why sheet.")


# ─────────────────────────────────────────────────────────────────────────────
# Phase
# ─────────────────────────────────────────────────────────────────────────────


class Phase(BaseModel):
    """A multi-week chunk of the program with shared intent.

    Mirrors the `block_library.velocity_12wk_v1.content.phases` shape so
    Phase 1.2's migration can populate Phase content directly without a
    second schema.
    """

    model_config = ConfigDict(extra="forbid")

    phase_id: str = Field(..., min_length=1, max_length=40, description='Stable handle: "base_building", "distance_extension", etc.')
    name: str = Field(..., min_length=1, max_length=60)
    week_count: int = Field(..., ge=1, le=16)
    phase_type: Literal["accumulation", "intensification", "realization", "deload", "transition", "base"] = "accumulation"
    intent_summary: str = Field(..., min_length=1, max_length=240, description='One-paragraph "why this phase exists" for the coach view.')
    intent_kpis: list[str] = Field(
        default_factory=list,
        description='Phase-level KPIs the engine governs against (e.g. "max long-toss dist", "weekly G load").',
    )
    default_training_intent: Optional[str] = None  # consumed by existing ProgramDetail.jsx

    @field_validator("phase_id")
    @classmethod
    def _phase_id_lower_snake(cls, v: str) -> str:
        if v != v.lower() or " " in v:
            raise ValueError(f"phase_id must be lower_snake_case: {v!r}")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Rationale + progression state
# ─────────────────────────────────────────────────────────────────────────────


class Citation(BaseModel):
    """One research-doc citation surfaced by the LLM authoring step.

    Resolved against `data/knowledge/research/*.md` frontmatter at generation
    time; rendered in the "why this program" panel (Plan 6 B3's State C).
    """

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    why: str = Field(..., min_length=1, max_length=240, description="Why this doc informed this program.")


class Rationale(BaseModel):
    """The "why" of the program — coach-readable, persisted on the program row."""

    model_config = ConfigDict(extra="forbid")

    phase_logic: str = Field(..., min_length=1, description="Multi-sentence narrative of the phase progression.")
    individualization_notes: str = Field(
        ...,
        min_length=1,
        description="How the pitcher's profile/injury/baseline shaped this program.",
    )
    cited_research_doc_ids: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list, description="Hydrated from research_resolver.")


class ProgressionState(BaseModel):
    """Where the program currently sits on its arc.

    `current_week`/`current_phase` advance at check-in time on the live path
    (Plan 4 / 6 wiring); the engine writes them at generation but they're
    runtime-mutable.
    """

    model_config = ConfigDict(extra="forbid")

    current_week: int = Field(default=1, ge=1)
    current_phase: Optional[str] = None
    acwr_rolling: Optional[float] = Field(default=None, ge=0.0, le=3.0, description="Most recent rolling ACWR. Null = not enough history.")
    banked_vs_planned: float = Field(default=0.0, description="Cumulative ratio of delivered:prescribed load. 1.0 = on track.")
    gate_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-gate readiness; e.g. {'mound_introduction': 'open'|'pending'|'blocked'}.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Top-level program
# ─────────────────────────────────────────────────────────────────────────────


ProgramDomain = Literal["throwing", "lifting", "unified"]
ProgramStatus = Literal["draft", "active", "archived"]


class PitcherProgram(BaseModel):
    """The generated program artifact.

    Persisted on the `programs` table (L1) with the additive engine_v1 columns
    from migration 034. Everything in this model that's NOT in the migration-020
    legacy contract goes into either `programs.generated_schedule_json.*`
    additive keys (for the per-day shape) or `programs.metadata` JSONB (for
    rationale + progression_state).
    """

    model_config = ConfigDict(extra="forbid")

    # Header
    pitcher_id: str = Field(..., min_length=1)
    goal: str = Field(..., min_length=1, max_length=80, description='e.g. "velocity", "longtoss", "rtt".')
    domain: ProgramDomain = "unified"
    knowledge_version: str = Field(..., min_length=8, description="SHA-1 hex of the resolver-assembled knowledge pack.")
    engine_version: str = "v1"
    generated_at: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", description="ISO-8601.")
    target_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    total_weeks: int = Field(..., ge=1, le=24)
    status: ProgramStatus = "draft"

    # Structure
    phases: list[Phase] = Field(..., min_length=1)
    days: list[Day] = Field(..., min_length=1)

    # Coach-facing
    rationale: Rationale
    progression_state: ProgressionState = Field(default_factory=ProgressionState)

    # Provenance — Phase 3.3 stamps these
    generation_provenance: dict[str, Any] = Field(
        default_factory=dict,
        description="{attempts, repair_log, fallback_used} per Task 3.3.",
    )

    @field_validator("days")
    @classmethod
    def _days_have_unique_indices(cls, v: list[Day]) -> list[Day]:
        seen: set[int] = set()
        for d in v:
            if d.day_index in seen:
                raise ValueError(f"duplicate day_index: {d.day_index}")
            seen.add(d.day_index)
        return v

    @field_validator("phases")
    @classmethod
    def _phase_weeks_sum_matches_total(cls, v: list[Phase]) -> list[Phase]:
        # Light check; full ACWR/load math is Phase 2.1, not schema-level.
        if not v:
            raise ValueError("at least one phase required")
        return v

    def total_phase_weeks(self) -> int:
        """Sum of phase week_count. Should equal total_weeks but the engine may
        permit transition micro-phases that don't add a full week."""
        return sum(p.week_count for p in self.phases)
