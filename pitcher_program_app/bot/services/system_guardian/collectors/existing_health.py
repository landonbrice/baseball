"""``existing_health`` collector — wraps the legacy 9am digest.

Per amendments doc:

* §3 V1 acceptance #2: this collector wraps :func:`bot.services.health_monitor.compute_daily_digest`
  so the legacy degradation signals become first-class normalized observations.
* §3 V1 acceptance #7: the 9am admin digest gets a new Guardian summary section
  that renders clustered observations.
* D13: ``compute_plan_health_rolling`` ALSO emits ONE additional observation
  with the deterministic signature ``plan_enrichment_health`` so a digest
  schema change can never silently mask the LLM-regression class.
* A1 runtime contract: every collector is an awaitable that finishes within
  5s (we wrap the sync digest computation in ``asyncio.to_thread`` +
  ``asyncio.wait_for``), NEVER raises, and on any failure returns ONE
  ``collector_failure`` observation so the wiring layer always has at least
  one row to persist.

This module owns ONLY the production-of-observation-dicts side. The wiring
layer (currently ``bot.services.health_monitor.format_guardian_summary_section``
+ ``bot.main._send_health_digest``) is responsible for calling
:func:`bot.services.system_guardian.store.insert_observation` on each
returned dict.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)

# A1: per-collector timeout ceiling.
_COLLECTOR_TIMEOUT_S = 5.0

# D13: stable signature for the dedicated plan-enrichment observation. Used as
# the literal ``signature`` value so cluster.generate_signature isn't allowed
# to re-derive it — the contract is that this exact string surfaces in the
# digest section AND in any incident keyed on it.
PLAN_ENRICHMENT_SIGNATURE = "plan_enrichment_health"

# Thresholds for the D13 observation (mirrors the icon thresholds in
# health_monitor.format_digest_message). enrichment_rate is 0..1.
_ENRICHMENT_CRITICAL_THRESHOLD = 0.40
_ENRICHMENT_WARNING_THRESHOLD = 0.60

# Sentinel source string so observations from this collector are traceable to
# the exact origin in the digest message + Supabase rows.
_SOURCE = "existing_health.collect_existing_health"


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


# ---------------------------------------------------------------------------
# Pure derivation helpers — easy to unit-test without async / DB plumbing.
# ---------------------------------------------------------------------------


def _build_plan_enrichment_observation(rolling: dict | None) -> dict:
    """D13: produce the standalone ``plan_enrichment_health`` observation.

    Always returns ONE observation regardless of input shape. Severity reflects
    the rolling enrichment ratio:

    * < 40%   → ``critical`` (LLM enrichment is broken)
    * 40-60%  → ``warning`` (slow drift — the canary band)
    * ≥ 60%   → ``info`` (healthy heartbeat)

    A query error or an empty rolling window degrades to ``info`` with a
    message documenting the gap — the goal is to never miss a digest run, not
    to escalate noise.
    """
    rolling = rolling or {}
    total = rolling.get("total_plans", 0) or 0
    rate = rolling.get("enrichment_rate") or 0.0

    metadata: dict[str, Any] = {
        "category": "silent_degradation",
        "code": "llm_enrichment_below_60pct",
        "window_days": rolling.get("window_days", 7),
        "total_plans": total,
        "llm_enriched": rolling.get("llm_enriched", 0),
        "python_fallback": rolling.get("python_fallback", 0),
        "enrichment_rate": rate,
        "top_source_reasons": rolling.get("top_source_reasons", []),
    }

    if rolling.get("query_error"):
        severity = "info"
        message = (
            f"plan_enrichment_health: rolling query error "
            f"({(rolling.get('query_error') or '')[:120]})"
        )
        metadata["query_error"] = rolling.get("query_error")
    elif total == 0:
        severity = "info"
        message = (
            f"plan_enrichment_health: no plans in last "
            f"{rolling.get('window_days', 7)} days — enrichment ratio undefined"
        )
    elif rate < _ENRICHMENT_CRITICAL_THRESHOLD:
        severity = "critical"
        message = (
            f"plan_enrichment_health: {rate * 100:.0f}% over last "
            f"{rolling.get('window_days', 7)} days "
            f"({rolling.get('llm_enriched', 0)}/{total}) — below "
            f"{int(_ENRICHMENT_CRITICAL_THRESHOLD * 100)}% critical floor"
        )
    elif rate < _ENRICHMENT_WARNING_THRESHOLD:
        severity = "warning"
        message = (
            f"plan_enrichment_health: {rate * 100:.0f}% over last "
            f"{rolling.get('window_days', 7)} days "
            f"({rolling.get('llm_enriched', 0)}/{total}) — below "
            f"{int(_ENRICHMENT_WARNING_THRESHOLD * 100)}% canary band"
        )
    else:
        severity = "info"
        message = (
            f"plan_enrichment_health: {rate * 100:.0f}% over last "
            f"{rolling.get('window_days', 7)} days "
            f"({rolling.get('llm_enriched', 0)}/{total})"
        )

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "health_monitor",
        "event_type": "plan_enrichment_health",
        "severity_hint": severity,
        "surface": "scheduled_digest",
        "route_or_job": "compute_plan_health_rolling",
        "message": message,
        # D13: explicit signature so a digest schema change can't accidentally
        # rehash this into a different bucket.
        "signature": PLAN_ENRICHMENT_SIGNATURE,
        "metadata": metadata,
    }


def _build_plan_health_observations(plan: dict | None) -> list[dict]:
    """Map today's ``compute_plan_health`` output to 0..2 observations.

    * Critical: ``plan_generation_not_shipping`` when no LLM-enriched OR fallback
      rows exist AT ALL on a day that has check-ins (no plans actually shipped).
      We use the existing per-day digest's emergency channel as the canary; we
      do NOT re-run the 3-failures-in-30-minutes detection (that already alerts
      out-of-band per CLAUDE.md).
    * Warning: high per-day python_fallback ratio (≥ 50%) on a day with at
      least 2 plans. The 7d rolling observation is the primary canary; this is
      a same-day partner for sharp regressions.
    * Info heartbeat: routine baseline summary so the digest section always has
      content on quiet days.
    """
    plan = plan or {}
    obs: list[dict] = []

    if plan.get("query_error"):
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "plan_health_query_error",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "compute_plan_health",
                "message": (
                    f"plan_health query failed: "
                    f"{(plan.get('query_error') or '')[:120]}"
                ),
                "metadata": {
                    "category": "guardian_self",
                    "code": "collector_failure",
                    "query_error": plan.get("query_error"),
                },
            }
        )
        return obs

    total = plan.get("total_plans", 0) or 0
    enriched = plan.get("llm_enriched", 0) or 0
    fallback = plan.get("python_fallback", 0) or 0
    no_plan = plan.get("no_plan", 0) or 0
    degraded = plan.get("degraded_pitchers") or []
    rate = plan.get("degradation_rate") or 0.0

    # Critical: no plans actually shipped today despite check-ins existing.
    # ``no_plan`` counts partial entries (check-in present, plan missing). If
    # everything is partial and zero plans were generated, that's the
    # `plan_generation_not_shipping` shape from classify.py.
    if total == 0 and no_plan > 0:
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "plan_generation_not_shipping",
                "severity_hint": "critical",
                "surface": "scheduled_digest",
                "route_or_job": "compute_plan_health",
                "message": (
                    f"plan_generation_not_shipping: {no_plan} check-ins logged "
                    f"with zero plans generated on {plan.get('date', '?')}"
                ),
                "metadata": {
                    "category": "silent_degradation",
                    "code": "plan_generation_not_shipping",
                    "date": plan.get("date"),
                    "checkins_without_plan": no_plan,
                    "total_plans": total,
                },
            }
        )

    # Warning: high same-day python_fallback share.
    if total >= 2 and rate >= 0.5:
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "plan_generation_degraded_today",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "compute_plan_health",
                "message": (
                    f"plan_generation_degraded_today: "
                    f"{fallback}/{total} python_fallback "
                    f"({rate * 100:.0f}%) on {plan.get('date', '?')}"
                ),
                "metadata": {
                    "category": "silent_degradation",
                    # Reusing the warning-tier signal name from classify.py so
                    # this clusters alongside the rolling-window observation
                    # when both fire on the same day.
                    "code": "llm_enrichment_below_60pct",
                    "date": plan.get("date"),
                    "total_plans": total,
                    "llm_enriched": enriched,
                    "python_fallback": fallback,
                    "degradation_rate": rate,
                    "source_reason_counts": plan.get("source_reason_counts", {}),
                    "degraded_pitchers": degraded,
                },
            }
        )

    # Info heartbeat — always present so the digest section never goes silent.
    obs.append(
        {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "health_monitor",
            "event_type": "plan_health_summary",
            "severity_hint": "info",
            "surface": "scheduled_digest",
            "route_or_job": "compute_plan_health",
            "message": (
                f"plan_health_summary: {enriched} enriched, {fallback} fallback, "
                f"{no_plan} no_plan on {plan.get('date', '?')}"
            ),
            "metadata": {
                "category": "existing_health",
                "code": "plan_health_summary",
                "date": plan.get("date"),
                "total_plans": total,
                "llm_enriched": enriched,
                "python_fallback": fallback,
                "no_plan": no_plan,
                "degradation_rate": rate,
            },
        }
    )
    return obs


def _build_whoop_observations(whoop: dict | None) -> list[dict]:
    """Map today's ``compute_whoop_health`` to 0..2 observations.

    * Warning: any linked pitcher is missing a pull (per spec §9
      `whoop_pull_missing`).
    * Info heartbeat: routine count summary.
    """
    whoop = whoop or {}
    obs: list[dict] = []

    if whoop.get("query_error"):
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "whoop_health_query_error",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "compute_whoop_health",
                "message": (
                    f"whoop_health query failed: "
                    f"{(whoop.get('query_error') or '')[:120]}"
                ),
                "metadata": {
                    "category": "guardian_self",
                    "code": "collector_failure",
                    "query_error": whoop.get("query_error"),
                },
            }
        )
        return obs

    linked = whoop.get("linked_count", 0) or 0
    pulled = whoop.get("pulled_count", 0) or 0
    missing = whoop.get("missing_pitchers") or []

    if linked == 0:
        # Nobody linked — nothing to observe.
        return obs

    if missing:
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "whoop_pull_missing",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "compute_whoop_health",
                "message": (
                    f"whoop_pull_missing: {len(missing)}/{linked} pulls missing "
                    f"on {whoop.get('date', '?')}"
                ),
                "metadata": {
                    "category": "silent_degradation",
                    "code": "whoop_pull_missing",
                    "date": whoop.get("date"),
                    "linked_count": linked,
                    "pulled_count": pulled,
                    "missing_pitchers": missing,
                },
            }
        )

    obs.append(
        {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "health_monitor",
            "event_type": "whoop_health_summary",
            "severity_hint": "info",
            "surface": "scheduled_digest",
            "route_or_job": "compute_whoop_health",
            "message": (
                f"whoop_health_summary: {pulled}/{linked} pulled on "
                f"{whoop.get('date', '?')}"
            ),
            "metadata": {
                "category": "existing_health",
                "code": "whoop_health_summary",
                "date": whoop.get("date"),
                "linked_count": linked,
                "pulled_count": pulled,
            },
        }
    )
    return obs


def _build_weekly_narrative_observations(narrative: dict | None) -> list[dict]:
    """Sunday-only: map ``compute_weekly_narrative_health`` to 0..1 obs.

    Returns ``[]`` on non-Sundays (the source function returns ``None`` then).
    """
    if not narrative:
        return []
    obs: list[dict] = []

    if narrative.get("query_error"):
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "weekly_narrative_query_error",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "compute_weekly_narrative_health",
                "message": (
                    f"weekly_narrative query failed: "
                    f"{(narrative.get('query_error') or '')[:120]}"
                ),
                "metadata": {
                    "category": "guardian_self",
                    "code": "collector_failure",
                    "query_error": narrative.get("query_error"),
                },
            }
        )
        return obs

    active = narrative.get("pitchers_with_activity", 0) or 0
    with_nar = narrative.get("pitchers_with_narrative", 0) or 0
    missing = narrative.get("missing_pitchers") or []

    if active > 0 and with_nar < active:
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "weekly_narrative_missing",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "compute_weekly_narrative_health",
                "message": (
                    f"weekly_narrative_missing: {len(missing)} pitchers "
                    f"missing weekly summary (week {narrative.get('week_start', '?')})"
                ),
                "metadata": {
                    "category": "silent_degradation",
                    "code": "weekly_narrative_missing",
                    "week_start": narrative.get("week_start"),
                    "pitchers_with_activity": active,
                    "pitchers_with_narrative": with_nar,
                    "missing_pitchers": missing,
                },
            }
        )
    return obs


def _build_qa_observations(qa: dict | None) -> list[dict]:
    """Map in-memory ``compute_qa_health`` to 0..1 observations.

    Warning when the daily error rate is ≥ 10% on a day with ≥ 3 Q&A
    interactions (matches the icon threshold in
    ``format_digest_message``). Lower volumes are too noisy to surface.
    """
    qa = qa or {}
    total = qa.get("total", 0) or 0
    errors = qa.get("errors", 0) or 0
    rate = qa.get("error_rate") or 0.0
    if total < 3 or rate < 0.10:
        return []

    return [
        {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "health_monitor",
            "event_type": "qa_error_rate_high",
            "severity_hint": "warning",
            "surface": "scheduled_digest",
            "route_or_job": "compute_qa_health",
            "message": (
                f"qa_error_rate_high: {errors}/{total} errors "
                f"({rate * 100:.0f}%) today"
            ),
            "metadata": {
                "category": "data_quality",
                "code": "qa_error_rate_high",
                "total": total,
                "successes": qa.get("successes", 0),
                "errors": errors,
                "error_rate": rate,
                "error_types": qa.get("error_types", {}),
            },
        }
    ]


def _build_collector_failure_observation(
    exc: BaseException, *, step: str
) -> dict:
    """Single ``collector_failure`` observation for the catch-all branch (A1)."""
    stack_excerpt = traceback.format_exc(limit=8)[-1500:]
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "health_monitor",
        "event_type": "collector_failure",
        "severity_hint": "warning",
        "surface": "scheduled_digest",
        "route_or_job": "collect_existing_health",
        "message": (
            f"collector_failure in existing_health.{step}: "
            f"{type(exc).__name__}: {str(exc)[:200]}"
        ),
        "stack": stack_excerpt,
        "metadata": {
            "category": "guardian_self",
            "code": "collector_failure",
            "step": step,
            "exception_class": type(exc).__name__,
        },
    }


def _derive_observations_from_digest(digest: dict, rolling: dict) -> list[dict]:
    """Compose the full observation list from the two precomputed dicts.

    Split out so a callsite that already has the digest in hand (e.g. an
    admin-triggered ``/healthcheck``) can avoid re-running ``compute_*`` and
    derive observations directly. Keeps the wiring layer focused on persistence.
    """
    observations: list[dict] = []

    # Per-day plan health.
    try:
        observations.extend(_build_plan_health_observations(digest.get("plan_health")))
    except Exception as e:
        logger.error("existing_health: plan_health derivation failed: %s", e, exc_info=True)
        observations.append(_build_collector_failure_observation(e, step="plan_health"))

    # D13 rolling plan enrichment — ALWAYS emit exactly one observation.
    try:
        observations.append(_build_plan_enrichment_observation(rolling))
    except Exception as e:
        logger.error("existing_health: plan_enrichment derivation failed: %s", e, exc_info=True)
        observations.append(
            _build_collector_failure_observation(e, step="plan_enrichment_health")
        )

    # WHOOP.
    try:
        observations.extend(_build_whoop_observations(digest.get("whoop_health")))
    except Exception as e:
        logger.error("existing_health: whoop derivation failed: %s", e, exc_info=True)
        observations.append(_build_collector_failure_observation(e, step="whoop_health"))

    # Weekly narrative (Sunday only).
    try:
        observations.extend(
            _build_weekly_narrative_observations(digest.get("weekly_narrative"))
        )
    except Exception as e:
        logger.error("existing_health: weekly_narrative derivation failed: %s", e, exc_info=True)
        observations.append(
            _build_collector_failure_observation(e, step="weekly_narrative")
        )

    # Q&A heartbeat / threshold.
    try:
        observations.extend(_build_qa_observations(digest.get("qa_health")))
    except Exception as e:
        logger.error("existing_health: qa derivation failed: %s", e, exc_info=True)
        observations.append(_build_collector_failure_observation(e, step="qa_health"))

    return observations


def _run_sync_digest() -> tuple[dict, dict]:
    """Sync entrypoint that runs both source computations under one threadpool
    handoff. Kept private so the timeout wrap stays in one place.
    """
    # Local import to dodge import-time circulars and to make tests trivial
    # to monkeypatch.
    from bot.services.health_monitor import (
        compute_daily_digest,
        compute_plan_health_rolling,
    )

    digest = compute_daily_digest()
    rolling = compute_plan_health_rolling(days=7)
    return digest, rolling


# ---------------------------------------------------------------------------
# Public coroutine
# ---------------------------------------------------------------------------


async def collect_existing_health() -> list[dict]:
    """Async collector entrypoint per A1.

    Steps:

    1. Run ``compute_daily_digest()`` + ``compute_plan_health_rolling(days=7)``
       in a threadpool, bounded by a 5s timeout.
    2. Derive observations via :func:`_derive_observations_from_digest`.
    3. On ANY error (timeout, exception in the sync block, exception in the
       derivation): return ONE ``collector_failure`` observation. Never raise.

    Returns the list of observation dicts. The wiring layer is responsible for
    calling :func:`bot.services.system_guardian.store.insert_observation` on
    each entry — collectors don't touch storage directly.
    """
    try:
        digest, rolling = await asyncio.wait_for(
            asyncio.to_thread(_run_sync_digest),
            timeout=_COLLECTOR_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error(
            "existing_health: collector exceeded %ss timeout", _COLLECTOR_TIMEOUT_S
        )
        return [
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "health_monitor",
                "event_type": "collector_failure",
                "severity_hint": "warning",
                "surface": "scheduled_digest",
                "route_or_job": "collect_existing_health",
                "message": (
                    f"collect_existing_health timed out after "
                    f"{_COLLECTOR_TIMEOUT_S}s"
                ),
                "metadata": {
                    "category": "guardian_self",
                    "code": "collector_failure",
                    "step": "wait_for",
                    "timeout_s": _COLLECTOR_TIMEOUT_S,
                },
            }
        ]
    except Exception as e:
        logger.error(
            "existing_health: collector raised in sync digest step: %s",
            e,
            exc_info=True,
        )
        return [_build_collector_failure_observation(e, step="compute_daily_digest")]

    try:
        return _derive_observations_from_digest(digest, rolling)
    except Exception as e:
        logger.error(
            "existing_health: derivation step raised: %s", e, exc_info=True
        )
        return [_build_collector_failure_observation(e, step="derive")]


__all__ = [
    "collect_existing_health",
    "PLAN_ENRICHMENT_SIGNATURE",
]
