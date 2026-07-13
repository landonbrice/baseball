"""Program Engine v1 — LLM-forward program authoring (Task 3.1).

Public surface:
- `author_program(pitcher_profile, pitcher_context, goal_spec, knowledge_pack,
                  *, seed=None, previous_violations=None) -> PitcherProgram`

The brilliant-coach prompt lives at `bot/prompts/program_engine_author.md`.
The LLM is invoked through `bot.services.llm.call_llm_reasoning` (deepseek-reasoner,
120s timeout — L11 latency-tolerant).

On LLM timeout, parse failure, or schema validation error, raises
`GenerationFailure`. The orchestrator (Task 3.3) catches that and falls
back to the deterministic floor.

**Does NOT validate against guardrails** — that's the orchestrator's job.
This function's contract is: produce a schema-valid PitcherProgram OR raise.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from bot.services.llm import call_llm_reasoning, load_prompt
from bot.services.program_engine.schemas import PitcherProgram

logger = logging.getLogger(__name__)


class GenerationFailure(Exception):
    """Raised when LLM authoring cannot produce a schema-valid PitcherProgram.

    Carries a `reason` string the orchestrator surfaces in generation_provenance.
    """

    def __init__(self, reason: str, *, detail: Optional[str] = None):
        super().__init__(reason if not detail else f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


_SYSTEM_PROMPT = (
    "You are a brilliant pitching coach authoring complete multi-week training "
    "programs as JSON. Emit ONLY valid JSON matching the PitcherProgram schema — "
    "no markdown, no prose, no fences. Emit COMPACT JSON: no indentation, no "
    "newlines between tokens. Keep drill/note strings terse. Your output budget "
    "is 65,536 tokens — a complete 9-week program with full lifting detail on "
    "every day fits comfortably, so write every single day as a complete Day "
    "object. NEVER summarize, abbreviate, or skip days; NEVER emit placeholder "
    "text, comments, or meta-commentary inside arrays — one non-object element "
    "in `days` invalidates the entire program. The downstream guardrails "
    "enforce the invariants; you focus on the program design."
)


def _format_profile_summary(profile: dict) -> str:
    """Compact profile summary for the prompt — keep the LLM context small.

    Pulls the fields the brilliant-coach prompt cares about: id, role, physical
    profile, injury_history summary, training preferences. JSONB nested dicts
    are flattened lightly; lists are bulleted.
    """
    if not profile:
        return "(no profile available)"
    lines: list[str] = []
    for key in ("pitcher_id", "name", "role", "throwing_hand"):
        v = profile.get(key)
        if v:
            lines.append(f"- {key}: {v}")
    phys = profile.get("physical_profile") or profile.get("physical") or {}
    if isinstance(phys, dict) and phys:
        lines.append("- physical_profile:")
        for k, v in phys.items():
            lines.append(f"    - {k}: {v}")
    training = profile.get("training") or {}
    if isinstance(training, dict) and training:
        lines.append("- training:")
        for k, v in training.items():
            if isinstance(v, (str, int, float, bool)):
                lines.append(f"    - {k}: {v}")
    injuries = profile.get("injury_history") or []
    if injuries:
        lines.append("- injury_history:")
        for inj in injuries[:10]:
            if isinstance(inj, dict):
                area = inj.get("area") or inj.get("injury_area") or "?"
                sev = inj.get("severity") or "?"
                status = inj.get("status") or "?"
                lines.append(f"    - {area} (severity={sev}, status={status})")
    return "\n".join(lines) if lines else "(profile fields empty)"


def _format_previous_violations(previous_violations: Optional[list]) -> str:
    """Format guardrail violations for the re-prompt path.

    `previous_violations` is a list of `GuardrailViolation` dataclasses OR dicts
    (both shapes accepted because callers may serialize before passing in).
    """
    if not previous_violations:
        return "(none — this is the first attempt)"
    lines: list[str] = []
    for v in previous_violations:
        if hasattr(v, "kind"):
            kind = getattr(v, "kind", "?")
            where = getattr(v, "where", {}) or {}
            actual = getattr(v, "actual", None)
            expected = getattr(v, "expected", None)
            hint = getattr(v, "repair_hint", None)
        else:
            kind = (v or {}).get("kind", "?")
            where = (v or {}).get("where", {})
            actual = (v or {}).get("actual")
            expected = (v or {}).get("expected")
            hint = (v or {}).get("repair_hint")
        line = f"- {kind} at {where}"
        if expected is not None:
            line += f" (expected={expected}"
            if actual is not None:
                line += f", actual={actual}"
            line += ")"
        if hint:
            line += f" — hint: {hint}"
        lines.append(line)
    return "\n".join(lines)


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences the LLM may have added despite instruction."""
    if not text:
        return text
    text = text.strip()
    # Common patterns: ```json\n...\n```  OR  ```\n...\n```
    m = re.match(r"^```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


_EXERCISE_MENU_CACHE: Optional[str] = None


def _exercise_menu() -> str:
    """Compact `ex_NNN  Name` lines for the full canonical exercise library.

    The prompt forbids invented IDs, so the model MUST be shown the real ones
    (first live run fabricated ex_002-style IDs — unknowable without this).
    Live `exercises` table preferred; snapshot fixture fallback keeps the
    author functional offline. Cached per process (library changes are rare
    and already require a redeploy for the pool cache anyway).
    """
    global _EXERCISE_MENU_CACHE
    if _EXERCISE_MENU_CACHE is not None:
        return _EXERCISE_MENU_CACHE
    rows: list[dict] = []
    try:
        from bot.services.db import get_client

        resp = get_client().table("exercises").select("id, name, tags, category").order("id").execute()
        rows = resp.data or []
    except Exception as e:  # offline / no creds — fall back to the snapshot
        logger.warning("author: live exercise menu unavailable (%s); using snapshot", e)
    if not rows:
        snapshot = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "exercises_snapshot.json"
        try:
            rows = json.loads(snapshot.read_text())
        except Exception:
            rows = []
    from bot.services.program_engine.structural_invariants import derive_structural_tags

    def _line(r: dict) -> str:
        tags = derive_structural_tags(r)
        suffix = f"  [{','.join(sorted(tags))}]" if tags else ""
        return f"{r['id']}  {r.get('name', '')}{suffix}"

    _EXERCISE_MENU_CACHE = "\n".join(
        _line(r) for r in rows if r.get("id")
    ) or "(exercise menu unavailable)"
    return _EXERCISE_MENU_CACHE




_SUPERSET_GROUP_RE = re.compile(r"^[A-Z][0-9]?$")


def _remap_invalid_superset_groups(day: dict) -> None:
    """Remap "BR2"/"BS1"-style superset labels to schema-legal ones (run #10).

    Grouping identity is what matters, not the label text — every exercise in
    the day sharing an invalid label gets the same fresh legal label, chosen
    to not collide with labels already in use that day.
    """
    exercises = [
        ex
        for block in day.get("lifting_blocks") or []
        if isinstance(block, dict)
        for ex in block.get("exercises") or []
        if isinstance(ex, dict)
    ]
    used = {
        ex["superset_group"]
        for ex in exercises
        if isinstance(ex.get("superset_group"), str) and _SUPERSET_GROUP_RE.match(ex["superset_group"])
    }
    remap: dict[str, str] = {}
    for ex in exercises:
        g = ex.get("superset_group")
        if not isinstance(g, str) or _SUPERSET_GROUP_RE.match(g):
            continue
        if g not in remap:
            fresh = next(
                (c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in used), None
            )
            if fresh is None:  # 26 groups in one day — schema will reject; leave it
                continue
            used.add(fresh)
            remap[g] = fresh
        ex["superset_group"] = remap[g]


def _normalize_authored_dict(data: dict) -> dict:
    """Deterministic normalization of near-miss LLM output (repair plane).

    Live run #5 attempt 3 parsed a full 63-day program cleanly and failed on
    exactly three MECHANICAL classes — fix those, reject nothing the schema
    can still catch afterward:
      1. day_focus (and similar) strings over the 120-char cap → clipped.
      2. lifting_blocks: null on non-lifting days → [].
      3. citations shaped {doc_id, sections} → {doc_id, title, why} (title
         derived from doc_id; why joined from sections; display re-resolves
         real titles from frontmatter anyway).
      4. superset_group "" → None (run #7 — the model uses the empty string
         for ungrouped exercises; the schema pattern requires "A1"-style).
      5. All length-capped prose fields clipped to their schema caps (run #8
         attempt 1 died on ONE over-long intent_summary in an otherwise-valid
         63-day program).
      6. Days nested inside lifting_blocks lifted back to the days array
         (runs #4/#8/#9 — the dominant failure class: one dropped `]}` makes
         json_repair close lifting_blocks too late, so every subsequent day
         nests recursively inside it; content is intact, only misplaced).
    """
    if not isinstance(data, dict):
        return data

    def _clip(obj: dict, key: str, cap: int) -> None:
        v = obj.get(key)
        if isinstance(v, str) and len(v) > cap:
            obj[key] = v[: cap - 3] + "..."

    def _is_migrant_day(b: Any) -> bool:
        return isinstance(b, dict) and "day_index" in b and "block_name" not in b

    days_in = data.get("days")
    if isinstance(days_in, list):
        out: list = []
        queue = list(days_in)
        while queue:
            d = queue.pop(0)
            if isinstance(d, dict) and isinstance(d.get("lifting_blocks"), list):
                real_blocks: list = []
                migrants: list = []
                for b in d["lifting_blocks"]:
                    (migrants if _is_migrant_day(b) else real_blocks).append(b)
                if migrants:
                    d["lifting_blocks"] = real_blocks
                    queue = migrants + queue  # chronological order preserved
                # Bracket slips also strand the day's own trailing fields
                # (day_focus/cues) inside its last block — move them home.
                for b in real_blocks:
                    if isinstance(b, dict) and "block_name" in b:
                        for stray in ("day_focus", "cues"):
                            if stray in b:
                                val = b.pop(stray)
                                if not d.get(stray):
                                    d[stray] = val
            out.append(d)
        data["days"] = out

    for day in data.get("days") or []:
        if not isinstance(day, dict):
            continue
        if day.get("lifting_blocks") is None:
            day["lifting_blocks"] = []
        _clip(day, "day_focus", 120)
        _clip(day, "phase_name", 60)
        for block in day.get("lifting_blocks") or []:
            if not isinstance(block, dict):
                continue
            _clip(block, "block_name", 60)
            for ex in block.get("exercises") or []:
                # superset_group must be None or "A1"-style; the model emits
                # "" for ungrouped exercises (live run #7).
                if isinstance(ex, dict) and isinstance(ex.get("superset_group"), str) and not ex["superset_group"].strip():
                    ex["superset_group"] = None
        _remap_invalid_superset_groups(day)
    for phase in data.get("phases") or []:
        if isinstance(phase, dict):
            _clip(phase, "phase_id", 40)
            _clip(phase, "name", 60)
            _clip(phase, "intent_summary", 240)
    rationale = data.get("rationale")
    if isinstance(rationale, dict):
        fixed = []
        for c in rationale.get("citations") or []:
            if not isinstance(c, dict):
                continue
            doc_id = c.get("doc_id") or ""
            title = c.get("title") or doc_id.replace("_", " ").title()
            why = c.get("why")
            if not why:
                sections = c.get("sections")
                why = "; ".join(sections) if isinstance(sections, list) else "cited by author"
            fixed.append({"doc_id": doc_id, "title": title, "why": str(why)[:240]})
        if fixed:
            rationale["citations"] = fixed
    return data


def _build_user_prompt(
    *,
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,
    knowledge_pack: dict,
    previous_violations: Optional[list],
) -> str:
    """Assemble the user prompt from the template + substitutions."""
    template = load_prompt("program_engine_author.md")
    combined = (knowledge_pack or {}).get("combined", "") or "(no knowledge pack)"
    profile_summary = _format_profile_summary(pitcher_profile or {})
    goal_json = json.dumps(goal_spec or {}, indent=2)
    violations_text = _format_previous_violations(previous_violations)
    user = template.replace("{knowledge_pack_combined}", combined)
    user = user.replace("{pitcher_profile_summary}", profile_summary)
    user = user.replace("{pitcher_context}", pitcher_context or "(no per-pitcher context)")
    user = user.replace("{goal_spec}", goal_json)
    user = user.replace("{previous_violations}", violations_text)
    user = user.replace("{exercise_menu}", _exercise_menu())
    return user


async def author_program(
    pitcher_profile: dict,
    pitcher_context: str,
    goal_spec: dict,
    knowledge_pack: dict,
    *,
    seed: Optional[int] = None,
    previous_violations: Optional[list] = None,
) -> PitcherProgram:
    """LLM-forward program authoring.

    Args:
        pitcher_profile: The pitcher's profile dict (id, role, physical_profile,
            injury_history, training preferences).
        pitcher_context: Free-form context string (the per-pitcher context.md).
        goal_spec: `{"tags": ["velocity"], "target_weeks": 12, "target_date": "...",
            "tunables": {...}}`.
        knowledge_pack: Output of `research_resolver.resolve_for_program_gen`.
            Must include `knowledge_version` + `combined` keys.
        seed: Optional integer for deterministic LLM sampling (reserved; not
            wired into call_llm_reasoning at v1 — kept for the test surface).
        previous_violations: When set, includes them in the prompt as
            "Your previous output had these issues; fix them" (re-prompt path
            used by Task 3.3).

    Returns:
        A schema-valid `PitcherProgram`. The `knowledge_version` field is
        stamped from `knowledge_pack["knowledge_version"]` AFTER parse — so
        the LLM's placeholder value is overwritten.

    Raises:
        GenerationFailure: On LLM timeout, malformed JSON, or schema validation
            failure. The orchestrator catches this and either re-prompts or
            falls back to the deterministic floor.
    """
    user_prompt = _build_user_prompt(
        pitcher_profile=pitcher_profile,
        pitcher_context=pitcher_context,
        goal_spec=goal_spec,
        knowledge_pack=knowledge_pack,
        previous_violations=previous_violations,
    )

    # Call the reasoning model (L11) — DeepSeek deepseek-reasoner, 120s timeout.
    try:
        raw = await call_llm_reasoning(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_prompt,
            # A full multi-week PitcherProgram (60-90 day objects) is ~20k+
            # output tokens and the reasoner's CoT shares the budget — 8k and
            # 32k both truncated live. 65536 probed accepted 2026-07-13.
            max_tokens=65536,
            timeout=300,  # one-shot compile step; latency-tolerant by design
            return_metadata=True,
        )
    except TimeoutError as e:
        logger.warning("author_program: LLM timeout (%s)", e)
        raise GenerationFailure("llm_timeout", detail=str(e)) from e
    except Exception as e:
        logger.warning("author_program: LLM error (%s)", e)
        raise GenerationFailure("llm_error", detail=str(e)) from e

    # return_metadata=True → (content, finish_reason). Truncation is a
    # first-class failure: don't burn a parse attempt on a cut-off body.
    if isinstance(raw, tuple):
        raw, finish_reason = raw[0], (raw[1] or "stop")
        if finish_reason == "length":
            raise GenerationFailure(
                "llm_truncated",
                detail=f"finish_reason=length at max_tokens=65536; output chars={len(raw or '')}",
            )

    if not isinstance(raw, str) or not raw.strip():
        raise GenerationFailure("llm_empty_response")

    text = _strip_json_fences(raw)

    # Parse (with deterministic bracket repair) → normalize → validate.
    # json_repair handles the one-bad-bracket-in-65KB class (live run #3);
    # _normalize_authored_dict handles the mechanical near-misses (run #5);
    # the full Pydantic schema still gates everything at the end.
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        try:
            import json_repair

            data = json_repair.loads(text)
            logger.warning("author_program: JSON repaired deterministically (json_repair)")
        except Exception as e:
            logger.warning("author_program: JSON unrecoverable (%s)", e)
            raise GenerationFailure("json_parse_failed", detail=str(e)) from e
    try:
        program = PitcherProgram.model_validate(_normalize_authored_dict(data))
    except ValidationError as e:
        logger.warning("author_program: schema validation failed post-normalize (%s)", e)
        raise GenerationFailure("schema_validation_failed", detail=str(e)) from e
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("author_program: JSON parse failed (%s)", e)
        raise GenerationFailure("json_parse_failed", detail=str(e)) from e

    # Stamp knowledge_version from the pack — the LLM's placeholder is overwritten.
    kv = (knowledge_pack or {}).get("knowledge_version")
    if kv:
        program = program.model_copy(update={"knowledge_version": kv})

    return program
