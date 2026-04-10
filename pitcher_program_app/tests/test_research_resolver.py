"""Tests for the unified research resolver."""

import pytest


@pytest.fixture(autouse=True)
def clear_resolver_cache():
    from bot.services.research_resolver import clear_cache
    clear_cache()
    yield
    clear_cache()


def test_parse_frontmatter_extracts_new_fields():
    from bot.services.research_resolver import _parse_frontmatter
    text = """---
id: test_doc
title: Test Document
keywords: [test, foo]
type: core_research
applies_to:
  - medial_elbow
  - forearm
triggers:
  - fpm
  - ucl_history
phase: any
priority: critical
contexts:
  - plan_gen
  - coach_chat
summary: A test document.
---
Body content here.
"""
    fm = _parse_frontmatter(text)
    assert fm["id"] == "test_doc"
    assert fm["title"] == "Test Document"
    assert "medial_elbow" in fm["applies_to"]
    assert "fpm" in fm["triggers"]
    assert fm["priority"] == "critical"
    assert "plan_gen" in fm["contexts"]
    assert "test document" in fm["summary"].lower()


def test_parse_frontmatter_missing_new_fields_returns_defaults():
    from bot.services.research_resolver import _parse_frontmatter
    text = """---
keywords: [test]
type: core_research
---
Old style doc.
"""
    fm = _parse_frontmatter(text)
    assert fm["id"] == ""
    assert fm["applies_to"] == []
    assert fm["triggers"] == []
    assert fm["priority"] == "standard"
    assert fm["contexts"] == ["plan_gen", "coach_chat", "morning", "daily_plan_why"]


def test_should_fire_research_non_green():
    from bot.services.research_resolver import should_fire_research
    profile = {"injury_history": []}
    triage = {"flag_level": "yellow", "modifications": []}
    fire, reason = should_fire_research(profile, triage)
    assert fire is True
    assert "flag_level=yellow" in reason


def test_should_fire_research_green_no_mods():
    from bot.services.research_resolver import should_fire_research
    profile = {"injury_history": [], "rotation_length": 7}
    triage = {"flag_level": "green", "modifications": []}
    fire, reason = should_fire_research(profile, triage)
    assert fire is False


def test_should_fire_research_keyword_match():
    from bot.services.research_resolver import should_fire_research
    profile = {"injury_history": []}
    fire, reason = should_fire_research(profile, user_message="my elbow is tight")
    assert fire is True
    assert "keyword:" in reason


def test_resolve_research_returns_payload():
    from bot.services.research_resolver import resolve_research, ResearchPayload
    profile = {"injury_history": [{"area": "medial_elbow"}]}
    payload = resolve_research(profile, "plan_gen")
    assert isinstance(payload, ResearchPayload)
    assert isinstance(payload.combined_text, str)
    assert isinstance(payload.loaded_docs, list)


def test_resolve_research_critical_always_loads():
    from bot.services.research_resolver import resolve_research
    profile = {"injury_history": []}
    payload = resolve_research(profile, "plan_gen")
    critical_ids = [d.id for d in payload.loaded_docs if d.priority == "critical"]
    assert "tightness_triage_framework" in critical_ids
    assert "recovery_physiology" in critical_ids


def test_resolve_research_context_filter():
    from bot.services.research_resolver import resolve_research
    profile = {"injury_history": []}
    payload = resolve_research(profile, "daily_plan_why")
    for doc in payload.loaded_docs:
        assert "daily_plan_why" in doc.contexts or doc.priority == "critical"
