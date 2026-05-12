"""Tests for the dual-pass secret redactor (A4) + observation normalization."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bot.services.system_guardian.normalize import (
    SECRET_PATTERNS,
    normalize_observation,
    redact_observation_for_emit,
    redact_text,
)


# Synthetic JWT used in the canonical A4 test. Hard-coded NOT a real token —
# the signature segment is a placeholder. We need a string that matches the
# `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` pattern.
SYNTHETIC_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJ0ZXN0In0"
    ".signature_here_padding"
)


# ---------------------------------------------------------------------------
# redact_text — pattern coverage
# ---------------------------------------------------------------------------

def test_redact_text_handles_none_and_returns_no_hits():
    out, hits = redact_text(None)
    assert out is None
    assert hits == []


def test_redact_text_no_secret_returns_unchanged():
    msg = "Pitcher kamat checked in at 08:14 with arm_feel=8"
    out, hits = redact_text(msg)
    assert out == msg
    assert hits == []


def test_redact_text_redacts_jwt():
    msg = f"Authorization header: {SYNTHETIC_JWT} (incoming)"
    out, hits = redact_text(msg)
    assert "[REDACTED:jwt]" in out
    assert SYNTHETIC_JWT not in out
    assert "jwt" in hits


def test_redact_text_redacts_telegram_token():
    # 9-digit id : 35-char base64ish suffix
    token = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
    msg = f"TELEGRAM_BOT_TOKEN={token}"
    out, hits = redact_text(msg)
    assert token not in out
    assert "[REDACTED:telegram_token]" in out
    assert "telegram_token" in hits


def test_redact_text_redacts_supabase_publishable_key():
    key = "sbp_abcdefghijklmnopqrstuvwxyz0123"
    msg = f"key {key} found in env dump"
    out, hits = redact_text(msg)
    assert key not in out
    assert "[REDACTED:supabase_key]" in out
    assert "supabase_key" in hits


def test_redact_text_redacts_supabase_secret_key():
    key = "sbs_abcdefghijklmnopqrstuvwxyz0123"
    msg = f"SUPABASE_SERVICE_KEY={key}"
    # The generic_secret pattern can also match this; either redaction kind
    # is acceptable as long as the literal secret never survives.
    out, hits = redact_text(msg)
    assert key not in out
    assert "[REDACTED:" in out
    assert hits  # at least one hit fired


def test_redact_text_redacts_oauth_bearer():
    msg = "Bearer abcdef0123456789ABCDEFGH"
    out, hits = redact_text(msg)
    assert "abcdef0123456789ABCDEFGH" not in out
    assert "[REDACTED:oauth_bearer]" in out


def test_redact_text_redacts_generic_secret_assignment():
    msg = "api_key: 'abcdefghijklmnop1234'"
    out, hits = redact_text(msg)
    assert "abcdefghijklmnop1234" not in out
    assert "[REDACTED:generic_secret]" in out


def test_redact_text_redacts_multiple_secrets_in_one_string():
    msg = (
        f"jwt={SYNTHETIC_JWT} bearer=Bearer abcdef0123456789ABCDEFGH"
    )
    out, hits = redact_text(msg)
    assert SYNTHETIC_JWT not in out
    assert "abcdef0123456789ABCDEFGH" not in out
    assert "jwt" in hits and "oauth_bearer" in hits


def test_secret_patterns_module_constant_exposed():
    # Surface check: the patterns list is the single source of truth and
    # must be importable so callers can introspect it (e.g. tests, future
    # admin diagnostics).
    assert isinstance(SECRET_PATTERNS, list)
    assert all(isinstance(item, tuple) and len(item) == 2 for item in SECRET_PATTERNS)
    kinds = {kind for kind, _ in SECRET_PATTERNS}
    assert {"jwt", "telegram_token", "supabase_key", "oauth_bearer", "generic_secret"} <= kinds


# ---------------------------------------------------------------------------
# Read-time redactor
# ---------------------------------------------------------------------------

def test_redact_observation_for_emit_handles_message_stack_samples():
    obs = {
        "message": f"see token {SYNTHETIC_JWT}",
        "stack": f"Traceback: header Authorization: {SYNTHETIC_JWT}",
        "sample_messages": [
            f"sample 1 has {SYNTHETIC_JWT}",
            {"message": f"nested sample with {SYNTHETIC_JWT}"},
            42,  # non-string non-dict — pass through
        ],
    }
    out = redact_observation_for_emit(obs)
    assert SYNTHETIC_JWT not in out["message"]
    assert SYNTHETIC_JWT not in out["stack"]
    assert SYNTHETIC_JWT not in out["sample_messages"][0]
    assert SYNTHETIC_JWT not in out["sample_messages"][1]["message"]
    assert out["sample_messages"][2] == 42


def test_redact_observation_for_emit_does_not_mutate_input():
    obs = {"message": f"hi {SYNTHETIC_JWT}"}
    snapshot = dict(obs)
    redact_observation_for_emit(obs)
    assert obs == snapshot


def test_redact_observation_for_emit_passes_non_dict_through():
    assert redact_observation_for_emit("hello") == "hello"
    assert redact_observation_for_emit(None) is None


# ---------------------------------------------------------------------------
# normalize_observation
# ---------------------------------------------------------------------------

def test_normalize_observation_fills_required_defaults():
    out = normalize_observation({"message": "hello world"})
    assert out["source"] == "guardian"
    assert out["event_type"] == "observation"
    assert out["observed_at"]
    assert out["signature"]  # generated
    assert out["metadata"] == {}
    assert "_redaction_hits" in out
    assert out["_redaction_hits"] == []


def test_normalize_observation_runs_write_time_redactor_on_message():
    out = normalize_observation(
        {"message": f"trace contained {SYNTHETIC_JWT}", "category": "runtime_error"}
    )
    assert SYNTHETIC_JWT not in out["message"]
    assert "[REDACTED:jwt]" in out["message"]
    assert "jwt" in out["_redaction_hits"]


def test_normalize_observation_runs_write_time_redactor_on_stack():
    out = normalize_observation(
        {
            "message": "ok",
            "stack": f"Traceback: {SYNTHETIC_JWT}",
            "category": "runtime_error",
        }
    )
    assert SYNTHETIC_JWT not in out["stack"]
    assert "jwt" in out["_redaction_hits"]


def test_normalize_observation_preserves_explicit_signature():
    out = normalize_observation(
        {"message": "x", "signature": "explicit_sig_xyz"}
    )
    assert out["signature"] == "explicit_sig_xyz"


def test_normalize_observation_invalid_metadata_replaced_with_empty_dict():
    out = normalize_observation({"message": "x", "metadata": "not-a-dict"})
    assert out["metadata"] == {}


# ---------------------------------------------------------------------------
# A4 canonical synthetic-JWT test —
# (a) row has [REDACTED:jwt] in `message`
# (b) security_posture incident with severity critical was created
# (c) original JWT does NOT appear anywhere in the persisted record
# ---------------------------------------------------------------------------

def test_synthetic_jwt_redacted_and_security_posture_incident_emitted():
    """Canonical A4 test from the build brief."""
    from bot.services.system_guardian import store

    raw_observation = {
        "source": "test_collector",
        "event_type": "runtime_log",
        "route_or_job": "POST /api/chat",
        "message": (
            "Authorization header leaked: " + SYNTHETIC_JWT + " into log line"
        ),
        "metadata": {"request_id": "req_001"},
    }

    # Capture every insert payload that the storage layer hands to Supabase.
    captured_inserts: list[dict] = []
    captured_incident_payloads: list[dict] = []

    class _FakeQuery:
        def __init__(self, table_name):
            self.table_name = table_name
            self._select = False
            self._eq_value = None

        def insert(self, payload):
            if self.table_name == "system_observations":
                captured_inserts.append(payload)
            elif self.table_name == "system_incidents":
                captured_incident_payloads.append(payload)
            return self

        def select(self, *a, **kw):
            self._select = True
            return self

        def eq(self, field, value):
            self._eq_value = value
            return self

        def update(self, payload):
            return self

        def execute(self):
            class _Resp:
                data = []

            return _Resp()

    class _FakeClient:
        def table(self, name):
            return _FakeQuery(name)

    with patch("bot.services.system_guardian.store._db.get_client", return_value=_FakeClient()):
        store.insert_observation(raw_observation)

    # Two observations should have been inserted: the original (redacted)
    # row + the paired security_posture observation.
    assert len(captured_inserts) >= 2, (
        "Expected the original observation insert + the paired "
        f"security_posture insert; got {len(captured_inserts)}"
    )

    # (a) original row's `message` is redacted.
    original_row = captured_inserts[0]
    assert "[REDACTED:jwt]" in original_row["message"]
    assert SYNTHETIC_JWT not in original_row["message"]

    # Walk every captured payload to assert NO insert contains the literal
    # JWT. This is the strongest version of (c): not just the message column,
    # but no field anywhere.
    import json as _json
    for payload in captured_inserts + captured_incident_payloads:
        serialized = _json.dumps(payload, default=str)
        assert SYNTHETIC_JWT not in serialized, (
            f"Synthetic JWT survived into a persisted payload: {payload}"
        )

    # (b) security_posture incident emitted, severity critical.
    assert captured_incident_payloads, "Expected a security_posture incident insert"
    incident = captured_incident_payloads[0]
    assert incident["category"] == "security_posture"
    assert incident["severity"] == "critical"
