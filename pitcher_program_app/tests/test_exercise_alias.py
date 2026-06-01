"""Tests for bot.services.exercise_alias (Program Engine Task 0.1).

Source-of-truth note: this module reads from the live `exercises.aliases`
jsonb column. Tests monkeypatch `get_exercises` (the same seam exercise_pool
tests use) so they don't hit Supabase.
"""

import pytest

from bot.services import exercise_alias
from bot.services.exercise_alias import (
    UnknownExerciseAlias,
    audit_names,
    refresh_index,
    resolve_alias,
    try_resolve_alias,
)


@pytest.fixture(autouse=True)
def _seed_index(monkeypatch):
    """Reset module state + install a minimal exercises snapshot for every test."""
    rows = [
        {
            "id": "ex_004",
            "name": "Rear-Foot-Elevated Split Squat",
            "aliases": ["Bulgarian split squat", "RFESS", "DB Bulgarian split squat"],
        },
        {
            "id": "ex_020",
            "name": "Chest-Supported Row",
            "aliases": ["seal row", "incline DB row"],
        },
        {
            "id": "ex_041",
            "name": "Pronator Teres Isolation",
            "aliases": ["full pronation", "DB pronation"],
        },
        {
            "id": "ex_070",
            "name": "Flexor Pressout",
            "aliases": ["flexor press out"],
        },
    ]
    monkeypatch.setattr("bot.services.exercise_alias.get_exercises", lambda: rows)
    refresh_index()
    yield
    refresh_index()


def test_resolve_canonical_name():
    assert resolve_alias("Chest-Supported Row") == "ex_020"


def test_resolve_alias_string():
    assert resolve_alias("seal row") == "ex_020"
    assert resolve_alias("Bulgarian split squat") == "ex_004"


def test_case_insensitive():
    assert resolve_alias("CHEST-SUPPORTED ROW") == "ex_020"
    assert resolve_alias("bulgarian SPLIT squat") == "ex_004"


def test_whitespace_normalization():
    assert resolve_alias("  Chest-Supported   Row  ") == "ex_020"


def test_punctuation_normalization():
    # Hyphen drops, period drops, parentheses drop
    assert resolve_alias("Chest Supported Row") == "ex_020"
    assert resolve_alias("Chest, Supported. Row.") == "ex_020"


def test_unknown_raises_with_name_attribute():
    with pytest.raises(UnknownExerciseAlias) as exc_info:
        resolve_alias("Glute Bridge Variation X")
    # Phase 2.3 guardrail loop relies on the .name attribute to re-prompt the LLM
    assert exc_info.value.name == "Glute Bridge Variation X"


def test_empty_string_raises():
    with pytest.raises(UnknownExerciseAlias):
        resolve_alias("")


def test_non_string_raises():
    with pytest.raises(UnknownExerciseAlias):
        resolve_alias(None)


def test_try_resolve_returns_none_on_miss():
    assert try_resolve_alias("Nonexistent Exercise") is None
    assert try_resolve_alias("seal row") == "ex_020"


def test_audit_names_partitions_resolved_vs_unresolved():
    out = audit_names(
        [
            "seal row",
            "Bulgarian split squat",
            "Flexor pressout",
            "Some Made Up Exercise",
            "another unknown one",
        ]
    )
    assert "seal row" in out["resolved"]
    assert "Bulgarian split squat" in out["resolved"]
    assert "Flexor pressout" in out["resolved"]
    assert "Some Made Up Exercise" in out["unresolved"]
    assert "another unknown one" in out["unresolved"]


def test_audit_names_dedupes_by_normalized_key():
    out = audit_names(["seal row", "SEAL ROW", "  seal row  "])
    # All three normalize to the same key — only one entry in resolved.
    assert len(out["resolved"]) == 1


def test_audit_names_ignores_blank_and_non_string():
    out = audit_names(["seal row", "", "  ", None, 42, "Bulgarian split squat"])
    assert "seal row" in out["resolved"]
    assert "Bulgarian split squat" in out["resolved"]
    # Blanks and non-strings are silently filtered, not counted as unresolved
    assert out["unresolved"] == []


def test_refresh_index_picks_up_supabase_changes(monkeypatch):
    # First resolve binds the index
    assert resolve_alias("seal row") == "ex_020"
    # Simulate a Supabase alias edit: now seal row points elsewhere
    new_rows = [
        {"id": "ex_999", "name": "New Row Variant", "aliases": ["seal row"]},
    ]
    monkeypatch.setattr("bot.services.exercise_alias.get_exercises", lambda: new_rows)
    # Without refresh, the stale index still wins
    assert resolve_alias("seal row") == "ex_020"
    # After refresh, the new mapping is live
    refresh_index()
    assert resolve_alias("seal row") == "ex_999"


def test_alias_overrides_canonical_on_collision():
    """If an alias on row B collides with row A's canonical name, alias wins.

    This is deliberate: aliases are operator-curated overrides. The audit
    script surfaces collisions so they don't go silent.
    """
    rows = [
        {"id": "ex_A", "name": "Shared Name", "aliases": []},
        {"id": "ex_B", "name": "Other", "aliases": ["Shared Name"]},
    ]
    import bot.services.exercise_alias as mod

    # Replace the seam, refresh, resolve
    original = mod.get_exercises
    mod.get_exercises = lambda: rows  # type: ignore
    try:
        refresh_index()
        assert resolve_alias("Shared Name") == "ex_B"
    finally:
        mod.get_exercises = original
        refresh_index()


def test_get_exercises_failure_keeps_last_good(monkeypatch, caplog):
    """A Supabase outage during refresh must not nuke the in-memory index."""
    assert resolve_alias("seal row") == "ex_020"  # warm

    def boom():
        raise RuntimeError("transient Supabase outage")

    monkeypatch.setattr("bot.services.exercise_alias.get_exercises", boom)
    # Don't call refresh_index (it clears the index); simulate a failed rebuild
    # by directly invoking _build_index — it should log + return without
    # clearing the prior data.
    exercise_alias._build_index()
    # Existing entry still works
    assert resolve_alias("seal row") == "ex_020"
