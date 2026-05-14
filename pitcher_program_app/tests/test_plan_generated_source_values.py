"""'program_prescribed' is now a valid plan_generated.source value.

This test pins the canonical set so future PRs that add more sources
have to update the constant explicitly."""

from bot.services.db import VALID_PLAN_SOURCES


def test_program_prescribed_is_valid_source():
    assert "program_prescribed" in VALID_PLAN_SOURCES


def test_legacy_sources_still_valid():
    assert "python_fallback" in VALID_PLAN_SOURCES
    assert "llm_enriched" in VALID_PLAN_SOURCES


def test_canonical_set_is_immutable():
    """frozenset prevents accidental mutation by callers."""
    assert isinstance(VALID_PLAN_SOURCES, frozenset)
