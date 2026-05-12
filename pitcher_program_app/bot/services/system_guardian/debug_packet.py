"""Debug packet builder per spec §12.

A debug packet is the JSON contract handed to Claude Code or Codex when an
incident needs investigation. The packet is a return value only; per
amendments doc A7 it MUST NOT be written to ``docs/guardian/incidents/`` or
any other in-repo path. Surfaces are: Telegram admin DM, the
``/admin/guardian/incidents/{id}/debug-packet`` API response (PR-5), and a
PII-stripped GitHub issue body in PR-7+.

Athlete context is full per decision D5: pitcher_id, name, current flag
levels, recent injury history. The packet is admin-only and never enters
git, so the trade-off is acceptable for debugging fidelity.

``recent_changes`` is populated via ``git log`` per D10 with the D14
cardinality cap: last 50 commits AND last 7 days, whichever yields fewer.
We shell out via ``subprocess.run`` — no library dep.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from bot.config import CHICAGO_TZ
from bot.services.system_guardian.normalize import redact_observation_for_emit

logger = logging.getLogger(__name__)


# Cardinality cap per D14.
_GIT_LOG_MAX_COMMITS = 50
_GIT_LOG_MAX_DAYS = 7
# Bounded subprocess timeout. Git log over a small repo is sub-second; we cap
# at 5s to match the runtime contract from A1.
_GIT_LOG_TIMEOUT_S = 5.0


def _repo_root() -> Path:
    """Return the repo root by walking up from this file.

    The package lives at ``pitcher_program_app/bot/services/system_guardian/``
    so the repo root is four levels up.
    """
    return Path(__file__).resolve().parents[4]


def _safe_git_log() -> list[dict]:
    """Shell out to ``git log`` and return up to N commits per D14.

    Failure modes are absorbed — debug packet generation must not crash on a
    malformed repo or missing ``git`` binary. The packet just gets an empty
    ``recent_changes`` list in that case.
    """
    since = (datetime.now(CHICAGO_TZ) - timedelta(days=_GIT_LOG_MAX_DAYS)).strftime("%Y-%m-%d")
    fmt = "%H%x1f%s%x1f%an%x1f%cI"  # shasubjectauthorcommitted_at
    cmd = [
        "git",
        "log",
        f"-n{_GIT_LOG_MAX_COMMITS}",
        f"--since={since}",
        f"--pretty=format:{fmt}",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=_GIT_LOG_TIMEOUT_S,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        logger.warning("guardian: git log failed for debug packet: %s", e)
        return []

    if result.returncode != 0:
        logger.warning(
            "guardian: git log nonzero exit (%s): %s",
            result.returncode,
            (result.stderr or "")[:200],
        )
        return []

    commits: list[dict] = []
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, subject, author, committed_at = parts
        commits.append(
            {
                "sha": sha,
                "subject": subject,
                "author": author,
                "committed_at": committed_at,
            }
        )
    return commits


def _athlete_context(pitcher_id: str | None) -> dict | None:
    """Load full athlete context per D5.

    Pulled inline rather than via collectors because debug-packet generation
    is read-only and infrequent. Returns ``None`` if no pitcher is associated
    with the incident or if the lookup fails — callers must tolerate the
    missing key.
    """
    if not pitcher_id:
        return None
    try:
        from bot.services import db as _db

        pitcher = _db.get_pitcher(pitcher_id)
    except Exception as e:
        logger.warning("guardian: athlete context load failed for %s: %s", pitcher_id, e)
        return None

    flags = {}
    try:
        from bot.services import db as _db

        flags = _db.get_active_flags(pitcher_id) or {}
    except Exception as e:
        logger.warning("guardian: active flags load failed for %s: %s", pitcher_id, e)

    injuries: list = []
    try:
        from bot.services import db as _db

        injuries = _db.get_injury_history(pitcher_id) or []
    except Exception as e:
        logger.warning("guardian: injury history load failed for %s: %s", pitcher_id, e)

    return {
        "pitcher_id": pitcher.get("pitcher_id"),
        "name": pitcher.get("name"),
        "role": pitcher.get("role"),
        "current_flag_level": flags.get("current_flag_level"),
        "current_arm_feel": flags.get("current_arm_feel"),
        "active_modifications": flags.get("active_modifications") or [],
        "recent_injury_history": injuries,
    }


def _affected_pitcher_id(incident: dict) -> str | None:
    """Best-effort pull of the affected pitcher id from the incident shape."""
    entities = incident.get("affected_entities") or {}
    if isinstance(entities, dict):
        if entities.get("pitcher_id"):
            return entities["pitcher_id"]
        ids = entities.get("pitcher_ids")
        if isinstance(ids, list) and ids:
            return ids[0]
    return None


def build_debug_packet(
    incident: dict,
    *,
    git_log_fn=None,
    athlete_context_fn=None,
) -> dict:
    """Return the §12 JSON contract for an incident.

    ``incident`` may be a row dict pulled from ``system_incidents`` OR a
    constructed dict in tests. The function does not require Supabase access
    by itself — athlete context is loaded via ``athlete_context_fn`` (default
    pulls from ``bot.services.db``), and ``git_log_fn`` defaults to a real
    shell-out.

    The returned dict is a runtime/Telegram/admin-API value (A7). The caller
    MUST NOT persist it to the repo.
    """
    git_log_fn = git_log_fn or _safe_git_log
    athlete_context_fn = athlete_context_fn or _athlete_context

    # Read-time redaction defense in depth — even if the incident row was
    # written before the write-time redactor existed, we strip again here.
    safe = redact_observation_for_emit(incident)

    samples = safe.get("sample_messages") or []
    evidence: list[str] = []
    if safe.get("first_seen"):
        evidence.append(f"First seen {safe['first_seen']}")
    if safe.get("last_seen") and safe.get("last_seen") != safe.get("first_seen"):
        evidence.append(f"Last seen {safe['last_seen']}")
    if safe.get("count"):
        evidence.append(f"Occurrences: {safe['count']}")
    for sample in samples[:3]:
        if isinstance(sample, dict) and sample.get("message"):
            evidence.append(str(sample["message"])[:200])
        elif isinstance(sample, str):
            evidence.append(sample[:200])

    pitcher_id = _affected_pitcher_id(safe)
    athlete = athlete_context_fn(pitcher_id) if pitcher_id else None

    packet: dict[str, Any] = {
        "title": safe.get("title") or "Untitled incident",
        "severity": safe.get("severity") or "info",
        "category": safe.get("category") or "runtime_error",
        "symptom": safe.get("title") or "",
        "impact": _impact_line(safe),
        "evidence": evidence,
        "likely_entrypoint": _likely_entrypoint(safe),
        "suspected_files": list(safe.get("suspected_files") or []),
        "recent_changes": git_log_fn() or [],
        "reproduction": _reproduction_steps(safe),
        "suggested_tests": _suggested_tests(safe),
        "vision_flags": list(safe.get("vision_flags") or []),
    }
    if athlete:
        packet["athlete_context"] = athlete
    return packet


# ---------------------------------------------------------------------------
# Heuristic helpers — kept small + replaceable by future LLM-assisted layer.
# ---------------------------------------------------------------------------

def _impact_line(incident: dict) -> str:
    severity = incident.get("severity") or "info"
    category = incident.get("category") or "runtime_error"
    affected = incident.get("affected_services") or []
    if severity == "critical":
        return f"Critical {category} affecting {', '.join(affected) or 'system'}."
    if severity == "warning":
        return f"Degraded {category} on {', '.join(affected) or 'system'}."
    return f"Informational {category} signal."


def _likely_entrypoint(incident: dict) -> str:
    surfaces = incident.get("affected_surfaces") or []
    if surfaces:
        return surfaces[0]
    return ""


def _reproduction_steps(incident: dict) -> list[str]:
    surfaces = incident.get("affected_surfaces") or []
    if not surfaces:
        return []
    return [f"Exercise the affected surface: {surfaces[0]}"]


def _suggested_tests(incident: dict) -> list[str]:
    files = incident.get("suspected_files") or []
    cmds = []
    for f in files:
        if "checkin" in f:
            cmds.append("python -m pytest tests/test_checkin_service_phase1.py")
        if "team_daily_status" in f or "team_scope" in f:
            cmds.append("python -m pytest tests/test_team_daily_status_contract.py")
        if "triage" in f or "baseline" in f:
            cmds.append("python -m pytest tests/test_baselines.py tests/test_triage_phase1.py")
    return sorted(set(cmds))


__all__ = ["build_debug_packet"]
