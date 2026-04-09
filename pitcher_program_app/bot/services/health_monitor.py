"""Silent degradation monitoring — queries Supabase for health signals.

Stateless by design. All functions take a date and return a dict.
No module-level state. Composed by send_daily_digest() into a Telegram message.
"""

import logging
from datetime import datetime, timedelta
from bot.config import CHICAGO_TZ
from bot.services import db as _db

logger = logging.getLogger(__name__)


def _today_iso() -> str:
    return datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d")


def compute_plan_health(date: str = None) -> dict:
    """Count plan_generated.source values across today's daily_entries.

    Returns:
        {
            "date": "2026-04-09",
            "total_plans": 10,
            "llm_enriched": 9,
            "python_fallback": 1,
            "no_plan": 2,         # partial entries where plan gen didn't run
            "degradation_rate": 0.10,  # python_fallback / total_plans
            "source_reason_counts": {"llm_timeout:TimeoutError": 1},
            "degraded_pitchers": ["pitcher_wilson_001"],
        }
    """
    if date is None:
        date = _today_iso()

    try:
        entries = _db.get_client().table("daily_entries").select(
            "pitcher_id, plan_generated"
        ).eq("date", date).execute().data or []
    except Exception as e:
        logger.error(f"health_monitor: failed to query daily_entries for {date}: {e}")
        return {
            "date": date, "total_plans": 0, "llm_enriched": 0,
            "python_fallback": 0, "no_plan": 0, "degradation_rate": 0.0,
            "source_reason_counts": {}, "degraded_pitchers": [],
            "query_error": str(e),
        }

    llm_enriched = 0
    python_fallback = 0
    no_plan = 0
    source_reason_counts = {}
    degraded_pitchers = []

    for entry in entries:
        plan_gen = entry.get("plan_generated") or {}
        source = plan_gen.get("source")
        if source == "llm_enriched":
            llm_enriched += 1
        elif source == "python_fallback":
            python_fallback += 1
            reason = plan_gen.get("source_reason") or "unknown"
            source_reason_counts[reason] = source_reason_counts.get(reason, 0) + 1
            degraded_pitchers.append(entry.get("pitcher_id"))
        else:
            # source is None → partial entry (check-in saved, plan didn't ship)
            # OR this is an old row from before source tagging (pre-2026-04-09)
            no_plan += 1

    total = llm_enriched + python_fallback
    rate = (python_fallback / total) if total > 0 else 0.0

    return {
        "date": date,
        "total_plans": total,
        "llm_enriched": llm_enriched,
        "python_fallback": python_fallback,
        "no_plan": no_plan,
        "degradation_rate": rate,
        "source_reason_counts": source_reason_counts,
        "degraded_pitchers": degraded_pitchers,
    }


def compute_whoop_health(date: str = None) -> dict:
    """Check which linked pitchers have a whoop_daily row for today.

    Returns:
        {
            "date": "2026-04-09",
            "linked_count": 4,
            "pulled_count": 3,
            "missing_pitchers": ["pitcher_richert_001"],
        }
    """
    if date is None:
        date = _today_iso()

    try:
        linked = _db.list_whoop_linked_pitchers() or []
    except Exception as e:
        logger.error(f"health_monitor: failed to list_whoop_linked_pitchers: {e}")
        return {"date": date, "linked_count": 0, "pulled_count": 0,
                "missing_pitchers": [], "query_error": str(e)}

    pulled = []
    missing = []
    for pitcher_id in linked:
        try:
            resp = (_db.get_client().table("whoop_daily")
                    .select("pitcher_id")
                    .eq("pitcher_id", pitcher_id)
                    .eq("date", date)
                    .execute())
            if resp.data:
                pulled.append(pitcher_id)
            else:
                missing.append(pitcher_id)
        except Exception:
            missing.append(pitcher_id)

    return {
        "date": date,
        "linked_count": len(linked),
        "pulled_count": len(pulled),
        "missing_pitchers": missing,
    }


def compute_weekly_narrative_health() -> dict | None:
    """Check if this week's weekly_summaries are present (Sunday check only).

    Returns None on non-Sundays. Otherwise a dict with pitcher activity + narrative counts.
    """
    now = datetime.now(CHICAGO_TZ)
    # weekday: Monday=0, Sunday=6
    if now.weekday() != 6:
        return None  # Not Sunday — skip

    monday = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    try:
        # Any pitcher who logged activity this week
        active_entries = (_db.get_client().table("daily_entries")
                          .select("pitcher_id")
                          .gte("date", monday)
                          .execute().data) or []
        active_pitchers = set(e["pitcher_id"] for e in active_entries)

        # Who has a weekly_summaries row for this week
        narrative_rows = (_db.get_client().table("weekly_summaries")
                          .select("pitcher_id")
                          .eq("week_start", monday)
                          .execute().data) or []
        pitchers_with_narrative = set(r["pitcher_id"] for r in narrative_rows)
    except Exception as e:
        logger.error(f"health_monitor: failed weekly narrative check: {e}")
        return {"week_start": monday, "pitchers_with_activity": 0,
                "pitchers_with_narrative": 0, "missing_pitchers": [],
                "query_error": str(e)}

    missing = sorted(active_pitchers - pitchers_with_narrative)
    return {
        "week_start": monday,
        "pitchers_with_activity": len(active_pitchers),
        "pitchers_with_narrative": len(pitchers_with_narrative),
        "missing_pitchers": missing,
    }


def compute_daily_digest(date: str = None) -> dict:
    """Compose the full daily health snapshot."""
    return {
        "plan_health": compute_plan_health(date),
        "whoop_health": compute_whoop_health(date),
        "weekly_narrative": compute_weekly_narrative_health(),
        "qa_health": compute_qa_health(),
    }


def format_digest_message(digest: dict) -> str:
    """Format the digest dict as a Telegram message.

    Uses simple text (no markdown parse mode) to avoid escaping issues.
    """
    lines = []
    plan = digest.get("plan_health", {})
    whoop = digest.get("whoop_health", {})
    narrative = digest.get("weekly_narrative")

    date = plan.get("date", "?")
    lines.append(f"🩺 Pitcher Bot Health — {date}")
    lines.append("")

    # Plan generation section
    total = plan.get("total_plans", 0)
    enriched = plan.get("llm_enriched", 0)
    fallback = plan.get("python_fallback", 0)
    rate = plan.get("degradation_rate", 0.0)

    if plan.get("query_error"):
        lines.append(f"⚠️ Plan query failed: {plan['query_error'][:100]}")
    elif total == 0:
        lines.append("📋 Plans: no check-ins logged yet today")
    else:
        icon = "✅" if rate == 0 else ("🟡" if rate < 0.3 else "🔴")
        lines.append(f"{icon} Plans: {enriched}/{total} enriched "
                     f"({fallback} fallback, {rate*100:.0f}% degraded)")
        if plan.get("source_reason_counts"):
            for reason, count in sorted(plan["source_reason_counts"].items(),
                                        key=lambda x: -x[1]):
                lines.append(f"     • {count}× {reason}")
        if plan.get("degraded_pitchers"):
            ids = ", ".join(plan["degraded_pitchers"][:5])
            suffix = f" (+{len(plan['degraded_pitchers'])-5} more)" if len(plan["degraded_pitchers"]) > 5 else ""
            lines.append(f"     Affected: {ids}{suffix}")

    # WHOOP section
    linked = whoop.get("linked_count", 0)
    pulled = whoop.get("pulled_count", 0)

    if whoop.get("query_error"):
        lines.append(f"⚠️ WHOOP query failed: {whoop['query_error'][:100]}")
    elif linked == 0:
        pass  # nobody linked — skip
    else:
        icon = "✅" if pulled == linked else "🟡"
        lines.append(f"{icon} WHOOP: {pulled}/{linked} pulled today")
        if whoop.get("missing_pitchers"):
            ids = ", ".join(whoop["missing_pitchers"])
            lines.append(f"     Missing: {ids}")

    # Q&A section
    qa = digest.get("qa_health") or {}
    if qa.get("total", 0) > 0:
        err_rate = qa.get("error_rate", 0.0)
        icon = "✅" if err_rate == 0 else ("🟡" if err_rate < 0.1 else "🔴")
        lines.append(
            f"{icon} Q&A: {qa['successes']}/{qa['total']} ok "
            f"({qa['errors']} errors, {err_rate*100:.0f}% fail rate)"
        )
        if qa.get("error_types"):
            for etype, count in sorted(qa["error_types"].items(), key=lambda x: -x[1]):
                lines.append(f"     • {count}× {etype}")

    # Weekly narrative section (Sunday only)
    if narrative:
        active = narrative.get("pitchers_with_activity", 0)
        with_nar = narrative.get("pitchers_with_narrative", 0)
        if narrative.get("query_error"):
            lines.append(f"⚠️ Narrative query failed: {narrative['query_error'][:100]}")
        elif active == 0:
            pass
        else:
            icon = "✅" if with_nar == active else "🟡"
            lines.append(f"{icon} Weekly narratives: {with_nar}/{active} written")
            if narrative.get("missing_pitchers"):
                ids = ", ".join(narrative["missing_pitchers"][:5])
                lines.append(f"     Missing: {ids}")

    lines.append("")
    lines.append("Reply /healthcheck any time for on-demand status (v3).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# V3 — Q&A tracking (in-memory, resets at midnight Chicago)
# ---------------------------------------------------------------------------

# Q&A errors don't persist to Supabase — they bubble up as generic error
# messages and disappear into Railway logs. We keep an in-memory counter
# so the daily digest can surface Q&A health.
_QA_STATE = {
    "errors_today": [],           # [(timestamp, pitcher_id, error_type), ...]
    "successes_today": 0,         # counter
    "last_reset_date": None,      # Chicago ISO date string
}


def _maybe_reset_qa_state() -> None:
    """Reset Q&A state if we've crossed into a new Chicago day."""
    today = _today_iso()
    if _QA_STATE["last_reset_date"] != today:
        _QA_STATE["errors_today"] = []
        _QA_STATE["successes_today"] = 0
        _QA_STATE["last_reset_date"] = today


def record_qa_success(pitcher_id: str = None) -> None:
    """Increment the Q&A success counter. Never raises."""
    try:
        _maybe_reset_qa_state()
        _QA_STATE["successes_today"] += 1
    except Exception as e:
        logger.error(f"record_qa_success failed: {e}")


def record_qa_error(pitcher_id: str, error_type: str) -> None:
    """Record a Q&A error. Never raises."""
    try:
        _maybe_reset_qa_state()
        _QA_STATE["errors_today"].append(
            (datetime.now(CHICAGO_TZ), pitcher_id, error_type)
        )
    except Exception as e:
        logger.error(f"record_qa_error failed: {e}")


def compute_qa_health() -> dict:
    """Summarize today's Q&A activity."""
    try:
        _maybe_reset_qa_state()
    except Exception:
        pass
    errors = _QA_STATE.get("errors_today") or []
    successes = _QA_STATE.get("successes_today") or 0
    total = successes + len(errors)
    rate = (len(errors) / total) if total > 0 else 0.0
    error_types = {}
    for _, _, etype in errors:
        error_types[etype] = error_types.get(etype, 0) + 1
    return {
        "total": total,
        "successes": successes,
        "errors": len(errors),
        "error_rate": rate,
        "error_types": error_types,
    }


# ---------------------------------------------------------------------------
# V2 — Real-time emergency detection
# ---------------------------------------------------------------------------

# In-memory emergency state (resets on Railway restart — acceptable loss).
# Worst case after restart: one re-alert on the next matching failure.
_EMERGENCY_STATE = {
    "recent_failures": [],           # [(timestamp, source_reason, pitcher_id), ...]
    "last_alert_times": {},          # {pattern: timestamp}
}

# Failure patterns that should trigger immediate alerts.
# Substring matching against source_reason strings.
EMERGENCY_PATTERNS = (
    "APIStatusError",
    "APIError",
    "AuthenticationError",
    "PermissionDeniedError",
    "InsufficientBalance",
    "insufficient_balance",
    "RateLimitError",
    "rate_limit",
)

# Thresholds
EMERGENCY_THRESHOLD = 3           # failures of same pattern to trigger
EMERGENCY_WINDOW_MIN = 30         # within N minutes
DEDUP_WINDOW_HOURS = 2            # don't re-alert for same pattern within N hours


def _matches_emergency_pattern(source_reason: str) -> str | None:
    """Return the matched pattern name if source_reason contains a known bad signal."""
    if not source_reason:
        return None
    for pattern in EMERGENCY_PATTERNS:
        if pattern in source_reason:
            return pattern
    return None


def record_and_check_emergency(source_reason: str, pitcher_id: str = None) -> dict | None:
    """Record a plan-gen failure and return alert info if threshold crossed.

    Never raises. Safe to call from sync code — no I/O.

    Args:
        source_reason: The `source_reason` string from plan_generator.
        pitcher_id: Optional — which pitcher triggered this failure.

    Returns:
        None if no alert should fire, else a dict:
            {"pattern": "APIStatusError", "count": 3, "window_min": 30,
             "reasons": [...], "pitchers": [...]}
    """
    try:
        pattern = _matches_emergency_pattern(source_reason)
        if not pattern:
            return None

        now = datetime.now(CHICAGO_TZ)
        # Prune stale entries outside the detection window
        cutoff = now - timedelta(minutes=EMERGENCY_WINDOW_MIN)
        _EMERGENCY_STATE["recent_failures"] = [
            (ts, reason, pid)
            for (ts, reason, pid) in _EMERGENCY_STATE["recent_failures"]
            if ts > cutoff
        ]
        # Record this failure
        _EMERGENCY_STATE["recent_failures"].append((now, source_reason, pitcher_id))

        # Count matches for this specific pattern
        matches = [
            (ts, reason, pid) for (ts, reason, pid)
            in _EMERGENCY_STATE["recent_failures"]
            if pattern in reason
        ]
        if len(matches) < EMERGENCY_THRESHOLD:
            return None

        # Check dedup window
        last_alert = _EMERGENCY_STATE["last_alert_times"].get(pattern)
        if last_alert and (now - last_alert) < timedelta(hours=DEDUP_WINDOW_HOURS):
            return None  # Already alerted recently

        # Fire the alert
        _EMERGENCY_STATE["last_alert_times"][pattern] = now
        return {
            "pattern": pattern,
            "count": len(matches),
            "window_min": EMERGENCY_WINDOW_MIN,
            "reasons": list({reason for _, reason, _ in matches}),
            "pitchers": list({pid for _, _, pid in matches if pid}),
        }
    except Exception as e:
        logger.error(f"record_and_check_emergency failed: {e}", exc_info=True)
        return None


def format_emergency_alert(alert: dict) -> str:
    """Format an emergency alert dict as a Telegram message."""
    lines = [
        "🚨 Pitcher Bot Emergency",
        "",
        f"Pattern: {alert.get('pattern', '?')}",
        f"Failures: {alert.get('count', 0)} in last {alert.get('window_min', 0)} min",
    ]
    pitchers = alert.get("pitchers") or []
    if pitchers:
        preview = ", ".join(pitchers[:5])
        suffix = f" (+{len(pitchers)-5} more)" if len(pitchers) > 5 else ""
        lines.append(f"Affected pitchers: {preview}{suffix}")
    reasons = alert.get("reasons") or []
    if reasons:
        lines.append("")
        lines.append("Reasons:")
        for r in reasons[:3]:
            lines.append(f"  • {r[:100]}")
    lines.append("")
    lines.append("Likely cause: DeepSeek billing / auth / rate limit.")
    lines.append("Check platform.deepseek.com")
    return "\n".join(lines)
