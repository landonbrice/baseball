"""Tests for the ``existing_health`` collector (PR-3).

Covers:

* Happy path: synthetic digest + rolling outputs are mapped to the expected
  observation shape.
* D13 invariant: ``compute_plan_health_rolling`` returns of 30% / 50% / 80%
  emit exactly one ``signature=plan_enrichment_health`` observation with
  severity ``critical`` / ``warning`` / ``info`` respectively, regardless of
  what the surrounding digest contains.
* Failure path: ``compute_daily_digest`` raises → exactly one
  ``collector_failure`` observation, severity ``warning``, no re-raise.
* Timeout path: ``compute_daily_digest`` sleeps past the 5s ceiling → exactly
  one ``collector_failure`` observation with a "timed out" message.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from bot.services.system_guardian.collectors import existing_health
from bot.services.system_guardian.collectors.existing_health import (
    PLAN_ENRICHMENT_SIGNATURE,
    collect_existing_health,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures matching the shape ``health_monitor`` produces.
# ---------------------------------------------------------------------------


def _make_digest(
    *,
    plan_total: int = 5,
    plan_enriched: int = 5,
    plan_fallback: int = 0,
    plan_no_plan: int = 0,
    plan_degradation_rate: float = 0.0,
    plan_query_error: str | None = None,
    whoop_linked: int = 3,
    whoop_pulled: int = 3,
    whoop_missing: list[str] | None = None,
    weekly_narrative: dict | None = None,
    qa_total: int = 0,
    qa_errors: int = 0,
) -> dict:
    plan_health: dict = {
        "date": "2026-05-13",
        "total_plans": plan_total,
        "llm_enriched": plan_enriched,
        "python_fallback": plan_fallback,
        "no_plan": plan_no_plan,
        "degradation_rate": plan_degradation_rate,
        "source_reason_counts": {},
        "degraded_pitchers": [],
    }
    if plan_query_error:
        plan_health["query_error"] = plan_query_error

    whoop_health = {
        "date": "2026-05-13",
        "linked_count": whoop_linked,
        "pulled_count": whoop_pulled,
        "missing_pitchers": whoop_missing or [],
    }

    qa_health = {
        "total": qa_total,
        "successes": max(0, qa_total - qa_errors),
        "errors": qa_errors,
        "error_rate": (qa_errors / qa_total) if qa_total > 0 else 0.0,
        "error_types": {},
    }

    return {
        "plan_health": plan_health,
        "plan_health_rolling": {},  # collector ignores this — uses rolling arg
        "whoop_health": whoop_health,
        "weekly_narrative": weekly_narrative,
        "qa_health": qa_health,
    }


def _make_rolling(
    *,
    enriched: int = 6,
    fallback: int = 2,
    rate: float | None = None,
    query_error: str | None = None,
    window_days: int = 7,
) -> dict:
    total = enriched + fallback
    if rate is None:
        rate = (enriched / total) if total else 0.0
    out: dict = {
        "window_days": window_days,
        "total_plans": total,
        "llm_enriched": enriched,
        "python_fallback": fallback,
        "enrichment_rate": rate,
        "top_source_reasons": [],
    }
    if query_error:
        out["query_error"] = query_error
    return out


def _patch_digest_sources(digest: dict, rolling: dict):
    """Monkey-patch the two source functions the collector imports lazily.

    We patch the functions on the ``health_monitor`` module itself because the
    collector's ``_run_sync_digest`` does a local import.
    """
    return [
        patch(
            "bot.services.health_monitor.compute_daily_digest",
            return_value=digest,
        ),
        patch(
            "bot.services.health_monitor.compute_plan_health_rolling",
            return_value=rolling,
        ),
    ]


async def _run_with_patches(digest: dict, rolling: dict) -> list[dict]:
    """Helper that wires the patches and awaits the collector once."""
    patches = _patch_digest_sources(digest, rolling)
    for p in patches:
        p.start()
    try:
        return await collect_existing_health()
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_returns_expected_observation_shape():
    digest = _make_digest(
        plan_total=4,
        plan_enriched=3,
        plan_fallback=1,
        plan_degradation_rate=0.25,
    )
    rolling = _make_rolling(enriched=10, fallback=2)

    out = await _run_with_patches(digest, rolling)

    # Every observation should have the required column-aligned keys.
    required_keys = {
        "observed_at",
        "source",
        "event_type",
        "severity_hint",
        "message",
    }
    for obs in out:
        assert required_keys <= set(obs.keys()), f"missing keys in {obs}"
        assert obs["source"] == "existing_health.collect_existing_health"
        assert obs["severity_hint"] in {"critical", "warning", "info"}

    # Exactly one plan_enrichment_health observation (D13).
    pe = [o for o in out if o.get("signature") == PLAN_ENRICHMENT_SIGNATURE]
    assert len(pe) == 1, f"expected exactly one plan_enrichment_health, got {len(pe)}: {pe}"

    # Heartbeat info observation for plan_health is present.
    summaries = [o for o in out if o["event_type"] == "plan_health_summary"]
    assert len(summaries) == 1

    # WHOOP info observation is present (no missing pitchers in this fixture).
    whoop_summaries = [o for o in out if o["event_type"] == "whoop_health_summary"]
    assert len(whoop_summaries) == 1

    # No collector_failure on the happy path.
    failures = [o for o in out if o["event_type"] == "collector_failure"]
    assert failures == []


@pytest.mark.asyncio
async def test_happy_path_critical_when_no_plans_shipped_with_checkins():
    digest = _make_digest(plan_total=0, plan_enriched=0, plan_fallback=0, plan_no_plan=3)
    rolling = _make_rolling(enriched=10, fallback=2)

    out = await _run_with_patches(digest, rolling)
    critical = [o for o in out if o["event_type"] == "plan_generation_not_shipping"]
    assert len(critical) == 1
    assert critical[0]["severity_hint"] == "critical"
    assert critical[0]["metadata"]["checkins_without_plan"] == 3


@pytest.mark.asyncio
async def test_happy_path_warning_when_today_fallback_above_50pct():
    digest = _make_digest(
        plan_total=4,
        plan_enriched=1,
        plan_fallback=3,
        plan_degradation_rate=0.75,
    )
    rolling = _make_rolling(enriched=10, fallback=2)

    out = await _run_with_patches(digest, rolling)
    warn = [o for o in out if o["event_type"] == "plan_generation_degraded_today"]
    assert len(warn) == 1
    assert warn[0]["severity_hint"] == "warning"


@pytest.mark.asyncio
async def test_happy_path_emits_whoop_pull_missing_warning():
    digest = _make_digest(
        whoop_linked=3,
        whoop_pulled=2,
        whoop_missing=["pitcher_kamat_001"],
    )
    rolling = _make_rolling()

    out = await _run_with_patches(digest, rolling)
    missing = [o for o in out if o["event_type"] == "whoop_pull_missing"]
    assert len(missing) == 1
    assert missing[0]["severity_hint"] == "warning"
    assert "pitcher_kamat_001" in missing[0]["metadata"]["missing_pitchers"]


@pytest.mark.asyncio
async def test_qa_warning_when_error_rate_above_10pct_and_total_at_least_3():
    digest = _make_digest(qa_total=10, qa_errors=2)  # 20% error rate
    rolling = _make_rolling()

    out = await _run_with_patches(digest, rolling)
    qa = [o for o in out if o["event_type"] == "qa_error_rate_high"]
    assert len(qa) == 1
    assert qa[0]["severity_hint"] == "warning"


@pytest.mark.asyncio
async def test_qa_silent_below_threshold():
    digest = _make_digest(qa_total=2, qa_errors=1)  # only 2 total → too noisy
    rolling = _make_rolling()

    out = await _run_with_patches(digest, rolling)
    qa = [o for o in out if o["event_type"] == "qa_error_rate_high"]
    assert qa == []


@pytest.mark.asyncio
async def test_weekly_narrative_only_emits_on_sunday_signal():
    """When ``compute_weekly_narrative_health`` returned None (non-Sunday),
    no weekly observation should be emitted."""
    digest = _make_digest(weekly_narrative=None)
    rolling = _make_rolling()
    out = await _run_with_patches(digest, rolling)
    weekly = [o for o in out if "weekly_narrative" in o["event_type"]]
    assert weekly == []


@pytest.mark.asyncio
async def test_weekly_narrative_missing_emits_warning_when_some_pitchers_lack_narrative():
    narrative = {
        "week_start": "2026-05-04",
        "pitchers_with_activity": 5,
        "pitchers_with_narrative": 3,
        "missing_pitchers": ["pitcher_a", "pitcher_b"],
    }
    digest = _make_digest(weekly_narrative=narrative)
    rolling = _make_rolling()
    out = await _run_with_patches(digest, rolling)
    weekly = [o for o in out if o["event_type"] == "weekly_narrative_missing"]
    assert len(weekly) == 1
    assert weekly[0]["severity_hint"] == "warning"


# ---------------------------------------------------------------------------
# D13 invariant: rolling ratio → observation severity mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rate, expected_severity",
    [
        (0.30, "critical"),  # < 40%
        (0.50, "warning"),   # 40-60%
        (0.80, "info"),      # ≥ 60%
        (0.39, "critical"),  # boundary just under critical
        (0.59, "warning"),   # boundary just under warning
        (0.60, "info"),      # boundary exactly at info
    ],
)
async def test_d13_plan_enrichment_severity_by_rate(rate, expected_severity):
    """D13: rate → severity mapping is deterministic regardless of digest contents.

    Constructs the rolling dict with a specific ``enrichment_rate``, leaves the
    rest of the digest healthy, and asserts the single
    ``signature=plan_enrichment_health`` observation has the expected severity.
    """
    digest = _make_digest()
    # Use total=20 so any rate produces enriched ≥ 0 cleanly.
    enriched = int(round(rate * 20))
    fallback = 20 - enriched
    rolling = _make_rolling(enriched=enriched, fallback=fallback, rate=rate)

    out = await _run_with_patches(digest, rolling)
    pe = [o for o in out if o.get("signature") == PLAN_ENRICHMENT_SIGNATURE]
    assert len(pe) == 1, (
        f"D13 invariant violated: expected exactly one plan_enrichment_health observation, "
        f"got {len(pe)}; out={out}"
    )
    assert pe[0]["severity_hint"] == expected_severity, (
        f"D13 severity mismatch for rate={rate}: expected {expected_severity}, "
        f"got {pe[0]['severity_hint']}; obs={pe[0]}"
    )
    # Signature must be the exact stable string.
    assert pe[0]["signature"] == "plan_enrichment_health"


@pytest.mark.asyncio
async def test_d13_plan_enrichment_emitted_even_when_total_zero():
    """If the rolling window has zero plans, we still emit the observation but
    degrade to info — the goal is never to silently miss a digest run."""
    digest = _make_digest()
    rolling = _make_rolling(enriched=0, fallback=0, rate=0.0)
    out = await _run_with_patches(digest, rolling)
    pe = [o for o in out if o.get("signature") == PLAN_ENRICHMENT_SIGNATURE]
    assert len(pe) == 1
    assert pe[0]["severity_hint"] == "info"


# ---------------------------------------------------------------------------
# Failure path (A1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_does_not_raise_when_digest_function_raises():
    """If ``compute_daily_digest`` raises, the collector must return ONE
    collector_failure observation and NOT re-raise. Per A1."""

    def _boom():
        raise RuntimeError("simulated digest failure")

    with (
        patch("bot.services.health_monitor.compute_daily_digest", _boom),
        patch(
            "bot.services.health_monitor.compute_plan_health_rolling",
            return_value=_make_rolling(),
        ),
    ):
        out = await collect_existing_health()

    assert isinstance(out, list)
    assert len(out) == 1, f"expected single collector_failure obs; got {out}"
    failure = out[0]
    assert failure["event_type"] == "collector_failure"
    assert failure["severity_hint"] == "warning"
    assert "RuntimeError" in failure["message"]
    # Per A1 metadata must include category=guardian_self + code=collector_failure
    assert failure["metadata"]["category"] == "guardian_self"
    assert failure["metadata"]["code"] == "collector_failure"


@pytest.mark.asyncio
async def test_collector_does_not_raise_when_rolling_function_raises():
    """If ``compute_plan_health_rolling`` raises (it runs in the same
    threadpool block), we still emit a single collector_failure rather than
    crashing or returning a partial list."""

    def _boom():
        raise RuntimeError("simulated rolling failure")

    with (
        patch(
            "bot.services.health_monitor.compute_daily_digest",
            return_value=_make_digest(),
        ),
        patch("bot.services.health_monitor.compute_plan_health_rolling", _boom),
    ):
        out = await collect_existing_health()

    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0]["event_type"] == "collector_failure"
    assert out[0]["severity_hint"] == "warning"


# ---------------------------------------------------------------------------
# Timeout path (A1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_collector_emits_timeout_failure_when_digest_hangs(monkeypatch):
    """If the sync digest call hangs past the 5s ceiling, the collector emits
    one collector_failure with a "timed out" message. We monkeypatch the
    timeout constant to keep the test fast."""
    monkeypatch.setattr(existing_health, "_COLLECTOR_TIMEOUT_S", 0.05)

    def _slow():
        time.sleep(0.5)
        return _make_digest()

    with (
        patch("bot.services.health_monitor.compute_daily_digest", _slow),
        patch(
            "bot.services.health_monitor.compute_plan_health_rolling",
            return_value=_make_rolling(),
        ),
    ):
        out = await collect_existing_health()

    assert isinstance(out, list)
    assert len(out) == 1
    failure = out[0]
    assert failure["event_type"] == "collector_failure"
    assert failure["severity_hint"] == "warning"
    assert "timed out" in failure["message"].lower()
    assert failure["metadata"]["category"] == "guardian_self"
    assert failure["metadata"]["code"] == "collector_failure"


# ---------------------------------------------------------------------------
# Public API surface check
# ---------------------------------------------------------------------------


def test_collectors_subpackage_imports():
    """The collectors subpackage exists and ``existing_health`` is importable."""
    from bot.services.system_guardian import collectors  # noqa: F401
    from bot.services.system_guardian.collectors import existing_health as _eh  # noqa: F401

    assert callable(collect_existing_health)
    assert PLAN_ENRICHMENT_SIGNATURE == "plan_enrichment_health"


def test_collect_existing_health_is_coroutine_function():
    """A1 contract: collectors are async."""
    assert asyncio.iscoroutinefunction(collect_existing_health)
