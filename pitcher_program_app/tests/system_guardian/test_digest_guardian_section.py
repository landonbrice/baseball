"""Tests for the Guardian summary section appended to the 9am digest.

Covers:

* ``format_guardian_summary_section`` produces a string containing the expected
  counts/highlights for a synthetic mixed observation list.
* Empty / None input returns the empty string (caller can append unconditionally).
* Clustering collapses duplicate signatures into a single row with ``×count``.
* Severity ordering: critical rows render before warning rows render before info.
* Read-time redaction wraps observation messages before render — a synthetic
  JWT in an observation message is replaced with ``[REDACTED:jwt]`` in the
  rendered section.
* The integration wiring (``_send_health_digest`` in ``bot/main.py``) calls
  the collector AND passes the observations to ``format_digest_message``. We
  verify this by patching the dependencies and asserting on the message
  payload that gets sent to Telegram.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.services.health_monitor import (
    format_digest_message,
    format_guardian_summary_section,
)


def _ensure_real_telegram_modules():
    """``tests/test_coach_chat.py`` (pre-existing) stubs out the ``telegram``
    package as a bare ``types.ModuleType`` so the qa handler can be imported
    without installing python-telegram-bot. That stub does NOT export
    ``BotCommand`` / ``InlineKeyboardButton`` / etc., which ``bot/main.py``
    needs at import time.

    When the full test suite runs, test_coach_chat lands first and leaves the
    stub in ``sys.modules``, so any subsequent test that imports ``bot.main``
    (us) blows up with an ImportError.

    This helper removes the stub iff python-telegram-bot is actually
    installed, forcing a fresh import of the real package. If
    python-telegram-bot is NOT installed, we leave the stub in place — the
    test will then skip rather than crash.
    """
    try:
        import telegram  # noqa: F401  # the real package on Railway
    except ImportError:
        return False
    # Real package importable but maybe shadowed by the stub. Detect by
    # checking for an attribute the real package has and the stub doesn't.
    if not hasattr(sys.modules.get("telegram"), "BotCommand"):
        # Drop the stub and its submodule entries so import picks up the real
        # package next time bot/main.py runs its top-of-file imports.
        for key in [k for k in list(sys.modules) if k == "telegram" or k.startswith("telegram.")]:
            del sys.modules[key]
        # Also drop bot.main / handlers that may have closed over the stub.
        for key in [
            k for k in list(sys.modules)
            if k == "bot.main" or k.startswith("bot.handlers")
        ]:
            del sys.modules[key]
        try:
            import telegram  # noqa: F401, re-imported to pick up real module
        except ImportError:
            return False
    return True


# ---------------------------------------------------------------------------
# format_guardian_summary_section
# ---------------------------------------------------------------------------


def _obs(
    *,
    signature: str,
    severity: str = "info",
    event_type: str = "observation",
    message: str = "",
    code: str | None = None,
) -> dict:
    metadata: dict = {}
    if code:
        metadata["code"] = code
    return {
        "observed_at": "2026-05-13T09:00:00-05:00",
        "source": "test",
        "service": "test",
        "event_type": event_type,
        "severity_hint": severity,
        "signature": signature,
        "message": message,
        "metadata": metadata,
    }


def test_empty_list_returns_empty_string():
    assert format_guardian_summary_section([]) == ""


def test_none_returns_empty_string():
    assert format_guardian_summary_section(None) == ""


def test_section_includes_headline_counts():
    observations = [
        _obs(signature="sig_a", severity="critical", code="plan_generation_not_shipping"),
        _obs(signature="sig_b", severity="warning", code="llm_enrichment_below_60pct"),
        _obs(signature="sig_c", severity="info", code="plan_health_summary"),
    ]
    section = format_guardian_summary_section(observations)
    # Header must announce the counts.
    assert "Guardian:" in section
    assert "1 critical" in section
    assert "1 warning" in section
    assert "1 info" in section
    assert "3 signatures" in section
    assert "3 obs" in section


def test_clustering_collapses_same_signature():
    """Multiple observations with the same signature → single row with ×count."""
    observations = [
        _obs(signature="sig_a", severity="warning", code="llm_enrichment_below_60pct"),
        _obs(signature="sig_a", severity="warning", code="llm_enrichment_below_60pct"),
        _obs(signature="sig_a", severity="warning", code="llm_enrichment_below_60pct"),
    ]
    section = format_guardian_summary_section(observations)
    # 1 cluster, 3 observations
    assert "1 signatures" in section
    assert "3 obs" in section
    # Render shows ×3 for the cluster
    assert "×3" in section


def test_critical_renders_before_warning_before_info():
    """Severity ordering — critical rows must render before warning/info."""
    observations = [
        _obs(signature="info_sig", severity="info", code="info_signal", message="info msg"),
        _obs(
            signature="crit_sig",
            severity="critical",
            code="critical_signal",
            message="crit msg",
        ),
        _obs(
            signature="warn_sig",
            severity="warning",
            code="warning_signal",
            message="warn msg",
        ),
    ]
    section = format_guardian_summary_section(observations)
    crit_idx = section.find("critical_signal")
    warn_idx = section.find("warning_signal")
    info_idx = section.find("info_signal")
    assert crit_idx != -1 and warn_idx != -1 and info_idx != -1
    assert crit_idx < warn_idx < info_idx, (
        f"severity ordering violated: critical@{crit_idx} warning@{warn_idx} info@{info_idx}"
    )


def test_section_uses_severity_icons():
    """Section uses 🔴 / 🟡 / · icons consistent with the rest of the digest."""
    observations = [
        _obs(signature="a", severity="critical", code="a"),
        _obs(signature="b", severity="warning", code="b"),
        _obs(signature="c", severity="info", code="c"),
    ]
    section = format_guardian_summary_section(observations)
    assert "🔴" in section
    assert "🟡" in section
    assert "·" in section


def test_section_renders_at_most_six_signatures_then_overflow_line():
    """Section caps rendered signatures so the digest stays concise."""
    observations = [
        _obs(signature=f"sig_{i}", severity="warning", code=f"code_{i}")
        for i in range(9)
    ]
    section = format_guardian_summary_section(observations)
    # The 9-6=3 overflow line should fire.
    assert "+3 more" in section


def test_section_under_eight_lines_for_typical_case():
    """Brief: aim for ≤ 8 lines. Validate header + up to 6 signatures + 1
    overflow = 8 lines max."""
    observations = [
        _obs(signature=f"sig_{i}", severity="warning", code=f"c_{i}")
        for i in range(20)
    ]
    section = format_guardian_summary_section(observations)
    lines = section.splitlines()
    assert len(lines) <= 8, f"section exceeded 8 lines: {lines}"


def test_section_redacts_jwt_in_observation_message():
    """Read-time redactor (A4) runs on every observation message before render
    so a secret that survived write-time can't leak through the digest."""
    synthetic_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0In0.signature_padding_xyz"
    )
    observations = [
        _obs(
            signature="redact_sig",
            severity="critical",
            code="exposed_secret",
            message=f"leaked token {synthetic_jwt} in log line",
        ),
    ]
    section = format_guardian_summary_section(observations)
    assert synthetic_jwt not in section
    assert "[REDACTED:jwt]" in section


def test_section_message_excerpt_truncated_at_90_chars():
    long_msg = "x" * 200
    observations = [
        _obs(signature="long", severity="warning", code="long_signal", message=long_msg),
    ]
    section = format_guardian_summary_section(observations)
    # Truncation: 87 x's + "..." (total 90 chars excerpt, matches the
    # 90-char cap in _guardian_summary_for_cluster).
    assert ("x" * 87 + "...") in section
    assert ("x" * 200) not in section


# ---------------------------------------------------------------------------
# format_digest_message integration — Guardian section opt-in
# ---------------------------------------------------------------------------


def _minimal_digest() -> dict:
    """The smallest digest format_digest_message accepts cleanly."""
    return {
        "plan_health": {
            "date": "2026-05-13",
            "total_plans": 2,
            "llm_enriched": 2,
            "python_fallback": 0,
            "no_plan": 0,
            "degradation_rate": 0.0,
            "source_reason_counts": {},
            "degraded_pitchers": [],
        },
        "plan_health_rolling": {
            "window_days": 7,
            "total_plans": 10,
            "llm_enriched": 9,
            "python_fallback": 1,
            "enrichment_rate": 0.9,
            "top_source_reasons": [],
        },
        "whoop_health": {
            "date": "2026-05-13",
            "linked_count": 0,
            "pulled_count": 0,
            "missing_pitchers": [],
        },
        "weekly_narrative": None,
        "qa_health": {
            "total": 0,
            "successes": 0,
            "errors": 0,
            "error_rate": 0.0,
            "error_types": {},
        },
    }


def test_format_digest_message_omits_section_when_observations_is_none():
    """Back-compat: callers that don't pass observations get the legacy shape."""
    msg = format_digest_message(_minimal_digest())
    assert "Guardian:" not in msg
    assert "🛡️" not in msg


def test_format_digest_message_includes_section_when_observations_passed():
    observations = [
        _obs(
            signature="sig_a",
            severity="warning",
            code="llm_enrichment_below_60pct",
            message="enrichment 50%",
        ),
    ]
    msg = format_digest_message(_minimal_digest(), guardian_observations=observations)
    assert "Guardian:" in msg
    assert "llm_enrichment_below_60pct" in msg


def test_format_digest_message_omits_section_when_observations_empty_list():
    """Empty list still produces no section (format_guardian_summary_section
    returns the empty string, the outer formatter skips the append)."""
    msg = format_digest_message(_minimal_digest(), guardian_observations=[])
    assert "Guardian:" not in msg


# ---------------------------------------------------------------------------
# bot.main._send_health_digest wiring (V1 acceptance #7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_health_digest_calls_collector_and_persists_observations():
    """The 9am scheduler hook (``_send_health_digest`` in ``bot/main.py``)
    must call the existing_health collector, persist each observation via
    insert_observation, AND pass the observations into format_digest_message
    so the section is included in the Telegram message body."""

    if not _ensure_real_telegram_modules():
        pytest.skip("python-telegram-bot not installed in this environment")
    from bot import main as bot_main

    sample_obs = [
        _obs(
            signature="plan_enrichment_health",
            severity="warning",
            code="llm_enrichment_below_60pct",
            event_type="plan_enrichment_health",
            message="plan_enrichment_health: 50% over last 7 days (4/8)",
        ),
        _obs(
            signature="ph_summary_sig",
            severity="info",
            code="plan_health_summary",
            event_type="plan_health_summary",
            message="plan_health_summary heartbeat",
        ),
    ]

    # Fake the context object the scheduler hands to the job.
    fake_context = MagicMock()
    fake_context.bot = MagicMock()
    fake_context.bot.send_message = AsyncMock()

    inserted: list[dict] = []

    def _fake_insert(obs):
        inserted.append(obs)
        return obs

    with (
        patch(
            "bot.services.health_monitor.compute_daily_digest",
            return_value=_minimal_digest(),
        ),
        patch(
            "bot.services.system_guardian.collectors.existing_health.collect_existing_health",
            new=AsyncMock(return_value=sample_obs),
        ),
        patch(
            "bot.services.system_guardian.store.insert_observation",
            side_effect=_fake_insert,
        ),
    ):
        await bot_main._send_health_digest(fake_context)

    # Every observation must be persisted.
    assert len(inserted) == len(sample_obs), (
        f"expected {len(sample_obs)} inserts, got {len(inserted)}: {inserted}"
    )
    # The send_message payload must include the Guardian section.
    fake_context.bot.send_message.assert_awaited_once()
    sent_kwargs = fake_context.bot.send_message.await_args.kwargs
    sent_text = sent_kwargs.get("text", "")
    assert "Guardian:" in sent_text, (
        f"Guardian section missing from digest message; sent_text={sent_text!r}"
    )
    # Sanity: at least one observation's code surfaces in the message body.
    assert "llm_enrichment_below_60pct" in sent_text


@pytest.mark.asyncio
async def test_send_health_digest_still_ships_when_collector_returns_failure():
    """If the collector returns a collector_failure (the A1 contract on
    exception), the digest still goes out — the failure observation is
    persisted but the broader digest message is unaffected."""

    if not _ensure_real_telegram_modules():
        pytest.skip("python-telegram-bot not installed in this environment")
    from bot import main as bot_main

    failure_obs = [
        _obs(
            signature="collector_failure_sig",
            severity="warning",
            code="collector_failure",
            event_type="collector_failure",
            message="collector_failure in existing_health.compute_daily_digest: RuntimeError",
        ),
    ]

    fake_context = MagicMock()
    fake_context.bot = MagicMock()
    fake_context.bot.send_message = AsyncMock()

    inserted: list[dict] = []

    with (
        patch(
            "bot.services.health_monitor.compute_daily_digest",
            return_value=_minimal_digest(),
        ),
        patch(
            "bot.services.system_guardian.collectors.existing_health.collect_existing_health",
            new=AsyncMock(return_value=failure_obs),
        ),
        patch(
            "bot.services.system_guardian.store.insert_observation",
            side_effect=lambda o: inserted.append(o) or o,
        ),
    ):
        await bot_main._send_health_digest(fake_context)

    fake_context.bot.send_message.assert_awaited_once()
    # The collector_failure observation should still surface in the section.
    sent_text = fake_context.bot.send_message.await_args.kwargs.get("text", "")
    assert "collector_failure" in sent_text
    assert len(inserted) == 1
