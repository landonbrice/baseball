"""Tests for incident payload construction + status transitions per A6."""

from __future__ import annotations

import pytest

from bot.services.system_guardian.incidents import (
    build_incident_payload,
    merge_observation_into_incident,
    validate_status_transition,
)


# ---------------------------------------------------------------------------
# build_incident_payload — first-occurrence shape
# ---------------------------------------------------------------------------

def test_build_incident_payload_full_shape():
    obs = {
        "signature": "sig_abc",
        "message": "LLM enrichment dropped to 42% over 7 days",
        "severity": "warning",
        "category": "silent_degradation",
        "service": "plan_generator",
        "surface": "checkin_pipeline",
        "observed_at": "2026-05-12T03:00:00-05:00",
        "affected_entities": {"pitcher_ids": ["p1", "p2"]},
    }
    payload = build_incident_payload(obs)
    assert payload["signature"] == "sig_abc"
    assert payload["status"] == "open"
    assert payload["severity"] == "warning"
    assert payload["category"] == "silent_degradation"
    assert payload["count"] == 1
    assert payload["first_seen"] == "2026-05-12T03:00:00-05:00"
    assert payload["last_seen"] == "2026-05-12T03:00:00-05:00"
    assert payload["affected_services"] == ["plan_generator"]
    assert payload["affected_surfaces"] == ["checkin_pipeline"]
    assert payload["affected_entities"] == {"pitcher_ids": ["p1", "p2"]}
    assert payload["last_notified_at"] is None  # PR-5 notifier sets this
    assert len(payload["sample_messages"]) == 1
    assert payload["sample_messages"][0]["message"] == obs["message"]


def test_build_incident_payload_invalid_severity_falls_back_to_info():
    obs = {"signature": "x", "message": "m", "severity": "moderate"}
    payload = build_incident_payload(obs)
    assert payload["severity"] == "info"


def test_build_incident_payload_truncates_long_title():
    long = "a" * 500
    payload = build_incident_payload({"signature": "x", "message": long})
    assert len(payload["title"]) <= 120


def test_build_incident_payload_falls_back_to_event_type_for_title():
    payload = build_incident_payload(
        {"signature": "x", "message": "", "event_type": "tick_budget_exceeded"}
    )
    assert payload["title"] == "tick_budget_exceeded"


# ---------------------------------------------------------------------------
# merge_observation_into_incident
# ---------------------------------------------------------------------------

def test_merge_increments_count_and_advances_last_seen():
    existing = {
        "id": "id1",
        "severity": "warning",
        "count": 3,
        "first_seen": "2026-05-10T00:00:00-05:00",
        "last_seen": "2026-05-11T00:00:00-05:00",
        "sample_messages": [],
        "affected_services": [],
        "affected_surfaces": [],
    }
    obs = {"message": "another occurrence", "observed_at": "2026-05-12T03:00:00-05:00"}
    out = merge_observation_into_incident(existing, obs)
    assert out["count"] == 4
    assert out["last_seen"] == "2026-05-12T03:00:00-05:00"
    # Severity unchanged → no notification advance.
    assert out["severity"] == "warning"
    assert "last_notified_at" not in out


def test_merge_does_not_advance_notified_when_severity_stays_same():
    existing = {
        "id": "id1",
        "severity": "warning",
        "count": 1,
        "sample_messages": [],
        "affected_services": [],
        "affected_surfaces": [],
    }
    obs = {"message": "again", "severity": "warning", "observed_at": "2026-05-12T03:00:00-05:00"}
    out = merge_observation_into_incident(existing, obs)
    assert "last_notified_at" not in out


def test_merge_advances_notified_on_severity_escalation():
    existing = {
        "id": "id1",
        "severity": "warning",
        "count": 1,
        "sample_messages": [],
        "affected_services": [],
        "affected_surfaces": [],
    }
    obs = {
        "message": "escalating",
        "severity": "critical",
        "observed_at": "2026-05-12T03:00:00-05:00",
    }
    out = merge_observation_into_incident(existing, obs)
    assert out["severity"] == "critical"
    assert out["last_notified_at"] == "2026-05-12T03:00:00-05:00"


def test_merge_does_not_de_escalate_severity():
    existing = {
        "id": "id1",
        "severity": "critical",
        "count": 1,
        "sample_messages": [],
        "affected_services": [],
        "affected_surfaces": [],
    }
    obs = {"message": "info-level repeat", "severity": "info"}
    out = merge_observation_into_incident(existing, obs)
    assert out["severity"] == "critical"


def test_merge_caps_sample_messages_at_five():
    existing = {
        "id": "id1",
        "severity": "warning",
        "count": 5,
        "sample_messages": [{"observed_at": "t1", "message": f"m{i}"} for i in range(5)],
        "affected_services": [],
        "affected_surfaces": [],
    }
    obs = {"message": "newest", "observed_at": "t-new"}
    out = merge_observation_into_incident(existing, obs)
    assert len(out["sample_messages"]) == 5
    assert out["sample_messages"][-1]["message"] == "newest"
    # Oldest was dropped:
    assert all(s["message"] != "m0" for s in out["sample_messages"])


def test_merge_unions_affected_services_and_surfaces():
    existing = {
        "id": "id1",
        "severity": "warning",
        "count": 1,
        "sample_messages": [],
        "affected_services": ["api"],
        "affected_surfaces": ["POST /api/chat"],
    }
    obs = {
        "message": "x",
        "service": "bot",
        "surface": "telegram_handler",
    }
    out = merge_observation_into_incident(existing, obs)
    assert "api" in out["affected_services"]
    assert "bot" in out["affected_services"]
    assert "POST /api/chat" in out["affected_surfaces"]
    assert "telegram_handler" in out["affected_surfaces"]


# ---------------------------------------------------------------------------
# validate_status_transition
# ---------------------------------------------------------------------------

def test_legal_transitions():
    validate_status_transition("open", "ack")
    validate_status_transition("open", "resolved")
    validate_status_transition("ack", "resolved")
    validate_status_transition("resolved", "open")  # re-open
    validate_status_transition("ack", "open")
    validate_status_transition("muted", "open")


def test_no_op_transition_is_allowed():
    validate_status_transition("open", "open")
    validate_status_transition("ack", "ack")


def test_illegal_transition_raises():
    with pytest.raises(ValueError):
        validate_status_transition("resolved", "ack")
    with pytest.raises(ValueError):
        validate_status_transition("open", "garbage_status")
