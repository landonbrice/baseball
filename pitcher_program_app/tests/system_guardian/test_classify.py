"""Tests for severity classification per spec §9."""

from __future__ import annotations

from bot.services.system_guardian.classify import (
    SEVERITY_RANK,
    classify_severity,
    max_severity,
    severity_at_least,
)


# ---------------------------------------------------------------------------
# Explicit critical signals
# ---------------------------------------------------------------------------

def test_exposed_secret_is_critical():
    assert classify_severity("security_posture", "exposed_secret") == "critical"


def test_rls_regression_is_critical():
    assert classify_severity("security_posture", "rls_disabled_in_public") == "critical"


def test_anon_grant_regression_is_critical():
    assert classify_severity("security_posture", "anon_grant_regression") == "critical"


def test_checkin_route_failure_spike_is_critical():
    assert classify_severity("runtime_error", "checkin_route_failure_spike") == "critical"


def test_auth_failure_spike_is_critical():
    assert classify_severity("runtime_error", "auth_failure_spike") == "critical"


def test_plan_generation_below_50pct_2d_is_critical():
    assert (
        classify_severity("silent_degradation", "plan_generation_below_50pct_2d")
        == "critical"
    )


def test_supabase_unavailable_is_critical():
    assert classify_severity("database_error", "supabase_unavailable") == "critical"


# ---------------------------------------------------------------------------
# Explicit warning signals
# ---------------------------------------------------------------------------

def test_llm_enrichment_below_60pct_is_warning():
    assert (
        classify_severity("silent_degradation", "llm_enrichment_below_60pct")
        == "warning"
    )


def test_advisor_lint_warning_is_warning():
    assert classify_severity("security_posture", "advisor_lint_warning") == "warning"


def test_collector_failure_repeated_is_warning():
    assert (
        classify_severity("guardian_self", "collector_failure_repeated") == "warning"
    )


def test_whoop_pull_missing_is_warning():
    assert classify_severity("silent_degradation", "whoop_pull_missing") == "warning"


# ---------------------------------------------------------------------------
# Defaults / unknown
# ---------------------------------------------------------------------------

def test_unknown_signal_defaults_to_info():
    assert classify_severity("runtime_error", "completely_made_up_signal") == "info"


def test_unknown_category_defaults_to_info():
    assert classify_severity("alien_category", "exposed_secret") == "info"


def test_missing_signal_defaults_to_info():
    assert classify_severity("security_posture", None) == "info"


# ---------------------------------------------------------------------------
# Helpers — severity_at_least / max_severity / SEVERITY_RANK
# ---------------------------------------------------------------------------

def test_severity_rank_ordering():
    assert SEVERITY_RANK["info"] < SEVERITY_RANK["warning"] < SEVERITY_RANK["critical"]


def test_severity_at_least_true_cases():
    assert severity_at_least("critical", "warning")
    assert severity_at_least("warning", "info")
    assert severity_at_least("critical", "info")
    assert severity_at_least("info", "info")


def test_severity_at_least_false_cases():
    assert not severity_at_least("info", "warning")
    assert not severity_at_least("warning", "critical")


def test_max_severity_picks_higher_rank():
    assert max_severity("info", "warning") == "warning"
    assert max_severity("warning", "critical") == "critical"
    assert max_severity("info", "info") == "info"
    assert max_severity("critical", "info") == "critical"


def test_max_severity_unknown_treated_as_info():
    # Unknown strings are treated as rank 0 — same as info — so they never
    # accidentally outrank a real severity.
    assert max_severity("???", "info") == "???"  # tie → first arg wins
    assert max_severity("???", "warning") == "warning"
