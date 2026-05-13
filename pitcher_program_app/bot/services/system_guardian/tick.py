"""System Guardian tick orchestrator (PR-6 — A1 runtime contract).

Per amendments doc §2 A1, V1 acceptance #10:

    A single Guardian tick wraps all collectors in
    ``asyncio.gather(..., return_exceptions=True)`` with a tick budget of
    30s total. If tick budget exceeded twice in a row, the next tick logs
    a ``severity=warning category=guardian_self`` incident.

This module owns the **outer** runtime contract — per-collector 5s ceilings
are already enforced inside each collector module (existing_health,
app_health, supabase_app). PR-6 adds:

* A single :func:`run_guardian_tick` coroutine that fans out the three Phase
  1 collectors in parallel with a 30s wallclock tick budget.
* Belt-and-suspenders 5s per-collector ``asyncio.wait_for`` enforced HERE in
  addition to the per-collector internal ceiling — defends against a future
  collector forgetting its own wrapper.
* Process-local "consecutive over-budget" counter. The WARNING incident
  fires on the SECOND consecutive over-budget tick, per A1 exactly.
* Persistence of every returned observation via
  :func:`store.insert_observation_with_notify` so the standard A6 notifier
  path (shakedown suppression, dedup) still applies.

The tick NEVER raises. The outer body is wrapped in try/except as
belt-and-suspenders — even if ``asyncio.gather`` itself somehow raises
(it shouldn't with ``return_exceptions=True``), we return a summary dict.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, Awaitable, Callable

from bot.config import CHICAGO_TZ
from bot.services.system_guardian import store as _store

logger = logging.getLogger(__name__)

# A1 tick budget — wallclock total across all collectors.
TICK_BUDGET_S: float = 30.0

# A1 per-collector belt-and-suspenders ceiling. Each collector already
# enforces its own 5s internally; this is a second layer at the tick level.
PER_COLLECTOR_TIMEOUT_S: float = 5.0

# Severity thresholds for the consecutive-over-budget counter.
# A1 wording: "If tick budget exceeded twice in a row, the next tick logs a
# severity=warning ... incident." That means:
#  - 1 consecutive over-budget tick: info (single late tick is noisy, not actionable)
#  - 2nd consecutive over-budget tick: WARNING (A1's "twice in a row" trigger)
#  - 5th+ consecutive: critical (chronic — obvious extension of the rule)
_WARNING_AT = 2
_CRITICAL_AT = 5

# Process-local counter — survives across ticks within a single bot process.
# Resets on any under-budget tick (and on process restart, which is itself a
# meaningful signal).
_consecutive_over_budget: int = 0

# Lock guarding the counter + the tick-level emit so two simultaneous ticks
# can't double-count. In practice the scheduler never fires this re-entrantly,
# but a manual /admin/guardian/tick during a scheduled tick is plausible.
_tick_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Lazy-allocate the asyncio.Lock so we don't bind to a loop at import."""
    global _tick_lock
    if _tick_lock is None:
        _tick_lock = asyncio.Lock()
    return _tick_lock


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def _reset_consecutive_over_budget() -> None:
    """Test/admin hook: zero the counter. NOT a public API."""
    global _consecutive_over_budget
    _consecutive_over_budget = 0


def _get_consecutive_over_budget() -> int:
    """Test hook: peek at the counter without resetting."""
    return _consecutive_over_budget


# ---------------------------------------------------------------------------
# Helper: bounded single collector
# ---------------------------------------------------------------------------


async def _run_one_collector_bounded(
    name: str,
    fn: Callable[[], Awaitable[list[dict]]],
    per_collector_timeout: float | None = None,
) -> tuple[str, list[dict], str, float]:
    """Run a single collector with a hard timeout. Never raise.

    Returns ``(name, observations, outcome, duration_s)`` where outcome is one
    of ``"ok"`` / ``"timeout"`` / ``"error"``. On timeout/error the
    observations list contains exactly one synthesized ``collector_failure``
    observation tagged ``source=tick.{name}`` so the tick-level wrapper is
    distinguishable from the collector's own internal failure path.

    The 5s wrapper here is belt-and-suspenders: each Phase 1 collector also
    enforces its own 5s ``asyncio.wait_for``. If the inner ceiling fires the
    collector returns gracefully and outcome is ``"ok"`` (the collector's
    failure observation is in the list). If the inner ceiling somehow doesn't
    fire (e.g. a future collector forgets the wrapper), this outer ceiling
    catches it.

    ``per_collector_timeout=None`` (the default) reads the module-level
    ``PER_COLLECTOR_TIMEOUT_S`` AT CALL TIME so monkeypatching the constant
    in tests works as expected. Passing an explicit float overrides.
    """
    if per_collector_timeout is None:
        per_collector_timeout = PER_COLLECTOR_TIMEOUT_S
    started = datetime.now(CHICAGO_TZ)
    started_perf = asyncio.get_event_loop().time()

    def _duration() -> float:
        return asyncio.get_event_loop().time() - started_perf

    try:
        result = await asyncio.wait_for(fn(), timeout=per_collector_timeout)
        if not isinstance(result, list):
            # Defensive: a future collector returning the wrong shape is
            # caller error, not a runtime failure. Coerce + log.
            logger.warning(
                "guardian.tick: collector %s returned non-list (%s); coercing to []",
                name,
                type(result).__name__,
            )
            result = []
        return name, result, "ok", _duration()
    except asyncio.TimeoutError:
        duration = _duration()
        logger.error(
            "guardian.tick: collector %s exceeded outer %ss ceiling (took %.2fs)",
            name,
            per_collector_timeout,
            duration,
        )
        return (
            name,
            [
                {
                    "observed_at": _now_iso(),
                    "source": f"tick.{name}",
                    "service": "guardian",
                    "event_type": "collector_failure",
                    "severity_hint": "warning",
                    "surface": "guardian_self",
                    "route_or_job": f"tick.{name}",
                    "message": (
                        f"tick wrapper timeout: collector {name} exceeded "
                        f"{per_collector_timeout}s outer ceiling"
                    ),
                    "metadata": {
                        "category": "guardian_self",
                        "code": "collector_failure",
                        "step": "tick_wait_for",
                        "collector": name,
                        "timeout_s": per_collector_timeout,
                        "started_at": started.isoformat(),
                    },
                }
            ],
            "timeout",
            duration,
        )
    except Exception as e:
        duration = _duration()
        logger.error(
            "guardian.tick: collector %s raised: %s",
            name,
            e,
            exc_info=True,
        )
        return (
            name,
            [
                {
                    "observed_at": _now_iso(),
                    "source": f"tick.{name}",
                    "service": "guardian",
                    "event_type": "collector_failure",
                    "severity_hint": "warning",
                    "surface": "guardian_self",
                    "route_or_job": f"tick.{name}",
                    "message": (
                        f"tick wrapper caught {type(e).__name__} from collector "
                        f"{name}: {e}"
                    ),
                    "metadata": {
                        "category": "guardian_self",
                        "code": "collector_failure",
                        "step": "tick_collector_call",
                        "collector": name,
                        "exception_class": type(e).__name__,
                        "stack": traceback.format_exc()[:1500],
                        "started_at": started.isoformat(),
                    },
                }
            ],
            "error",
            duration,
        )


# ---------------------------------------------------------------------------
# Tick budget incident emit
# ---------------------------------------------------------------------------


def _build_tick_budget_observation(
    *,
    duration_s: float,
    consecutive: int,
    collectors_summary: dict[str, dict[str, Any]],
) -> dict:
    """Build the ``tick_budget_exceeded`` observation.

    Severity tier per A1:
      * 1 consecutive over-budget → info (single late tick)
      * 2nd consecutive           → warning (A1's "twice in a row")
      * 5th+ consecutive          → critical (chronic; obvious extension)
    """
    if consecutive >= _CRITICAL_AT:
        severity = "critical"
    elif consecutive >= _WARNING_AT:
        severity = "warning"
    else:
        severity = "info"

    return {
        "observed_at": _now_iso(),
        "source": "tick.run_guardian_tick",
        "service": "guardian",
        "event_type": "tick_budget_exceeded",
        "severity_hint": severity,
        "surface": "guardian_self",
        "route_or_job": "run_guardian_tick",
        "signature": "tick_budget_exceeded",  # stable — clustering pins on this
        "message": (
            f"Guardian tick exceeded {TICK_BUDGET_S}s budget "
            f"(took {duration_s:.2f}s); consecutive over-budget ticks: "
            f"{consecutive}"
        ),
        "metadata": {
            "category": "guardian_self",
            "code": "tick_budget_exceeded",
            "duration_s": round(duration_s, 3),
            "budget_s": TICK_BUDGET_S,
            "consecutive_over_budget": consecutive,
            "collectors": collectors_summary,
        },
    }


# ---------------------------------------------------------------------------
# Public tick orchestrator
# ---------------------------------------------------------------------------


async def run_guardian_tick() -> dict:
    """Run all Phase 1 collectors in parallel with a 30s tick budget.

    Returns a summary dict (never raises). On any catastrophic outer failure
    (which shouldn't happen with ``return_exceptions=True``) the summary will
    record the error and return cleanly.

    Persistence: every observation returned by every collector — including
    synthesized ``collector_failure`` rows from the per-collector wrapper and
    the ``tick_budget_exceeded`` self-observation — is persisted via
    :func:`store.insert_observation_with_notify`. Shakedown suppression and
    dedup apply as normal.
    """
    global _consecutive_over_budget

    lock = _get_lock()
    async with lock:
        started_at = datetime.now(CHICAGO_TZ)
        started_perf = asyncio.get_event_loop().time()

        summary: dict[str, Any] = {
            "started_at": started_at.isoformat(),
            "duration_s": 0.0,
            "over_budget": False,
            "consecutive_over_budget": _consecutive_over_budget,
            "collectors": {},
            "observations_persisted": 0,
            "tick_budget_incident_emitted": False,
        }

        # Lazy import the collectors so importing tick.py doesn't pull the
        # whole collector dependency graph (httpx, supabase) on cold start.
        try:
            from bot.services.system_guardian.collectors import (
                collect_app_health,
                collect_existing_health,
                collect_supabase_app,
            )
        except Exception as e:  # pragma: no cover — collectors package always importable
            logger.error(
                "guardian.tick: collectors package import failed: %s",
                e,
                exc_info=True,
            )
            summary["duration_s"] = round(
                asyncio.get_event_loop().time() - started_perf, 3
            )
            summary["error"] = f"collectors_import_failed: {type(e).__name__}"
            return summary

        collectors: dict[str, Callable[[], Awaitable[list[dict]]]] = {
            "existing_health": collect_existing_health,
            "app_health": collect_app_health,
            "supabase_app": collect_supabase_app,
        }

        results: list[tuple[str, list[dict], str, float]] = []
        over_budget = False

        try:
            # 30s wallclock budget around the entire gather. Per-collector 5s
            # is enforced INSIDE _run_one_collector_bounded.
            gather_coro = asyncio.gather(
                *[
                    _run_one_collector_bounded(name, fn)
                    for name, fn in collectors.items()
                ],
                return_exceptions=True,
            )
            raw_results = await asyncio.wait_for(gather_coro, timeout=TICK_BUDGET_S)

            # _run_one_collector_bounded never raises, so we shouldn't get
            # exceptions back from gather — but return_exceptions=True means
            # we need to handle the BaseException case defensively.
            for idx, item in enumerate(raw_results):
                if isinstance(item, BaseException):
                    name = list(collectors.keys())[idx]
                    logger.error(
                        "guardian.tick: collector %s returned exception via gather: %s",
                        name,
                        item,
                        exc_info=item,
                    )
                    results.append(
                        (
                            name,
                            [
                                {
                                    "observed_at": _now_iso(),
                                    "source": f"tick.{name}",
                                    "service": "guardian",
                                    "event_type": "collector_failure",
                                    "severity_hint": "warning",
                                    "surface": "guardian_self",
                                    "route_or_job": f"tick.{name}",
                                    "message": (
                                        f"tick gather caught {type(item).__name__} "
                                        f"from {name}: {item}"
                                    ),
                                    "metadata": {
                                        "category": "guardian_self",
                                        "code": "collector_failure",
                                        "step": "tick_gather",
                                        "collector": name,
                                        "exception_class": type(item).__name__,
                                    },
                                }
                            ],
                            "error",
                            0.0,
                        )
                    )
                else:
                    results.append(item)
        except asyncio.TimeoutError:
            # Whole-tick budget exceeded. Cancel the gather and treat each
            # not-yet-completed collector as a tick-budget casualty.
            over_budget = True
            elapsed = asyncio.get_event_loop().time() - started_perf
            logger.error(
                "guardian.tick: tick budget %ss exceeded (elapsed=%.2fs)",
                TICK_BUDGET_S,
                elapsed,
            )
            gather_coro.cancel()
            # Try to drain whatever finished before the budget popped. We
            # can't reliably get partial results from a cancelled gather, so
            # synthesize a collector_failure for each collector — tick-budget
            # is a tick-level failure mode and the per-collector wrappers
            # may not have run.
            for name in collectors:
                results.append(
                    (
                        name,
                        [
                            {
                                "observed_at": _now_iso(),
                                "source": f"tick.{name}",
                                "service": "guardian",
                                "event_type": "collector_failure",
                                "severity_hint": "warning",
                                "surface": "guardian_self",
                                "route_or_job": f"tick.{name}",
                                "message": (
                                    f"tick budget {TICK_BUDGET_S}s exceeded; "
                                    f"collector {name} did not complete"
                                ),
                                "metadata": {
                                    "category": "guardian_self",
                                    "code": "collector_failure",
                                    "step": "tick_budget",
                                    "collector": name,
                                    "tick_budget_s": TICK_BUDGET_S,
                                },
                            }
                        ],
                        "timeout",
                        elapsed,
                    )
                )
        except Exception as e:
            # Belt-and-suspenders: gather should not raise other exceptions
            # with return_exceptions=True. If it does, we record the failure
            # and return — never raise.
            logger.error(
                "guardian.tick: unexpected exception in gather: %s",
                e,
                exc_info=True,
            )
            summary["error"] = f"gather_failed: {type(e).__name__}: {e}"
            summary["duration_s"] = round(
                asyncio.get_event_loop().time() - started_perf, 3
            )
            return summary

        duration_s = asyncio.get_event_loop().time() - started_perf
        summary["duration_s"] = round(duration_s, 3)

        # If we didn't pop the wallclock budget above, still check whether
        # the gather happened to take >TICK_BUDGET_S (e.g. cooperative cleanup
        # cycles pushed us over). Belt-and-suspenders for the over_budget flag.
        if not over_budget and duration_s > TICK_BUDGET_S:
            over_budget = True

        # Update the consecutive-over-budget counter atomically (inside the
        # lock, so two simultaneous ticks can't both increment off the same
        # stale value).
        if over_budget:
            _consecutive_over_budget += 1
        else:
            _consecutive_over_budget = 0

        summary["over_budget"] = over_budget
        summary["consecutive_over_budget"] = _consecutive_over_budget

        # Build per-collector summary + collect observations for persistence.
        collectors_summary: dict[str, dict[str, Any]] = {}
        all_observations: list[dict] = []
        for name, obs_list, outcome, c_duration in results:
            collectors_summary[name] = {
                "observation_count": len(obs_list),
                "duration_s": round(c_duration, 3),
                "outcome": outcome,
            }
            all_observations.extend(obs_list)
        summary["collectors"] = collectors_summary

        # If we're over budget, append the tick_budget_exceeded observation.
        # Severity tier depends on the consecutive counter we just updated.
        if over_budget:
            tick_obs = _build_tick_budget_observation(
                duration_s=duration_s,
                consecutive=_consecutive_over_budget,
                collectors_summary=collectors_summary,
            )
            all_observations.append(tick_obs)
            summary["tick_budget_incident_emitted"] = True

        # Persist. Each insert is wrapped — a single failure must not abort
        # the rest of the persistence loop.
        persisted = 0
        for obs in all_observations:
            try:
                await _store.insert_observation_with_notify(obs)
                persisted += 1
            except Exception as e:
                logger.error(
                    "guardian.tick: insert_observation_with_notify failed: %s",
                    e,
                    exc_info=True,
                )
        summary["observations_persisted"] = persisted

        return summary


__all__ = [
    "run_guardian_tick",
    "_run_one_collector_bounded",
    "TICK_BUDGET_S",
    "PER_COLLECTOR_TIMEOUT_S",
]
