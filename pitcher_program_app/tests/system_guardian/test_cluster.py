"""Tests for signature generation + observation clustering per spec §13."""

from __future__ import annotations

from bot.services.system_guardian.cluster import (
    cluster_observations,
    generate_signature,
)


# ---------------------------------------------------------------------------
# generate_signature
# ---------------------------------------------------------------------------

def test_signature_is_deterministic_for_same_input():
    obs = {
        "category": "silent_degradation",
        "code": "llm_enrichment_below_60pct",
        "route_or_job": "plan_generator",
        "error_class": None,
        "message": "rolling enrichment 42% over 7 days",
    }
    assert generate_signature(obs) == generate_signature(obs)


def test_signature_length_under_64_chars():
    obs = {
        "category": "silent_degradation_extra_long_category_label_xyz",
        "code": "very_long_code_string_for_signature_test",
        "route_or_job": "POST /api/very/long/route/name/with/many/segments",
    }
    sig = generate_signature(obs)
    assert len(sig) <= 64


def test_signature_has_category_prefix_for_readability():
    sig = generate_signature(
        {"category": "security_posture", "code": "exposed_secret"}
    )
    assert sig.startswith("security_pos") or sig.startswith("security")


def test_signature_strips_pitcher_id_volatility():
    obs_a = {
        "category": "silent_degradation",
        "code": "whoop_pull_missing",
        "message": "pitcher pitcher_kamat_001 missing whoop pull for 2026-04-30",
    }
    obs_b = {
        "category": "silent_degradation",
        "code": "whoop_pull_missing",
        "message": "pitcher pitcher_richert_001 missing whoop pull for 2026-05-01",
    }
    assert generate_signature(obs_a) == generate_signature(obs_b)


def test_signature_strips_request_id_volatility():
    obs_a = {
        "category": "runtime_error",
        "code": "checkin_500",
        "message": "request_id=req_abc123 failed in process_checkin",
    }
    obs_b = {
        "category": "runtime_error",
        "code": "checkin_500",
        "message": "request_id=req_def987 failed in process_checkin",
    }
    assert generate_signature(obs_a) == generate_signature(obs_b)


def test_signature_strips_uuid_volatility():
    obs_a = {
        "category": "runtime_error",
        "code": "row_lookup_failed",
        "message": "row 11111111-2222-3333-4444-555555555555 not found",
    }
    obs_b = {
        "category": "runtime_error",
        "code": "row_lookup_failed",
        "message": "row aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee not found",
    }
    assert generate_signature(obs_a) == generate_signature(obs_b)


def test_signature_differs_when_route_differs():
    obs_a = {
        "category": "runtime_error",
        "code": "500",
        "route_or_job": "POST /api/chat",
        "error_class": "TypeError",
    }
    obs_b = {
        "category": "runtime_error",
        "code": "500",
        "route_or_job": "POST /api/coach/team/overview",
        "error_class": "TypeError",
    }
    assert generate_signature(obs_a) != generate_signature(obs_b)


def test_signature_differs_when_category_differs():
    base = {
        "code": "x",
        "route_or_job": "POST /api/foo",
        "error_class": "X",
    }
    a = generate_signature({**base, "category": "runtime_error"})
    b = generate_signature({**base, "category": "silent_degradation"})
    assert a != b


def test_signature_works_without_code_or_route():
    obs = {"category": "data_quality", "message": "invalid arm_feel value"}
    sig = generate_signature(obs)
    assert sig
    assert len(sig) <= 64


def test_signature_handles_empty_observation():
    sig = generate_signature({})
    assert sig
    assert len(sig) <= 64


# ---------------------------------------------------------------------------
# cluster_observations
# ---------------------------------------------------------------------------

def test_cluster_groups_same_signature():
    obs1 = {"category": "x", "code": "y", "signature": "sig_a"}
    obs2 = {"category": "x", "code": "y", "signature": "sig_a"}
    obs3 = {"category": "x", "code": "y", "signature": "sig_b"}
    grouped = cluster_observations([obs1, obs2, obs3])
    assert len(grouped["sig_a"]) == 2
    assert len(grouped["sig_b"]) == 1


def test_cluster_generates_signature_when_missing():
    obs1 = {"category": "x", "code": "y", "route_or_job": "A"}
    obs2 = {"category": "x", "code": "y", "route_or_job": "A"}
    grouped = cluster_observations([obs1, obs2])
    # Both should hash to the same generated signature → one bucket.
    assert len(grouped) == 1
    bucket = next(iter(grouped.values()))
    assert len(bucket) == 2


def test_cluster_returns_empty_dict_for_empty_input():
    assert cluster_observations([]) == {}
