"""System Guardian — Phase 1 package skeleton.

V1 builds in PR sequence per
``docs/superpowers/plans/2026-05-09-system-guardian-amendments.md`` §6.

This is PR-2: pure logic + storage helpers + the 3am pruning job hook
(:func:`run_observation_prune` per D15). Collectors land in PR-3 / PR-4 and
admin routes / shakedown logic in PR-5.

Public API surface kept small on purpose so future PRs can reshape internals
without breaking the bot's import points.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from bot.config import CHICAGO_TZ
from bot.services.system_guardian import classify, cluster, debug_packet, incidents, normalize, store, tick
from bot.services.system_guardian.tick import run_guardian_tick

logger = logging.getLogger(__name__)

# A1: bounded timeout on every collector / scheduled hook.
_PRUNE_TIMEOUT_S = 5.0


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def _emit_self_observation(
    *,
    event_type: str,
    severity_hint: str,
    message: str,
    metadata: dict[str, Any] | None = None,
    code: str | None = None,
) -> None:
    """Best-effort guardian_self observation emit.

    Used by the prune job to record both success ("rows pruned: N") and
    failure ("collector_failure"). Wrapped in a broad except because the
    scheduler hook MUST NOT raise — that's the whole point of D15.
    """
    try:
        store.insert_observation(
            {
                "observed_at": _now_iso(),
                "source": "guardian",
                "service": "scheduler",
                "event_type": event_type,
                "severity_hint": severity_hint,
                "surface": "guardian_self",
                "route_or_job": "guardian_prune_observations",
                "message": message,
                "metadata": {
                    **(metadata or {}),
                    "category": "guardian_self",
                    "code": code or event_type,
                },
            }
        )
    except Exception as e:  # pragma: no cover — defensive; insert_observation
        logger.error("guardian: self-observation emit failed: %s", e, exc_info=True)


async def run_observation_prune() -> int:
    """3am scheduler hook (D15): prune old observations + emit self-observation.

    Returns the row count pruned (or ``-1`` on failure). Per A1, all errors
    are swallowed and surfaced as a ``collector_failure`` observation rather
    than re-raised — Guardian must never crash the host process.

    Bounded timeout per A1 (5s). The actual SQL function call is sync, so we
    push it through ``asyncio.to_thread`` and wrap with ``asyncio.wait_for``.
    """
    try:
        pruned = await asyncio.wait_for(
            asyncio.to_thread(store.call_prune_old_observations),
            timeout=_PRUNE_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error("guardian: prune job exceeded %ss timeout", _PRUNE_TIMEOUT_S)
        _emit_self_observation(
            event_type="collector_failure",
            severity_hint="warning",
            message=(
                f"prune_observations_daily timed out after {_PRUNE_TIMEOUT_S}s"
            ),
            metadata={"timeout_s": _PRUNE_TIMEOUT_S, "job": "guardian_prune_observations"},
            code="collector_failure",
        )
        return -1
    except Exception as e:
        logger.error("guardian: prune job raised: %s", e, exc_info=True)
        _emit_self_observation(
            event_type="collector_failure",
            severity_hint="warning",
            message=f"prune_observations_daily raised {type(e).__name__}: {e}",
            metadata={
                "exception_class": type(e).__name__,
                "job": "guardian_prune_observations",
            },
            code="collector_failure",
        )
        return -1

    if pruned < 0:
        # Storage layer logged + returned -1; emit a guardian_self failure so
        # the loss-of-prune surfaces in the digest.
        _emit_self_observation(
            event_type="collector_failure",
            severity_hint="warning",
            message="prune_observations_daily RPC returned error sentinel",
            metadata={"job": "guardian_prune_observations"},
            code="collector_failure",
        )
        return pruned

    _emit_self_observation(
        event_type="prune_observations_daily",
        severity_hint="info",
        message=f"Pruned {pruned} system_observations rows older than 14 days",
        metadata={"rows_pruned": pruned, "job": "guardian_prune_observations"},
        code="prune_observations_daily",
    )
    return pruned


async def check_shakedown_expiry() -> bool:
    """Periodic scheduler hook (PR-5 / A6): auto-expire the shakedown window.

    Hourly cadence in production. Calls
    :func:`store.check_and_expire_shakedown` to detect the 24h transition,
    and on a true transition dispatches the end-of-window summary DM via
    :func:`notify.send_shakedown_summary`. Returns the transition bool.

    Never raises - all failures are absorbed and logged so a single bad hour
    doesn't stop the scheduler.
    """
    try:
        transitioned = await asyncio.to_thread(store.check_and_expire_shakedown)
    except Exception as e:
        logger.error("guardian: check_shakedown_expiry probe failed: %s", e, exc_info=True)
        return False

    if not transitioned:
        return False

    try:
        # Local import keeps the python-telegram-bot dep off the cold path.
        from bot.services.system_guardian import notify as _notify

        await _notify.send_shakedown_summary()
    except Exception as e:
        logger.error(
            "guardian: send_shakedown_summary failed in expiry hook: %s",
            e,
            exc_info=True,
        )
    return True


__all__ = [
    "classify",
    "cluster",
    "debug_packet",
    "incidents",
    "normalize",
    "store",
    "tick",
    "run_observation_prune",
    "check_shakedown_expiry",
    "run_guardian_tick",
]
