"""Layer 1 of the Program Builder funnel: structured-input → candidate templates.

Pure function. Reads block_library through a _load_* helper for testability.
"""
from __future__ import annotations

from typing import Optional


_REQUIRED_KEYS = {"domain", "goal", "duration_weeks", "effective_phase", "hard_constraints"}
_VALID_DOMAINS = ("throwing", "lifting")
_MAX_CANDIDATES = 3


def _load_all_templates() -> list[dict]:
    """Read all rows from block_library. Tests monkeypatch this."""
    from bot.services import db
    resp = db.get_client().table("block_library").select("*").execute()
    return resp.data or []


def _parse_int4range(rng: Optional[str]) -> Optional[tuple[int, int]]:
    """Parse Postgres int4range literal '[lo,hi]' or '[lo,hi)' to (lo, hi_inclusive).

    Returns None if rng is None/empty. Treats both '[]' and '[)' as inclusive on lower
    and adjusts the upper bound for half-open notation. Valid examples:
      '[8,12]'  -> (8, 12)
      '[8,12)'  -> (8, 11)
      '(7,12]'  -> (8, 12)
    """
    if not rng:
        return None
    s = rng.strip()
    if len(s) < 5:
        return None
    lo_inc = s[0] == "["
    hi_inc = s[-1] == "]"
    parts = s[1:-1].split(",")
    if len(parts) != 2:
        return None
    try:
        lo = int(parts[0])
        hi = int(parts[1])
    except ValueError:
        return None
    if not lo_inc:
        lo += 1
    if not hi_inc:
        hi -= 1
    return (lo, hi)


def _matches(tpl: dict, env: dict) -> bool:
    if tpl.get("domain") != env["domain"]:
        return False
    if env["effective_phase"] not in (tpl.get("compatible_phases") or []):
        return False
    if env["goal"] not in (tpl.get("goal_tags") or []):
        return False
    rng = _parse_int4range(tpl.get("duration_range_weeks"))
    if rng:
        lo, hi = rng
        if not (lo <= env["duration_weeks"] <= hi):
            return False
    # Hard-constraint filtering: stays light in v1.
    # If a template has tunable_parameters_schema declaring incompatibility tags,
    # honor them. Otherwise no-op (templates self-declare in scaffold).
    incompat = (tpl.get("tunable_parameters_schema") or {}).get("incompatible_with") or []
    for hc in env["hard_constraints"]:
        if hc in incompat:
            return False
    return True


def _score(tpl: dict, env: dict) -> int:
    """Higher = better. Used to rank when more than _MAX_CANDIDATES match."""
    score = 0
    if tpl.get("implied_phase") == env["effective_phase"]:
        score += 5  # template implies the same phase the pitcher is in — good fit
    rng = _parse_int4range(tpl.get("duration_range_weeks"))
    if rng:
        lo, hi = rng
        # Prefer templates whose midpoint is closest to the requested duration
        midpoint = (lo + hi) / 2
        score -= abs(midpoint - env["duration_weeks"])
    return score


def match_candidates(constraint_envelope: dict) -> list[dict]:
    """Layer 1: filter+rank block_library to 1–3 candidate templates.

    constraint_envelope keys (all required):
      - domain: 'throwing' | 'lifting'
      - goal: str (must match a goal_tag on the template)
      - duration_weeks: int
      - effective_phase: str (must be in template.compatible_phases)
      - hard_constraints: list[str]

    Returns up to 3 templates. Empty list if no template matches.
    """
    missing = _REQUIRED_KEYS - constraint_envelope.keys()
    if missing:
        raise KeyError(f"constraint_envelope missing keys: {sorted(missing)}")
    if constraint_envelope["domain"] not in _VALID_DOMAINS:
        raise ValueError(f"domain must be one of {_VALID_DOMAINS}, got {constraint_envelope['domain']!r}")

    candidates = [t for t in _load_all_templates() if _matches(t, constraint_envelope)]
    candidates.sort(key=lambda t: _score(t, constraint_envelope), reverse=True)
    return candidates[:_MAX_CANDIDATES]
