"""Tests for the debug packet builder per spec §12 / amendments D5/D10/D14/A7."""

from __future__ import annotations

from unittest.mock import patch

from bot.services.system_guardian.debug_packet import build_debug_packet


SYNTHETIC_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJ0ZXN0In0"
    ".signature_here_padding"
)


def _stub_git_log():
    return [
        {
            "sha": "deadbeef",
            "subject": "feat: something",
            "author": "Lando",
            "committed_at": "2026-05-12T01:00:00-05:00",
        }
    ]


def _stub_athlete_context(pitcher_id):
    return {
        "pitcher_id": pitcher_id,
        "name": "Test Pitcher",
        "role": "Starter (7-day)",
        "current_flag_level": "yellow",
        "current_arm_feel": 6,
        "active_modifications": ["mobility_only"],
        "recent_injury_history": [
            {"area": "elbow", "severity": "moderate"},
        ],
    }


# ---------------------------------------------------------------------------
# Packet shape (§12 contract)
# ---------------------------------------------------------------------------

def test_packet_contains_all_required_fields():
    incident = {
        "title": "Check-in route failing",
        "severity": "critical",
        "category": "runtime_error",
        "first_seen": "2026-05-12T08:12:00-05:00",
        "last_seen": "2026-05-12T08:30:00-05:00",
        "count": 6,
        "affected_services": ["api"],
        "affected_surfaces": ["POST /api/chat"],
        "suspected_files": ["api/routes.py", "bot/services/checkin_service.py"],
        "sample_messages": [
            {"observed_at": "2026-05-12T08:12:00-05:00", "message": "TypeError in process_checkin"},
        ],
    }
    packet = build_debug_packet(
        incident,
        git_log_fn=_stub_git_log,
        athlete_context_fn=_stub_athlete_context,
    )
    for key in (
        "title",
        "severity",
        "category",
        "symptom",
        "impact",
        "evidence",
        "likely_entrypoint",
        "suspected_files",
        "recent_changes",
        "reproduction",
        "suggested_tests",
        "vision_flags",
    ):
        assert key in packet, f"Missing required packet field: {key}"
    assert packet["severity"] == "critical"
    assert packet["category"] == "runtime_error"


def test_packet_uses_provided_git_log_fn():
    packet = build_debug_packet(
        {"title": "x", "severity": "info", "category": "runtime_error"},
        git_log_fn=_stub_git_log,
        athlete_context_fn=lambda _pid: None,
    )
    assert packet["recent_changes"] == _stub_git_log()


def test_packet_evidence_includes_first_last_seen_and_count():
    incident = {
        "title": "x",
        "severity": "warning",
        "category": "silent_degradation",
        "first_seen": "2026-05-10T00:00:00-05:00",
        "last_seen": "2026-05-12T00:00:00-05:00",
        "count": 7,
        "sample_messages": [{"observed_at": "t", "message": "smpl"}],
    }
    packet = build_debug_packet(
        incident,
        git_log_fn=lambda: [],
        athlete_context_fn=lambda _: None,
    )
    evidence_blob = "\n".join(packet["evidence"])
    assert "2026-05-10" in evidence_blob
    assert "2026-05-12" in evidence_blob
    assert "Occurrences: 7" in evidence_blob
    assert "smpl" in evidence_blob


def test_packet_includes_athlete_context_when_pitcher_id_present():
    incident = {
        "title": "x",
        "severity": "warning",
        "category": "silent_degradation",
        "affected_entities": {"pitcher_id": "pitcher_test_001"},
    }
    packet = build_debug_packet(
        incident,
        git_log_fn=lambda: [],
        athlete_context_fn=_stub_athlete_context,
    )
    assert "athlete_context" in packet
    assert packet["athlete_context"]["pitcher_id"] == "pitcher_test_001"
    assert packet["athlete_context"]["recent_injury_history"]


def test_packet_omits_athlete_context_when_no_pitcher():
    incident = {
        "title": "x",
        "severity": "info",
        "category": "guardian_self",
        "affected_entities": {},
    }
    packet = build_debug_packet(
        incident,
        git_log_fn=lambda: [],
        athlete_context_fn=_stub_athlete_context,
    )
    assert "athlete_context" not in packet


def test_packet_picks_pitcher_id_from_pitcher_ids_list():
    incident = {
        "title": "x",
        "severity": "warning",
        "category": "silent_degradation",
        "affected_entities": {"pitcher_ids": ["pitcher_a", "pitcher_b"]},
    }
    packet = build_debug_packet(
        incident,
        git_log_fn=lambda: [],
        athlete_context_fn=_stub_athlete_context,
    )
    assert packet["athlete_context"]["pitcher_id"] == "pitcher_a"


# ---------------------------------------------------------------------------
# Read-time redactor defense in depth (A4)
# ---------------------------------------------------------------------------

def test_packet_redacts_jwt_in_title_and_samples():
    incident = {
        "title": f"check-in failing because of header {SYNTHETIC_JWT}",
        "severity": "warning",
        "category": "runtime_error",
        "sample_messages": [
            {"observed_at": "t", "message": f"see {SYNTHETIC_JWT}"},
        ],
    }
    packet = build_debug_packet(
        incident,
        git_log_fn=lambda: [],
        athlete_context_fn=lambda _: None,
    )
    import json

    serialized = json.dumps(packet, default=str)
    assert SYNTHETIC_JWT not in serialized


# ---------------------------------------------------------------------------
# git_log_fn failure paths
# ---------------------------------------------------------------------------

def test_packet_tolerates_git_log_failure():
    def _boom():
        raise RuntimeError("git binary missing")

    # Wrap _boom so we don't bubble — debug_packet uses the function as-is, so
    # we need to test the actual tolerance pathway via the default _safe_git_log.
    # Here we just confirm that returning [] from a stub does not break shape.
    packet = build_debug_packet(
        {"title": "x", "severity": "info", "category": "runtime_error"},
        git_log_fn=lambda: [],
        athlete_context_fn=lambda _: None,
    )
    assert packet["recent_changes"] == []


def test_real_safe_git_log_handles_missing_binary(monkeypatch):
    """If `git` shells out and fails, recent_changes is [] (not an exception)."""
    from bot.services.system_guardian import debug_packet as dbg

    def _raise(*args, **kwargs):
        raise FileNotFoundError("git not on PATH")

    monkeypatch.setattr(dbg.subprocess, "run", _raise)
    out = dbg._safe_git_log()
    assert out == []


def test_safe_git_log_parses_pretty_format(monkeypatch):
    """Smoke-test the parser with a stubbed subprocess result."""
    from bot.services.system_guardian import debug_packet as dbg

    class _R:
        returncode = 0
        stderr = ""
        stdout = (
            "abc123\x1ffeat: a\x1fLando\x1f2026-05-12T01:00:00-05:00\n"
            "def456\x1ffix: b\x1fClaude\x1f2026-05-11T20:00:00-05:00\n"
        )

    monkeypatch.setattr(dbg.subprocess, "run", lambda *a, **kw: _R())
    commits = dbg._safe_git_log()
    assert len(commits) == 2
    assert commits[0]["sha"] == "abc123"
    assert commits[0]["subject"] == "feat: a"
    assert commits[0]["author"] == "Lando"


def test_safe_git_log_caps_commits_at_d14_limit():
    """D14 cap: ``-n50`` is in the command. Verify the constant."""
    from bot.services.system_guardian import debug_packet as dbg

    assert dbg._GIT_LOG_MAX_COMMITS == 50
    assert dbg._GIT_LOG_MAX_DAYS == 7
