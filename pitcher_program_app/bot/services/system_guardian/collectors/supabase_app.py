"""``supabase_app`` collector — Phase 1 telemetry queries against the app's
own Supabase tables.

Per amendments doc §2 A2: this is the **Phase 1** Supabase collector. It uses
the existing ``SUPABASE_SERVICE_KEY`` via :func:`bot.services.db.get_client`.
The Phase 2 management-API collector (`supabase_mgmt`) is gated on a new
``SUPABASE_ACCESS_TOKEN`` env var and ships in PR-7+.

Signals produced:

* ``daily_entries_stale``        — count of rows for ``date >= today - 1d``
  that have a check-in (``pre_training.arm_feel`` set) but no
  ``plan_generated``. Warning when > 3.
* ``research_load_anomaly``      — last-24h aggregate against
  ``research_load_log``: total calls, share that were degraded, mean
  injection length. Warning when degraded share > 25% (any signal) OR
  mean ``total_chars`` > 8000 (LLM regression canary — see CLAUDE.md
  "LLM enrichment depends on a 45s budget").
* ``ui_fallback_log_spike``      — count rows in last 24h of
  ``ui_fallback_log``. Warning when > 10 in 24h.
* ``whoop_daily_freshness``      — per-pitcher: linked in ``whoop_tokens``
  but no ``whoop_daily`` row for today. One warning observation per missing
  pitcher (matches the per-pitcher granularity that ``health_monitor``
  surfaces in ``compute_whoop_health``).
* ``supabase_app_heartbeat``     — info observation summarizing the run
  ("queried 4 tables, X anomalies, Y rows scanned") so a healthy collector
  always leaves a footprint.

Schema-drift defense (CLAUDE.md "Schema drift in team_scope.py / team daily
status selects"): ``daily_entries`` selects stay on the production-safe
columns: ``pitcher_id, date, team_id, pre_training, plan_generated``.

Failure semantics (A1):

* Each table query lives in its own try/except. If one raises, that signal
  becomes a ``signal_failure`` info-level note and OTHER signals still
  produce. Schema drift on one table never poisons the whole collector.
* If :func:`bot.services.db.get_client` itself raises (no Supabase
  credentials, etc.), the collector returns ONE ``collector_failure``
  observation. Never re-raises.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import date as _date, datetime, timedelta, timezone
from typing import Any

from bot.config import CHICAGO_TZ

logger = logging.getLogger(__name__)

# A1: per-collector timeout ceiling.
_COLLECTOR_TIMEOUT_S = 5.0

# Sentinel source string for traceability.
_SOURCE = "supabase_app.collect_supabase_app"

# Thresholds.
_DAILY_ENTRIES_STALE_WARN = 3
_RESEARCH_DEGRADED_RATE_WARN = 0.25
_RESEARCH_INJECTION_CHARS_WARN = 8000
_UI_FALLBACK_24H_WARN = 10

# Production-safe column list for `daily_entries` (CLAUDE.md).
_DAILY_ENTRIES_COLUMNS = "pitcher_id, date, team_id, pre_training, plan_generated"


def _now_iso() -> str:
    return datetime.now(CHICAGO_TZ).isoformat()


def _chicago_today_str() -> str:
    return datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")


def _utc_iso_n_hours_ago(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# Pure builders + per-signal queries.
# ---------------------------------------------------------------------------


def _signal_failure_obs(*, signal: str, exc: BaseException) -> dict:
    """Per-signal isolation: one query raised but others should still run.

    Emit an info-level note so the wiring layer can still cluster on signature.
    """
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": f"{signal}_query_failed",
        "severity_hint": "info",
        "surface": "scheduled_collector",
        "route_or_job": f"supabase_app.{signal}",
        "message": (
            f"{signal} query failed: {type(exc).__name__}: {str(exc)[:200]}"
        ),
        "metadata": {
            "category": "guardian_self",
            "code": "signal_failure",
            "signal": signal,
            "exception_class": type(exc).__name__,
        },
    }


def _build_collector_failure_observation(exc: BaseException, *, step: str) -> dict:
    stack_excerpt = traceback.format_exc(limit=8)[-1500:]
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "collector_failure",
        "severity_hint": "warning",
        "surface": "guardian_self",
        "route_or_job": "collect_supabase_app",
        "message": (
            f"collector_failure in supabase_app.{step}: "
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


# -- daily_entries_stale ----------------------------------------------------


def _query_daily_entries_stale(client) -> list[dict]:
    """Pull check-ins from today + yesterday and count partials (no plan).

    Uses only production-safe columns per CLAUDE.md schema-drift guard.
    """
    today_str = _chicago_today_str()
    yesterday_str = (
        _date.fromisoformat(today_str) - timedelta(days=1)
    ).isoformat()

    resp = (
        client.table("daily_entries")
        .select(_DAILY_ENTRIES_COLUMNS)
        .gte("date", yesterday_str)
        .lte("date", today_str)
        .execute()
    )
    return resp.data or []


def _build_daily_entries_stale_observation(rows: list[dict]) -> dict:
    stale = []
    for row in rows or []:
        pre = row.get("pre_training") or {}
        if not isinstance(pre, dict):
            continue
        # Has a check-in iff pre_training.arm_feel is non-null (per
        # team_daily_status contract in CLAUDE.md).
        if pre.get("arm_feel") is None:
            continue
        if not row.get("plan_generated"):
            stale.append({"pitcher_id": row.get("pitcher_id"), "date": row.get("date")})

    if len(stale) > _DAILY_ENTRIES_STALE_WARN:
        severity = "warning"
        message = (
            f"daily_entries_stale: {len(stale)} check-ins missing plan_generated "
            f"in last 2 days (threshold {_DAILY_ENTRIES_STALE_WARN})"
        )
        category = "silent_degradation"
    else:
        severity = "info"
        message = (
            f"daily_entries_stale: {len(stale)} stale in last 2 days "
            f"(under threshold {_DAILY_ENTRIES_STALE_WARN})"
        )
        category = "existing_health"

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "daily_entries_stale",
        "severity_hint": severity,
        "surface": "scheduled_collector",
        "route_or_job": "supabase_app.daily_entries_stale",
        "message": message,
        "metadata": {
            "category": category,
            "code": "daily_entries_stale",
            "stale_count": len(stale),
            "threshold": _DAILY_ENTRIES_STALE_WARN,
            "stale_pitchers": [s for s in stale][:20],  # bound the list
        },
    }


# -- research_load_anomaly --------------------------------------------------


def _query_research_load_log_24h(client) -> list[dict]:
    cutoff = _utc_iso_n_hours_ago(24)
    resp = (
        client.table("research_load_log")
        .select("pitcher_id, context, trigger_reason, total_chars, degraded, created_at")
        .gte("created_at", cutoff)
        .execute()
    )
    return resp.data or []


def _build_research_load_anomaly_observation(rows: list[dict]) -> dict:
    rows = rows or []
    total = len(rows)
    if total == 0:
        return {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "supabase",
            "event_type": "research_load_anomaly",
            "severity_hint": "info",
            "surface": "scheduled_collector",
            "route_or_job": "supabase_app.research_load_anomaly",
            "message": "research_load_anomaly: zero research calls logged in last 24h",
            "metadata": {
                "category": "existing_health",
                "code": "research_load_anomaly",
                "total_calls_24h": 0,
                "degraded_count": 0,
                "degraded_rate": 0.0,
                "mean_total_chars": 0,
            },
        }

    degraded_count = sum(1 for r in rows if r.get("degraded"))
    degraded_rate = degraded_count / total if total else 0.0
    chars_values = [r.get("total_chars") or 0 for r in rows]
    mean_chars = sum(chars_values) / len(chars_values) if chars_values else 0

    is_anomaly = (
        degraded_rate > _RESEARCH_DEGRADED_RATE_WARN
        or mean_chars > _RESEARCH_INJECTION_CHARS_WARN
    )
    severity = "warning" if is_anomaly else "info"
    category = "llm_degradation" if is_anomaly else "existing_health"

    message = (
        f"research_load_anomaly: {total} calls, "
        f"{degraded_count} degraded ({degraded_rate * 100:.0f}%), "
        f"mean injection {mean_chars:.0f} chars"
    )
    if is_anomaly:
        message += " — over threshold"

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "research_load_anomaly",
        "severity_hint": severity,
        "surface": "scheduled_collector",
        "route_or_job": "supabase_app.research_load_anomaly",
        "message": message,
        "metadata": {
            "category": category,
            "code": "research_load_anomaly",
            "total_calls_24h": total,
            "degraded_count": degraded_count,
            "degraded_rate": degraded_rate,
            "mean_total_chars": mean_chars,
            "degraded_rate_threshold": _RESEARCH_DEGRADED_RATE_WARN,
            "injection_chars_threshold": _RESEARCH_INJECTION_CHARS_WARN,
        },
    }


# -- ui_fallback_log_spike --------------------------------------------------


def _query_ui_fallback_log_24h(client) -> list[dict]:
    cutoff = _utc_iso_n_hours_ago(24)
    resp = (
        client.table("ui_fallback_log")
        .select("id, exercise_id, surface, component, pitcher_id, logged_at")
        .gte("logged_at", cutoff)
        .execute()
    )
    return resp.data or []


def _build_ui_fallback_spike_observation(rows: list[dict]) -> dict:
    rows = rows or []
    count = len(rows)

    by_exercise: dict[str, int] = {}
    for r in rows:
        ex = r.get("exercise_id") or "unknown"
        by_exercise[ex] = by_exercise.get(ex, 0) + 1
    top_exercises = sorted(by_exercise.items(), key=lambda kv: -kv[1])[:5]

    if count > _UI_FALLBACK_24H_WARN:
        severity = "warning"
        category = "frontend_degradation"
        message = (
            f"ui_fallback_log_spike: {count} fallbacks in last 24h "
            f"(threshold {_UI_FALLBACK_24H_WARN})"
        )
    else:
        severity = "info"
        category = "existing_health"
        message = (
            f"ui_fallback_log_spike: {count} fallbacks in last 24h "
            f"(under threshold {_UI_FALLBACK_24H_WARN})"
        )

    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "ui_fallback_log_spike",
        "severity_hint": severity,
        "surface": "scheduled_collector",
        "route_or_job": "supabase_app.ui_fallback_log_spike",
        "message": message,
        "metadata": {
            "category": category,
            "code": "ui_fallback_log_spike",
            "count_24h": count,
            "threshold": _UI_FALLBACK_24H_WARN,
            "top_exercises": top_exercises,
        },
    }


# -- whoop_daily_freshness -------------------------------------------------


def _query_whoop_linked_pitchers(client) -> list[str]:
    resp = client.table("whoop_tokens").select("pitcher_id").execute()
    return [r["pitcher_id"] for r in (resp.data or []) if r.get("pitcher_id")]


def _query_whoop_daily_pulled_today(client, today_str: str) -> set[str]:
    resp = (
        client.table("whoop_daily")
        .select("pitcher_id, date")
        .eq("date", today_str)
        .execute()
    )
    return {r["pitcher_id"] for r in (resp.data or []) if r.get("pitcher_id")}


def _build_whoop_freshness_observations(
    *, linked: list[str], pulled: set[str], today_str: str
) -> list[dict]:
    """One warning per missing pitcher + one info heartbeat at the end."""
    obs: list[dict] = []
    missing = [pid for pid in linked if pid not in pulled]

    for pid in missing:
        obs.append(
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "supabase",
                "event_type": "whoop_daily_freshness",
                "severity_hint": "warning",
                "surface": "scheduled_collector",
                "route_or_job": "supabase_app.whoop_daily_freshness",
                "message": (
                    f"whoop_daily_freshness: {pid} has no whoop_daily row for {today_str}"
                ),
                "metadata": {
                    "category": "external_integration",
                    "code": "whoop_pull_missing",
                    "pitcher_id": pid,
                    "date": today_str,
                    "linked_count": len(linked),
                    "pulled_count": len(pulled),
                },
            }
        )

    obs.append(
        {
            "observed_at": _now_iso(),
            "source": _SOURCE,
            "service": "supabase",
            "event_type": "whoop_daily_freshness_summary",
            "severity_hint": "info",
            "surface": "scheduled_collector",
            "route_or_job": "supabase_app.whoop_daily_freshness",
            "message": (
                f"whoop_daily_freshness_summary: {len(pulled)}/{len(linked)} "
                f"linked pitchers pulled today ({today_str})"
            ),
            "metadata": {
                "category": "existing_health",
                "code": "whoop_daily_freshness_summary",
                "linked_count": len(linked),
                "pulled_count": len(pulled),
                "missing_count": len(missing),
                "date": today_str,
            },
        }
    )
    return obs


# -- heartbeat -------------------------------------------------------------


def _build_heartbeat_observation(
    *, queried: int, anomalies: int, total_rows: int
) -> dict:
    return {
        "observed_at": _now_iso(),
        "source": _SOURCE,
        "service": "supabase",
        "event_type": "supabase_app_heartbeat",
        "severity_hint": "info",
        "surface": "scheduled_collector",
        "route_or_job": "supabase_app.heartbeat",
        "message": (
            f"supabase_app_heartbeat: queried {queried} telemetry tables, "
            f"{anomalies} anomalies, {total_rows} total rows scanned"
        ),
        "metadata": {
            "category": "existing_health",
            "code": "supabase_app_heartbeat",
            "tables_queried": queried,
            "anomalies": anomalies,
            "total_rows_scanned": total_rows,
        },
    }


# ---------------------------------------------------------------------------
# Sync worker — runs all four table queries inside one threadpool handoff.
# ---------------------------------------------------------------------------


def _run_sync_collect() -> list[dict]:
    """All four table queries + builders. Catches per-signal errors so a
    schema-drift surprise on one table doesn't poison the others.

    Returns the full observation list. If :func:`get_client` raises (no env
    creds), this raises — the outer ``collect_supabase_app`` wrap catches it
    and emits one ``collector_failure`` observation.
    """
    from bot.services.db import get_client  # lazy import for test-time patching

    client = get_client()
    observations: list[dict] = []
    anomalies = 0
    total_rows = 0
    tables_queried = 0

    # daily_entries_stale ---------------------------------------------------
    try:
        rows = _query_daily_entries_stale(client) or []
        total_rows += len(rows)
        tables_queried += 1
        obs = _build_daily_entries_stale_observation(rows)
        observations.append(obs)
        if obs["severity_hint"] == "warning":
            anomalies += 1
    except Exception as e:
        logger.error("supabase_app: daily_entries_stale query failed: %s", e, exc_info=True)
        observations.append(_signal_failure_obs(signal="daily_entries_stale", exc=e))

    # research_load_anomaly -------------------------------------------------
    try:
        rows = _query_research_load_log_24h(client) or []
        total_rows += len(rows)
        tables_queried += 1
        obs = _build_research_load_anomaly_observation(rows)
        observations.append(obs)
        if obs["severity_hint"] == "warning":
            anomalies += 1
    except Exception as e:
        logger.error("supabase_app: research_load_anomaly query failed: %s", e, exc_info=True)
        observations.append(_signal_failure_obs(signal="research_load_anomaly", exc=e))

    # ui_fallback_log_spike -------------------------------------------------
    try:
        rows = _query_ui_fallback_log_24h(client) or []
        total_rows += len(rows)
        tables_queried += 1
        obs = _build_ui_fallback_spike_observation(rows)
        observations.append(obs)
        if obs["severity_hint"] == "warning":
            anomalies += 1
    except Exception as e:
        logger.error("supabase_app: ui_fallback_log_spike query failed: %s", e, exc_info=True)
        observations.append(_signal_failure_obs(signal="ui_fallback_log_spike", exc=e))

    # whoop_daily_freshness -------------------------------------------------
    today_str = _chicago_today_str()
    try:
        linked = _query_whoop_linked_pitchers(client)
        total_rows += len(linked)
        tables_queried += 1
        pulled: set[str] | None
        try:
            pulled = _query_whoop_daily_pulled_today(client, today_str)
            total_rows += len(pulled)
            tables_queried += 1
        except Exception as e:
            logger.error("supabase_app: whoop_daily query failed: %s", e, exc_info=True)
            observations.append(_signal_failure_obs(signal="whoop_daily_freshness", exc=e))
            # Skip the per-pitcher warnings on partial failure; the signal
            # failure obs above already captures the gap.
            pulled = None

        if pulled is not None:
            whoop_obs = _build_whoop_freshness_observations(
                linked=linked, pulled=pulled, today_str=today_str
            )
            observations.extend(whoop_obs)
            anomalies += sum(1 for o in whoop_obs if o["severity_hint"] == "warning")
    except Exception as e:
        logger.error(
            "supabase_app: whoop_daily_freshness query failed: %s", e, exc_info=True
        )
        observations.append(_signal_failure_obs(signal="whoop_daily_freshness", exc=e))

    # heartbeat -------------------------------------------------------------
    observations.append(
        _build_heartbeat_observation(
            queried=tables_queried, anomalies=anomalies, total_rows=total_rows
        )
    )

    return observations


# ---------------------------------------------------------------------------
# Public coroutine
# ---------------------------------------------------------------------------


async def collect_supabase_app() -> list[dict]:
    """Async collector entrypoint per A1.

    Wraps the sync table-query block in ``asyncio.to_thread`` and bounds it
    with a 5s ``asyncio.wait_for``. On timeout or top-level exception
    (e.g. ``get_client()`` blows up due to missing env), returns ONE
    ``collector_failure`` observation. Per-signal failures inside the sync
    block already produce their own ``signal_failure`` info notes; the
    catastrophic catch-all is for when the whole client is unreachable.

    Never raises.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_run_sync_collect),
            timeout=_COLLECTOR_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.error(
            "supabase_app: collector exceeded %ss timeout", _COLLECTOR_TIMEOUT_S
        )
        return [
            {
                "observed_at": _now_iso(),
                "source": _SOURCE,
                "service": "supabase",
                "event_type": "collector_failure",
                "severity_hint": "warning",
                "surface": "guardian_self",
                "route_or_job": "collect_supabase_app",
                "message": (
                    f"collect_supabase_app timed out after {_COLLECTOR_TIMEOUT_S}s"
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
        logger.error("supabase_app: collector raised: %s", e, exc_info=True)
        return [_build_collector_failure_observation(e, step="run_sync_collect")]


__all__ = ["collect_supabase_app"]
