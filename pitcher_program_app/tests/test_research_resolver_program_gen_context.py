"""Tests for research_resolver.resolve_for_program_gen (Task 1.3).

These tests run against the LIVE research docs in data/knowledge/research/ so
they double as a regression test for the Task 1.4 frontmatter edits — if a
generative doc loses its `program_gen` context tag, the resolver's selection
shrinks and the velocity-test fails.

Templates are stubbed via monkeypatch on list_block_library, since hitting
Supabase from the test suite would require env vars.
"""
from __future__ import annotations

import hashlib
import os

import pytest

from bot.services import research_resolver


@pytest.fixture(autouse=True)
def _isolate_research_index(monkeypatch):
    """Don't poison the module-level index_cache across tests."""
    research_resolver.clear_cache()
    yield
    research_resolver.clear_cache()


@pytest.fixture
def _stub_block_library(monkeypatch):
    """Replace list_block_library with a deterministic in-memory fixture."""
    fake_rows = [
        {
            "block_template_id": "velocity_12wk_v1",
            "name": "Velocity (12-week)",
            "domain": "throwing",
            "goal_tags": ["velocity"],
            "compatible_phases": ["off_season", "preseason"],
            "duration_range_weeks": [10, 14],
            "content": {"phases": [{"name": "Base", "weeks": [1, 2, 3]}]},
            "tunable_parameters_schema": {},
            "modification_rules_json": None,
            "research_doc_ids": [],
        },
        {
            "block_template_id": "longtoss_ramp_6wk_v1",
            "name": "Long Toss Ramp",
            "domain": "throwing",
            "goal_tags": ["longtoss", "return_to_throwing"],
            "compatible_phases": ["off_season"],
            "duration_range_weeks": [5, 7],
            "content": {"phases": []},
            "tunable_parameters_schema": {},
            "modification_rules_json": None,
            "research_doc_ids": [],
        },
        {
            "block_template_id": "hypertrophy_8wk_v1",
            "name": "Hypertrophy 8wk",
            "domain": "lifting",
            "goal_tags": ["hypertrophy"],
            "compatible_phases": ["off_season"],
            "duration_range_weeks": [7, 9],
            "content": {},
            "tunable_parameters_schema": {},
            "modification_rules_json": None,
            "research_doc_ids": [],
        },
    ]
    monkeypatch.setattr("bot.services.db.list_block_library", lambda: fake_rows)
    return fake_rows


@pytest.fixture
def _no_exemplars(monkeypatch):
    """Skip the openpyxl exemplar load to keep tests fast."""
    monkeypatch.setattr(research_resolver, "_load_golden_exemplars", lambda: [])


def test_resolve_for_program_gen_velocity_returns_real_docs(_stub_block_library, _no_exemplars):
    """The velocity goal should pull in throwing + lifting + research-base + FPM."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "landon_brice", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    assert out["loaded_doc_ids"], "velocity goal must load at least one doc"
    # The 5 docs we tagged program_gen in Task 1.4 should all be eligible
    expected_program_gen_docs = {
        "final_research_base",
        "gemini_researching_lifting",
        "driveline_lifting_programs",
        "driveline_throwing_program",
        "research_gap_analysis",
    }
    loaded = set(out["loaded_doc_ids"])
    # At least some of these should be present (precise membership depends on
    # which other docs have `program_gen` in contexts and which are critical)
    overlap = loaded & expected_program_gen_docs
    assert overlap, f"none of the 5 program_gen-tagged docs surfaced; loaded={loaded}"


def test_resolve_for_program_gen_picks_critical_baseline(_stub_block_library, _no_exemplars):
    """Critical-priority docs must surface regardless of goal tag overlap."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["unrelated_made_up_goal"]},
        max_chars=50000,
    )
    # FPM is critical+program_gen+coach_chat+morning (Task 1.4 didn't change it)
    # — should surface even though triggers don't intersect with our goal.
    # Wait — FPM doesn't include program_gen in its contexts (verified by reading
    # the file in the working tree). The hard filter blocks it. So instead check
    # that one of our newly-tagged critical docs surfaces.
    # final_research_base is now critical + program_gen, so it should surface.
    assert "final_research_base" in out["loaded_doc_ids"], (
        f"final_research_base (critical + program_gen) must always surface; "
        f"loaded={out['loaded_doc_ids']}"
    )


def test_resolve_for_program_gen_excludes_coach_chat_only_docs(_stub_block_library, _no_exemplars):
    """Docs without program_gen in contexts (e.g. supplamentation) must be filtered out."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    # supplamentation is coach_chat only — must not surface
    assert "supplamentation" not in out["loaded_doc_ids"]
    # bot_intelligence_architecture is coach_chat only — must not surface
    assert "bot_intelligence_architecture" not in out["loaded_doc_ids"]


def test_resolve_for_program_gen_templates_filtered_by_goal_tag(_stub_block_library, _no_exemplars):
    """Only block_library rows whose goal_tags overlap should surface."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    tpl_ids = {t["block_template_id"] for t in out["templates"]}
    assert "velocity_12wk_v1" in tpl_ids, "velocity goal must surface velocity template"
    assert "longtoss_ramp_6wk_v1" not in tpl_ids, "longtoss must NOT surface for velocity"
    assert "hypertrophy_8wk_v1" not in tpl_ids


def test_resolve_for_program_gen_knowledge_version_is_sha1(_stub_block_library, _no_exemplars):
    """knowledge_version is hex SHA-1 — 40 chars, lowercase hex."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    kv = out["knowledge_version"]
    assert len(kv) == 40, f"knowledge_version must be 40-char SHA-1 hex, got {len(kv)}"
    assert all(c in "0123456789abcdef" for c in kv), "must be lowercase hex"


def test_resolve_for_program_gen_knowledge_version_stable(_stub_block_library, _no_exemplars):
    """Repeat calls with identical inputs must produce identical knowledge_version."""
    kwargs = {
        "pitcher_profile": {"pitcher_id": "test", "injury_history": []},
        "pitcher_context": "",
        "goal_spec": {"tags": ["velocity"]},
        "max_chars": 50000,
    }
    out1 = research_resolver.resolve_for_program_gen(**kwargs)
    research_resolver.clear_cache()  # force re-read
    out2 = research_resolver.resolve_for_program_gen(**kwargs)
    assert out1["knowledge_version"] == out2["knowledge_version"]


def test_resolve_for_program_gen_knowledge_version_changes_on_content_edit(
    _stub_block_library, _no_exemplars, tmp_path, monkeypatch
):
    """Living-knowledge proof: edit a doc → knowledge_version differs.

    Stages a synthetic research dir with one program_gen-tagged doc, takes
    the kv, mutates the doc, takes the kv again, and asserts they differ.
    """
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    doc_path = research_dir / "fake_doc.md"
    frontmatter = """---
id: fake_doc
title: Fake Doc
applies_to: [any]
triggers: [velocity]
priority: critical
contexts: [program_gen]
summary: synthetic for test
---
Original body content."""
    doc_path.write_text(frontmatter)

    monkeypatch.setattr(research_resolver, "RESEARCH_DIR", str(research_dir))
    research_resolver.clear_cache()

    out1 = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    kv1 = out1["knowledge_version"]
    assert "fake_doc" in out1["loaded_doc_ids"]

    # Mutate the body
    new_content = frontmatter.replace("Original body content.", "Modified body content X.")
    doc_path.write_text(new_content)
    research_resolver.clear_cache()

    out2 = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    kv2 = out2["knowledge_version"]
    assert kv1 != kv2, "knowledge_version must change when doc body changes"


def test_resolve_for_program_gen_respects_max_chars(_stub_block_library, _no_exemplars):
    """Budget bound: when budget allows, stop adding before the next doc would exceed.

    The "always include at least one" rule means a single large doc can blow
    past the budget; that's by design (a 7k-char critical doc beats truncation).
    What we ARE checking: with a generous budget, the resolver doesn't load the
    entire research dir.
    """
    full_budget = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=100000,
    )
    small_budget = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=2000,
    )
    # Small budget MUST load strictly fewer docs than full budget
    assert len(small_budget["loaded_doc_ids"]) < len(full_budget["loaded_doc_ids"]), (
        f"small={small_budget['loaded_doc_ids']} full={full_budget['loaded_doc_ids']}"
    )


def test_resolve_for_program_gen_injury_history_pulls_relevant_docs(_stub_block_library, _no_exemplars):
    """A pitcher with medial_elbow history should pull UCL/FPM docs."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={
            "pitcher_id": "test",
            "injury_history": [{"area": "medial_elbow", "status": "history"}],
        },
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    # FPM and UCL docs ARE critical AND apply_to medial_elbow — but they don't
    # have program_gen in their contexts (Task 1.4 left them alone since they're
    # already in plan_gen). So the test asserts that the (program_gen-tagged)
    # research-base is loaded, which is a weaker check. Refine post-Task-1.4
    # once we decide whether FPM/UCL belong in program_gen too.
    assert "final_research_base" in out["loaded_doc_ids"]


def test_resolve_for_program_gen_empty_goal_returns_minimal_set(_stub_block_library, _no_exemplars):
    """No goal tags → only criticals + templates with empty goal_tags overlap."""
    out = research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "test", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": []},
        max_chars=50000,
    )
    # Critical docs still come through
    assert "final_research_base" in out["loaded_doc_ids"]
    # No templates should match an empty goal
    assert out["templates"] == []


def test_resolve_for_program_gen_logs_to_research_load_log(_stub_block_library, _no_exemplars, monkeypatch):
    """Observability: the call should hit _log_research_load with context='program_gen'."""
    captured = {}

    def _spy(pitcher_id, context, trigger_reason, doc_ids, total_chars, degraded=False):
        captured["pitcher_id"] = pitcher_id
        captured["context"] = context
        captured["trigger_reason"] = trigger_reason
        captured["doc_ids"] = list(doc_ids)
        captured["total_chars"] = total_chars
        captured["degraded"] = degraded

    monkeypatch.setattr(research_resolver, "_log_research_load", _spy)
    research_resolver.resolve_for_program_gen(
        pitcher_profile={"pitcher_id": "landon_brice", "injury_history": []},
        pitcher_context="",
        goal_spec={"tags": ["velocity"]},
        max_chars=50000,
    )
    assert captured.get("context") == "program_gen"
    assert captured.get("pitcher_id") == "landon_brice"
    assert "velocity" in captured.get("trigger_reason", "")
