"""Program runtime helpers: phase precedence resolution + active-program lookups.

Pure functions. All DB reads go through small _load_* helpers so tests
can monkeypatch them. New canonical home for queries against the new
`programs` table — coexists with legacy `bot/services/programs.py`
(which targets the v0 `training_programs` table and stays untouched).
"""
from __future__ import annotations

from typing import Optional

_VALID_DOMAINS = ("throwing", "lifting")


def _ensure_domain(domain: str) -> None:
    if domain not in _VALID_DOMAINS:
        raise ValueError(f"domain must be one of {_VALID_DOMAINS}, got {domain!r}")


def _load_active_program(pitcher_id: str, domain: str) -> Optional[dict]:
    """Return the row from `programs` where (pitcher_id, domain, status='active'), or None."""
    from bot.services import db
    return db.get_active_program(pitcher_id, domain)


def _load_template_implied_phase(template_id: str) -> Optional[str]:
    from bot.services import db
    tpl = db.get_block_library_row(template_id)
    if not tpl:
        return None
    return tpl.get("implied_phase")


def _load_pitcher_overrides(pitcher_id: str) -> dict:
    from bot.services import db
    model = db.get_pitcher_training_model(pitcher_id) or {}
    return {
        "coach_throwing_phase_override": model.get("coach_throwing_phase_override"),
        "coach_lifting_phase_override":  model.get("coach_lifting_phase_override"),
    }


def _load_team_phase_for_pitcher(pitcher_id: str, domain: str) -> Optional[str]:
    from bot.services import db, team_scope
    try:
        profile = db.get_pitcher(pitcher_id)
    except KeyError:
        return None
    team_id = (profile or {}).get("team_id")
    if not team_id:
        return None
    return team_scope.get_team_phase(team_id, domain=domain)


def get_effective_phase(pitcher_id: str, domain: str) -> Optional[str]:
    """Per-domain phase precedence: active program implied_phase > coach override > team default.

    See spec D6 + Section 1 (Phase model).
    """
    _ensure_domain(domain)

    active = _load_active_program(pitcher_id, domain)
    if active and active.get("parent_template_id"):
        implied = _load_template_implied_phase(active["parent_template_id"])
        if implied:
            return implied

    overrides = _load_pitcher_overrides(pitcher_id)
    override = overrides.get(f"coach_{domain}_phase_override")
    if override:
        return override

    return _load_team_phase_for_pitcher(pitcher_id, domain)
