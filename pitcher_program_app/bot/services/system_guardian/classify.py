"""Severity classification per the original spec §9.

The mapping below is intentionally conservative:

* ``critical`` — paged-immediately tier. Exposed secrets, RLS regressions,
  plan generation collapsing, auth/security failures.
* ``warning`` — surfaces in the daily digest. Degraded enrichment, advisor
  warnings, repeated collector failures.
* ``info`` — persisted but never notified outside the digest.

This is rule-based on purpose. The spec calls out "pick a sensible default
(`info`) and explicitly handle the named criticals/warnings the spec lists" —
so unknown ``(category, signal)`` pairs land at ``info`` rather than being
treated as warnings, which avoids notification storms when a new collector
ships.
"""

from __future__ import annotations

# Severity hierarchy — used both here and by incidents.upsert_incident when
# deciding whether to escalate a stored severity.
SEVERITY_RANK: dict[str, int] = {
    "info": 0,
    "warning": 1,
    "critical": 2,
}


def severity_at_least(a: str, b: str) -> bool:
    """``True`` when severity ``a`` is greater than or equal to ``b``."""
    return SEVERITY_RANK.get(a, 0) >= SEVERITY_RANK.get(b, 0)


def max_severity(a: str, b: str) -> str:
    """Return the higher-ranked of two severities."""
    if SEVERITY_RANK.get(a, 0) >= SEVERITY_RANK.get(b, 0):
        return a
    return b


# Critical signals per spec §9 — exact `signal` strings the collectors agree
# to emit. Anything that hits this list pages immediately.
_CRITICAL_SIGNALS_BY_CATEGORY: dict[str, set[str]] = {
    "security_posture": {
        "exposed_secret",
        "rls_disabled_in_public",
        "anon_grant_regression",
        "sensitive_columns_exposed",
    },
    "runtime_error": {
        "checkin_route_failure_spike",
        "auth_failure_spike",
        "telegram_unreachable",
    },
    "silent_degradation": {
        "plan_generation_below_50pct_2d",
        "plan_generation_not_shipping",
    },
    "database_error": {
        "supabase_unavailable",
        "migration_broke_dashboard",
    },
    "llm_degradation": {
        "llm_provider_down",
    },
}

# Warning-tier signals per spec §9.
_WARNING_SIGNALS_BY_CATEGORY: dict[str, set[str]] = {
    "silent_degradation": {
        "llm_enrichment_below_60pct",
        "whoop_pull_missing",
        "weekly_narrative_missing",
        "frontend_fallback_repeated",
    },
    "llm_degradation": {
        "llm_enrichment_below_60pct",
    },
    "security_posture": {
        "advisor_lint_warning",
    },
    "guardian_self": {
        "collector_failure_repeated",
        "tick_budget_exceeded",
    },
    "data_quality": {
        "qa_error_rate_high",
    },
    "frontend_degradation": {
        "fallback_render_repeated",
    },
}


def classify_severity(category: str, signal: str | None = None) -> str:
    """Return ``critical | warning | info`` for a (category, signal) pair.

    ``signal`` is a short stable token the collectors agree on (e.g.
    ``llm_enrichment_below_60pct``). When absent, we fall back to ``info`` —
    notification policy must be conservative for unknown shapes.
    """
    if signal is None:
        return "info"

    crit = _CRITICAL_SIGNALS_BY_CATEGORY.get(category, set())
    if signal in crit:
        return "critical"

    warn = _WARNING_SIGNALS_BY_CATEGORY.get(category, set())
    if signal in warn:
        return "warning"

    return "info"


__all__ = [
    "SEVERITY_RANK",
    "classify_severity",
    "max_severity",
    "severity_at_least",
]
