# Research-Aware Coaching Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the knowledge base into four surfaces (coach chat, plan gen, morning notification, daily plan "why") through a unified resolver, with proactive mutation cards and deterministic safety guarantees.

**Architecture:** A single `research_resolver.py` replaces all research-routing logic. Frontmatter on each research doc declares applicability. A shared `vocabulary.py` provides canonical injury areas and modification tags used by triage, exercise pool, and the resolver. Coach chat returns structured JSON (reply + mutation card + lookahead) on every triggered turn. Morning notifications get two-pass LLM enrichment with Python fallback.

**Tech Stack:** Python 3.11 / FastAPI / python-telegram-bot v20 / Supabase / React 18 / Tailwind

**Spec:** `docs/superpowers/specs/2026-04-10-research-aware-coaching-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `bot/services/vocabulary.py` | CREATE | Canonical injury areas, modification tags, shared by all services |
| `bot/services/research_resolver.py` | CREATE | Unified resolver: `resolve_research()`, `should_fire_research()`, frontmatter parsing, observability logging |
| `bot/prompts/coach_chat_prompt.md` | CREATE | Prompt template for research-aware coach turns with structured JSON output |
| `bot/prompts/morning_message.md` | CREATE | Prompt template for LLM-enriched morning notifications |
| `tests/test_vocabulary.py` | CREATE | Tests for vocabulary data integrity |
| `tests/test_research_resolver.py` | CREATE | Tests for resolver logic, trigger function, frontmatter parsing |
| `tests/test_research_coverage.py` | CREATE | CI coverage tests: every mod tag has research, every injury area has critical doc |
| `tests/test_coach_chat.py` | CREATE | Tests for structured output parsing, mutation card generation, fallback |
| `data/knowledge/research/*.md` (14 files) | MODIFY | Add new frontmatter schema to all research MDs |
| `bot/services/knowledge_retrieval.py` | MODIFY | Old functions become thin wrappers around `resolve_research()` |
| `bot/services/triage.py` | MODIFY | Emit `MODIFICATION_TAGS` keys instead of freeform strings |
| `bot/services/exercise_pool.py` | MODIFY | Import `INJURY_TO_FLAG` from `vocabulary.py` |
| `bot/services/plan_generator.py` | MODIFY | Use resolver, persist `research_sources` on daily_entry |
| `bot/services/db.py` | MODIFY | Add `research_sources` to `_DAILY_ENTRY_COLUMNS` |
| `bot/handlers/qa.py` | MODIFY | Research-aware flow with structured output + mutation card |
| `api/routes.py` | MODIFY | Coach chat: parse structured output, return mutation card; new `GET /api/research/docs` endpoint |
| `bot/main.py` | MODIFY | Two-pass morning notification with LLM enrichment |
| `mini-app/src/components/DailyCard.jsx` | MODIFY | "Why today looks different" info icon + bottom sheet |

---

## Task 1: Shared Vocabulary (`bot/services/vocabulary.py`)

**Files:**
- Create: `pitcher_program_app/bot/services/vocabulary.py`
- Create: `pitcher_program_app/tests/test_vocabulary.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vocabulary.py
"""Tests for shared vocabulary — injury areas, modification tags."""


def test_injury_areas_have_keywords():
    from bot.services.vocabulary import INJURY_AREAS
    for area, meta in INJURY_AREAS.items():
        assert isinstance(meta["keywords"], list), f"{area} missing keywords"
        assert len(meta["keywords"]) > 0, f"{area} has empty keywords"
        assert isinstance(meta["research_triggers"], list), f"{area} missing research_triggers"


def test_modification_tags_have_descriptions():
    from bot.services.vocabulary import MODIFICATION_TAGS
    for tag, meta in MODIFICATION_TAGS.items():
        assert "description" in meta, f"{tag} missing description"
        assert "research_triggers" in meta, f"{tag} missing research_triggers"
        assert len(meta["research_triggers"]) > 0, f"{tag} has empty research_triggers"


def test_injury_areas_keys_are_snake_case():
    from bot.services.vocabulary import INJURY_AREAS
    import re
    for area in INJURY_AREAS:
        assert re.match(r"^[a-z][a-z0-9_]*$", area), f"{area} is not snake_case"


def test_modification_tags_keys_are_snake_case():
    from bot.services.vocabulary import MODIFICATION_TAGS
    import re
    for tag in MODIFICATION_TAGS:
        assert re.match(r"^[a-z][a-z0-9_]*$", tag), f"{tag} is not snake_case"


def test_all_trigger_keywords_lowercase():
    from bot.services.vocabulary import INJURY_AREAS
    for area, meta in INJURY_AREAS.items():
        for kw in meta["keywords"]:
            assert kw == kw.lower(), f"{area} keyword '{kw}' not lowercase"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pitcher_program_app && python -m pytest tests/test_vocabulary.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'bot.services.vocabulary'"

- [ ] **Step 3: Write the implementation**

```python
# bot/services/vocabulary.py
"""Shared vocabulary — canonical injury areas and modification tags.

Single source of truth consumed by triage, exercise_pool, and research_resolver.
Adding a new injury area or modification tag here is the ONLY place you need to
update — downstream consumers import from this module.
"""

# Maps injury area (from pitcher_profile.injury_history[*].area) to:
#   keywords: terms for matching free-text and research doc triggers
#   research_triggers: tags that research docs use in their frontmatter `triggers` field
INJURY_AREAS = {
    "medial_elbow": {
        "keywords": ["ucl", "flexor", "pronator", "fpm", "medial", "elbow"],
        "research_triggers": ["fpm", "ucl_history"],
    },
    "forearm": {
        "keywords": ["forearm", "flexor", "pronator", "fpm"],
        "research_triggers": ["fpm"],
    },
    "shoulder": {
        "keywords": ["shoulder", "scapular", "external rotation", "labrum", "gird", "impingement"],
        "research_triggers": ["arm_care", "shoulder_protection"],
    },
    "lower_back": {
        "keywords": ["back", "lumbar", "axial", "spine"],
        "research_triggers": ["workload"],
    },
    "oblique": {
        "keywords": ["oblique", "rotational", "core"],
        "research_triggers": ["workload"],
    },
    "hip": {
        "keywords": ["hip", "mobility", "flexor"],
        "research_triggers": ["mobility"],
    },
    "knee": {
        "keywords": ["knee", "patellar", "quad"],
        "research_triggers": ["lower_body"],
    },
    "ulnar_nerve": {
        "keywords": ["ulnar", "nerve", "numbness", "tingling"],
        "research_triggers": ["ucl_history", "nerve"],
    },
}

# Maps modification tag keys (emitted by triage.py) to:
#   description: human-readable text for logging and UI
#   research_triggers: tags to match against research doc frontmatter
MODIFICATION_TAGS = {
    "fpm_volume": {
        "description": "Elevated FPM volume — tightness flagged with elbow history",
        "research_triggers": ["fpm", "ucl_history"],
    },
    "reduce_pressing": {
        "description": "Drop pressing movements",
        "research_triggers": ["fpm", "shoulder_protection"],
    },
    "rpe_cap_56": {
        "description": "Reduce all loads to RPE 5-6",
        "research_triggers": ["recovery", "workload"],
    },
    "rpe_cap_67": {
        "description": "Reduce loads to RPE 6-7",
        "research_triggers": ["recovery"],
    },
    "maintain_compounds_reduced": {
        "description": "Maintain compounds at reduced intensity",
        "research_triggers": ["recovery"],
    },
    "no_high_intent_throw": {
        "description": "No high-intent throwing — recovery plyo + light catch only",
        "research_triggers": ["recovery", "throwing"],
    },
    "cap_hybrid_b": {
        "description": "Cap throwing at Hybrid B — no compression throws or pulldowns",
        "research_triggers": ["throwing"],
    },
    "no_lifting": {
        "description": "No lifting today — mobility and recovery only",
        "research_triggers": ["recovery"],
    },
    "no_throwing": {
        "description": "No throwing — light catch only if arm feels OK",
        "research_triggers": ["recovery"],
    },
    "primer_session": {
        "description": "Primer session only — start within 48h",
        "research_triggers": ["workload"],
    },
    "low_volume_activation": {
        "description": "Low volume, activation focus",
        "research_triggers": ["workload"],
    },
    "modified_green": {
        "description": "Modified green — proceed with awareness",
        "research_triggers": [],
    },
    "elevated_fpm_history": {
        "description": "Elevated FPM volume per injury history flag",
        "research_triggers": ["fpm"],
    },
    "expected_soreness_override": {
        "description": "Expected soreness — pitcher confirms normal for rotation",
        "research_triggers": [],
    },
}


def get_all_trigger_keywords() -> set[str]:
    """Return the union of all keywords from all injury areas.

    Used by should_fire_research() to detect injury-related language
    in free-text coach messages without hardcoding.
    """
    keywords = set()
    for meta in INJURY_AREAS.values():
        keywords.update(meta["keywords"])
    return keywords


def get_research_triggers_for_injury(area: str) -> list[str]:
    """Return research_triggers for a given injury area, or empty list if unknown."""
    meta = INJURY_AREAS.get(area, {})
    return meta.get("research_triggers", [])


def get_research_triggers_for_mod(tag: str) -> list[str]:
    """Return research_triggers for a given modification tag, or empty list if unknown."""
    meta = MODIFICATION_TAGS.get(tag, {})
    return meta.get("research_triggers", [])


def get_mod_description(tag: str) -> str:
    """Return human-readable description for a modification tag."""
    meta = MODIFICATION_TAGS.get(tag, {})
    return meta.get("description", tag.replace("_", " "))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd pitcher_program_app && python -m pytest tests/test_vocabulary.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd pitcher_program_app
git add bot/services/vocabulary.py tests/test_vocabulary.py
git commit -m "feat: add shared vocabulary for injury areas and modification tags"
```

---

## Task 2: Research Doc Frontmatter Migration

**Files:**
- Modify: `pitcher_program_app/data/knowledge/research/*.md` (14 files, skip INDEX.md)

This task adds the new frontmatter schema to every research doc. The old `keywords` + `type` fields are kept for backward compatibility until Task 4 (resolver) replaces the parser.

- [ ] **Step 1: Add frontmatter to `tightness_triage_framework.md`**

Replace the existing frontmatter:
```yaml
---
keywords: [triage, protocol, flag, red, yellow, green, worried, concern, sharp, numb, tingling, swelling, shut down, skip, day off, should i throw, modify, modification, back off, push through, can i throw, what should i do]
type: core_research
---
```

With:
```yaml
---
id: tightness_triage_framework
title: Tightness Triage Protocol Decision Framework
keywords: [triage, protocol, flag, red, yellow, green, worried, concern, sharp, numb, tingling, swelling, shut down, skip, day off, should i throw, modify, modification, back off, push through, can i throw, what should i do]
type: core_research
applies_to:
  - any
triggers:
  - triage
  - flag
  - modification
  - worried
  - concern
  - should_i_throw
phase: any
priority: critical
contexts:
  - plan_gen
  - coach_chat
  - morning
  - daily_plan_why
summary: >
  Codifies clinical reasoning for protocol decisions — translates symptom inputs
  into flag levels and protocol adjustments based on injury history.
---
```

- [ ] **Step 2: Add frontmatter to `recovery_physiology.md`**

Replace existing frontmatter with:
```yaml
---
id: recovery_physiology
title: Post-Outing Recovery Physiology
keywords: [recovery, sore, soreness, ice, inflammation, sleep, hrv, rest, fatigue, tired, ache, stiff, pain, hurt, nsaid, ibuprofen, stretch, mobility, warm, heat, blood flow, massage, foam roll, doms, post-outing, cool down]
type: core_research
applies_to:
  - any
triggers:
  - recovery
  - soreness
  - rest
  - post_outing
  - doms
phase: any
priority: critical
contexts:
  - plan_gen
  - coach_chat
  - morning
  - daily_plan_why
summary: >
  Explains the physiological cascade after pitching — eccentric loading, DOMS timeline,
  and evidence-based recovery protocols for the 24-72hr window.
---
```

- [ ] **Step 3: Add frontmatter to `ucl_flexor_pronator_protection.md`**

Replace existing frontmatter with:
```yaml
---
id: ucl_flexor_pronator_protection
title: UCL Flexor-Pronator Protection Protocol
keywords: [ucl, flexor, pronator, medial, elbow, forearm, tight, tightness, valgus, ligament, dynamic stabilization, fpm, injury, protect, prevent, arm]
type: core_research
applies_to:
  - medial_elbow
  - forearm
triggers:
  - fpm
  - ucl_history
  - flexor
  - pronator
  - medial_elbow
phase: any
priority: critical
contexts:
  - plan_gen
  - coach_chat
  - morning
  - daily_plan_why
summary: >
  Protective protocol for pitchers with UCL or flexor-pronator history — defines
  pressing restrictions, FPM addon prescriptions, and yellow-day modifications.
---
```

- [ ] **Step 4: Add frontmatter to `FPM.md`**

Replace existing frontmatter with:
```yaml
---
id: fpm_strain_protocol
title: Flexor-Pronator Mass Strain Protocol
keywords: [fpm, flexor, pronator, medial elbow, ucl, tightness, strain, isometric, acute, pain, yellow flag, loading, wrist flexion, forearm, guarding]
type: core_research
applies_to:
  - medial_elbow
  - forearm
triggers:
  - fpm
  - ucl_history
  - flexor
  - strain
  - forearm_tightness
phase: any
priority: critical
contexts:
  - plan_gen
  - coach_chat
  - morning
  - daily_plan_why
summary: >
  Acute FPM strain management — isometric loading protocol, yellow-flag criteria,
  and return-to-throwing decision framework for flexor-pronator injuries.
---
```

- [ ] **Step 5: Add frontmatter to `arm_care_program.md`**

Replace existing frontmatter (read file first to get current keywords) with:
```yaml
---
id: arm_care_program
title: Arm Care Programming Reference
keywords: [arm care, shoulder, scapular, external rotation, band, cuff, rotator, prehab, stability, impingement, gird]
type: core_research
applies_to:
  - shoulder
triggers:
  - arm_care
  - shoulder_protection
  - scapular
  - rotator_cuff
phase: any
priority: standard
contexts:
  - plan_gen
  - coach_chat
  - daily_plan_why
summary: >
  Arm care template logic and exercise selection for shoulder health — heavy vs light
  templates, scapular activation, and injury-specific cuff work.
---
```

- [ ] **Step 6: Add frontmatter to `advanced_workload_performance.md`**

```yaml
---
id: advanced_workload_performance
title: Advanced Workload & Performance Management
keywords: [workload, load management, acute chronic, ramp, volume, tonnage, deload, periodization, overtraining, fatigue]
type: core_research
applies_to:
  - lower_back
  - oblique
triggers:
  - workload
  - load_management
  - deload
phase: any
priority: standard
contexts:
  - plan_gen
  - coach_chat
summary: >
  Workload management frameworks — acute:chronic ratios, volume progression,
  and deload triggers for college pitchers managing in-season training loads.
---
```

- [ ] **Step 7: Add frontmatter to `driveline_lifting_programs.md`**

```yaml
---
id: driveline_lifting_programs
title: Driveline Lifting Programs Reference
keywords: [driveline, lifting, strength, power, hypertrophy, squat, deadlift, bench, programming]
type: core_research
applies_to:
  - any
triggers:
  - lifting
  - strength
  - programming
phase: any
priority: reference
contexts:
  - coach_chat
summary: >
  Driveline's approach to in-season and off-season lifting — set/rep schemes,
  exercise selection philosophy, and periodization templates.
---
```

- [ ] **Step 8: Add frontmatter to `driveline_throwing_program.md`**

```yaml
---
id: driveline_throwing_program
title: Driveline Throwing Program Reference
keywords: [driveline, throwing, plyocare, plyo, long toss, pulldown, velo, arm speed, catch play]
type: core_research
applies_to:
  - any
triggers:
  - throwing
  - plyocare
  - long_toss
  - velo
phase: any
priority: reference
contexts:
  - coach_chat
summary: >
  Driveline throwing development protocol — plyocare progression, long toss structure,
  pulldown integration, and in-season maintenance approach.
---
```

- [ ] **Step 9: Add frontmatter to `brice_arm_care_reference.md`**

```yaml
---
id: brice_arm_care_reference
title: Brice Arm Care Reference
keywords: [brice, arm care, personal, cuff, external rotation, scapular, band work]
type: personal_reference
applies_to:
  - shoulder
  - medial_elbow
triggers:
  - arm_care
  - personal_protocol
phase: any
priority: reference
contexts:
  - coach_chat
summary: >
  Personal arm care reference for Landon Brice — specific exercise selections,
  cuff activation preferences, and historical protocol notes.
---
```

- [ ] **Step 10: Add frontmatter to remaining docs**

For each of: `bot_intelligence_architecture.md`, `FINAL_research_base.md`, `Gemeni Researching Lifting.md`, `research_gap_analysis.md`, `supplamentation.md`.

Read each file first, then add appropriate frontmatter following the schema. These are lower-priority docs:

- `bot_intelligence_architecture.md` → `priority: reference`, `contexts: [coach_chat]`, `applies_to: [any]`
- `FINAL_research_base.md` → `priority: reference`, `contexts: [coach_chat]`, `applies_to: [any]`
- `Gemeni Researching Lifting.md` → `priority: reference`, `contexts: [coach_chat]`, `applies_to: [any]`
- `research_gap_analysis.md` → `priority: reference`, `contexts: [coach_chat]`, `applies_to: [any]`
- `supplamentation.md` → `priority: reference`, `contexts: [coach_chat]`, `applies_to: [any]`, `triggers: [supplements, nutrition]`

- [ ] **Step 11: Commit**

```bash
cd pitcher_program_app
git add data/knowledge/research/*.md
git commit -m "feat: add research-aware frontmatter schema to all 14 research docs"
```

---

## Task 3: Research Resolver (`bot/services/research_resolver.py`)

**Files:**
- Create: `pitcher_program_app/bot/services/research_resolver.py`
- Create: `pitcher_program_app/tests/test_research_resolver.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_research_resolver.py
"""Tests for the unified research resolver."""

import pytest


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
    # Profile with no injuries — critical+applies_to:any docs should still load
    profile = {"injury_history": []}
    payload = resolve_research(profile, "plan_gen")
    critical_ids = [d.id for d in payload.loaded_docs if d.priority == "critical"]
    # tightness_triage_framework and recovery_physiology have applies_to: [any] + priority: critical
    assert "tightness_triage_framework" in critical_ids
    assert "recovery_physiology" in critical_ids


def test_resolve_research_context_filter():
    from bot.services.research_resolver import resolve_research
    profile = {"injury_history": []}
    payload = resolve_research(profile, "daily_plan_why")
    # Reference-only docs (contexts: [coach_chat]) should NOT appear in daily_plan_why
    for doc in payload.loaded_docs:
        assert "daily_plan_why" in doc.contexts or doc.priority == "critical"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pitcher_program_app && python -m pytest tests/test_research_resolver.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write the resolver implementation**

```python
# bot/services/research_resolver.py
"""Unified research resolver — single door for all surfaces.

Replaces the split routing logic in knowledge_retrieval.py. All surfaces
(plan_gen, coach_chat, morning, daily_plan_why) call resolve_research()
to get research context for a pitcher.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Literal, Optional

import yaml

from bot.config import KNOWLEDGE_DIR
from bot.services.vocabulary import (
    INJURY_AREAS,
    get_all_trigger_keywords,
    get_research_triggers_for_injury,
    get_research_triggers_for_mod,
)

logger = logging.getLogger(__name__)

RESEARCH_DIR = os.path.join(KNOWLEDGE_DIR, "research")

# All valid contexts a doc can opt into
ALL_CONTEXTS = ["plan_gen", "coach_chat", "morning", "daily_plan_why"]


@dataclass
class DocRef:
    id: str
    title: str
    summary: str
    priority: str
    contexts: list[str] = field(default_factory=list)


@dataclass
class ResearchPayload:
    combined_text: str
    loaded_docs: list[DocRef]
    trigger_reason: str


# Cache: doc_id -> (frontmatter_dict, content_without_frontmatter)
_index_cache: dict[str, tuple[dict, str]] = {}


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a research doc.

    Returns dict with all frontmatter fields, using sensible defaults
    for missing fields (backward compat with old-style keywords-only docs).
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {
            "id": "", "title": "", "keywords": [], "type": "",
            "applies_to": [], "triggers": [], "phase": "any",
            "priority": "standard", "contexts": list(ALL_CONTEXTS),
            "summary": "",
        }

    try:
        parsed = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        parsed = {}

    return {
        "id": parsed.get("id", ""),
        "title": parsed.get("title", ""),
        "keywords": parsed.get("keywords", []),
        "type": parsed.get("type", ""),
        "applies_to": parsed.get("applies_to", []),
        "triggers": parsed.get("triggers", []),
        "phase": parsed.get("phase", "any"),
        "priority": parsed.get("priority", "standard"),
        "contexts": parsed.get("contexts", list(ALL_CONTEXTS)),
        "summary": parsed.get("summary", ""),
    }


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from content."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)


def _load_index() -> dict[str, tuple[dict, str]]:
    """Scan research/ directory and build index from frontmatter.

    Returns dict: doc_id -> (frontmatter_dict, content_without_frontmatter)
    Caches after first call.
    """
    global _index_cache
    if _index_cache:
        return _index_cache

    if not os.path.exists(RESEARCH_DIR):
        logger.warning("Research directory not found: %s", RESEARCH_DIR)
        return {}

    for filename in os.listdir(RESEARCH_DIR):
        if not filename.endswith(".md") or filename == "INDEX.md":
            continue
        filepath = os.path.join(RESEARCH_DIR, filename)
        try:
            with open(filepath, "r") as f:
                content = f.read()
            fm = _parse_frontmatter(content)
            doc_id = fm["id"] or filename.replace(".md", "")
            body = _strip_frontmatter(content)
            _index_cache[doc_id] = (fm, body)

            # Warn on missing new-style frontmatter
            if not fm["id"]:
                logger.warning("Research doc %s missing 'id' in frontmatter", filename)
        except Exception as e:
            logger.warning("Error reading research file %s: %s", filename, e)

    logger.info("Research index: %d docs loaded", len(_index_cache))
    return _index_cache


def clear_cache():
    """Clear the research index cache. Called when new research is generated."""
    global _index_cache
    _index_cache = {}


def should_fire_research(
    pitcher_profile: dict,
    triage_result: dict | None = None,
    user_message: str | None = None,
) -> tuple[bool, str]:
    """Determine whether research-aware behavior should activate.

    Returns (should_fire, reason_string).

    Three OR'd conditions:
    1. Non-green flag_level
    2. Recent modification within rotation_length days
    3. Injury keyword detected in user_message (coach chat only)
    """
    # Condition 1: non-green flag
    if triage_result:
        flag = triage_result.get("flag_level", "green")
        if flag in ("yellow", "red", "modified_green"):
            return True, f"flag_level={flag}"

        # Condition 2: modifications present in current triage
        mods = triage_result.get("modifications", [])
        if mods:
            first_mod = mods[0] if isinstance(mods[0], str) else str(mods[0])
            return True, f"recent_mod:{first_mod}"

    # Condition 2b: check recent modifications from profile
    active_mods = (pitcher_profile.get("active_flags") or {}).get("active_modifications", [])
    if active_mods:
        return True, f"recent_mod:{active_mods[0]}"

    # Condition 3: keyword in free-text (coach chat)
    if user_message:
        msg_lower = user_message.lower()
        trigger_keywords = get_all_trigger_keywords()
        for kw in trigger_keywords:
            if kw in msg_lower:
                return True, f"keyword:{kw}"

    return False, ""


def resolve_research(
    pitcher_profile: dict,
    context: Literal["plan_gen", "coach_chat", "morning", "daily_plan_why"],
    triage_result: dict | None = None,
    user_message: str | None = None,
    max_chars: int = 12000,
) -> ResearchPayload:
    """Single source of truth for research retrieval across all surfaces.

    Doc selection algorithm (deterministic order):
    1. Critical docs whose applies_to intersects pitcher's injury_areas (or 'any')
    2. Docs whose triggers intersect triage modifications
    3. Docs whose triggers match user_message keywords (coach_chat only)
    4. Standard docs that match injury_areas, until max_chars
    """
    index = _load_index()
    loaded: dict[str, tuple[DocRef, str]] = {}  # doc_id -> (DocRef, content)

    # Collect pitcher's injury areas
    injury_areas = set()
    for injury in pitcher_profile.get("injury_history", []):
        area = injury.get("area", "").lower()
        if area:
            injury_areas.add(area)

    # Collect research triggers from injury areas
    injury_triggers = set()
    for area in injury_areas:
        injury_triggers.update(get_research_triggers_for_injury(area))

    # Collect triggers from triage modifications
    mod_triggers = set()
    if triage_result:
        for mod in triage_result.get("modifications", []):
            mod_key = mod if isinstance(mod, str) else str(mod)
            mod_triggers.update(get_research_triggers_for_mod(mod_key))

    # Also check active_modifications from profile
    active_mods = (pitcher_profile.get("active_flags") or {}).get("active_modifications", [])
    for mod in active_mods:
        mod_triggers.update(get_research_triggers_for_mod(mod))

    trigger_reasons = []

    # Step 1: Critical docs for this context where applies_to matches
    for doc_id, (fm, content) in index.items():
        if context not in fm.get("contexts", ALL_CONTEXTS):
            continue
        if fm["priority"] != "critical":
            continue
        applies = fm.get("applies_to", [])
        if "any" in applies or injury_areas.intersection(applies):
            ref = DocRef(
                id=doc_id, title=fm["title"], summary=fm["summary"],
                priority=fm["priority"], contexts=fm.get("contexts", ALL_CONTEXTS),
            )
            loaded[doc_id] = (ref, content)
            trigger_reasons.append(f"critical:{doc_id}")

    # Step 2: Docs whose triggers intersect triage modifications
    all_triggers = injury_triggers | mod_triggers
    if all_triggers:
        for doc_id, (fm, content) in index.items():
            if doc_id in loaded:
                continue
            if context not in fm.get("contexts", ALL_CONTEXTS):
                continue
            doc_triggers = set(fm.get("triggers", []))
            if doc_triggers.intersection(all_triggers):
                ref = DocRef(
                    id=doc_id, title=fm["title"], summary=fm["summary"],
                    priority=fm["priority"], contexts=fm.get("contexts", ALL_CONTEXTS),
                )
                loaded[doc_id] = (ref, content)
                trigger_reasons.append(f"trigger_match:{doc_id}")

    # Step 3: User message keyword match (coach_chat only)
    if user_message and context == "coach_chat":
        msg_lower = user_message.lower()
        for doc_id, (fm, content) in index.items():
            if doc_id in loaded:
                continue
            if context not in fm.get("contexts", ALL_CONTEXTS):
                continue
            doc_triggers = set(fm.get("triggers", []))
            if any(t in msg_lower for t in doc_triggers):
                ref = DocRef(
                    id=doc_id, title=fm["title"], summary=fm["summary"],
                    priority=fm["priority"], contexts=fm.get("contexts", ALL_CONTEXTS),
                )
                loaded[doc_id] = (ref, content)
                trigger_reasons.append(f"keyword_match:{doc_id}")

    # Step 4: Standard docs matching injury_areas (fill remaining budget)
    for doc_id, (fm, content) in index.items():
        if doc_id in loaded:
            continue
        if context not in fm.get("contexts", ALL_CONTEXTS):
            continue
        if fm["priority"] != "standard":
            continue
        applies = fm.get("applies_to", [])
        if injury_areas.intersection(applies):
            ref = DocRef(
                id=doc_id, title=fm["title"], summary=fm["summary"],
                priority=fm["priority"], contexts=fm.get("contexts", ALL_CONTEXTS),
            )
            loaded[doc_id] = (ref, content)
            trigger_reasons.append(f"standard:{doc_id}")

    # Build combined text with budget
    combined_parts = []
    total_chars = 0
    final_docs = []
    for doc_id, (ref, content) in loaded.items():
        if total_chars + len(content) > max_chars:
            # Only add if critical
            if ref.priority == "critical":
                remaining = max_chars - total_chars
                combined_parts.append(content[:remaining])
                final_docs.append(ref)
            break
        combined_parts.append(content)
        total_chars += len(content)
        final_docs.append(ref)

    combined = "\n\n---\n\n".join(combined_parts)
    reason = "; ".join(trigger_reasons) if trigger_reasons else "baseline"

    # Observability: log the load (non-blocking)
    _log_research_load(
        pitcher_profile.get("pitcher_id") or pitcher_profile.get("id", ""),
        context, reason,
        [d.id for d in final_docs],
        len(combined),
    )

    if final_docs:
        logger.info(
            "Research resolved [%s]: %d docs (%s) — %d chars",
            context, len(final_docs),
            ", ".join(d.id for d in final_docs), len(combined),
        )

    return ResearchPayload(
        combined_text=combined,
        loaded_docs=final_docs,
        trigger_reason=reason,
    )


def _log_research_load(
    pitcher_id: str, context: str, trigger_reason: str,
    doc_ids: list[str], total_chars: int, degraded: bool = False,
):
    """Write a row to research_load_log for observability. Non-blocking."""
    if not pitcher_id:
        return
    try:
        from bot.services.db import get_client
        get_client().table("research_load_log").insert({
            "pitcher_id": pitcher_id,
            "context": context,
            "trigger_reason": trigger_reason,
            "loaded_doc_ids": doc_ids,
            "total_chars": total_chars,
            "degraded": degraded,
        }).execute()
    except Exception as e:
        logger.debug("research_load_log insert failed (non-blocking): %s", e)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pitcher_program_app && python -m pytest tests/test_research_resolver.py -v`
Expected: all 8 tests PASS

Note: Some tests that check specific doc IDs (like `test_resolve_research_critical_always_loads`) depend on the frontmatter from Task 2 being applied. If Task 2 is not yet done, those tests will fail — that's expected. Run Task 2 first.

- [ ] **Step 5: Commit**

```bash
cd pitcher_program_app
git add bot/services/research_resolver.py tests/test_research_resolver.py
git commit -m "feat: add unified research resolver with frontmatter-driven routing"
```

---

## Task 4: Supabase Migration — `research_load_log` Table + `research_sources` Column

**Files:**
- No file changes — run via Supabase MCP

- [ ] **Step 1: Create `research_load_log` table**

Run via Supabase MCP:
```sql
CREATE TABLE IF NOT EXISTS research_load_log (
  id bigserial PRIMARY KEY,
  ts timestamptz DEFAULT now(),
  pitcher_id text REFERENCES pitchers(pitcher_id),
  context text NOT NULL,
  trigger_reason text,
  loaded_doc_ids text[],
  total_chars int,
  degraded boolean DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_research_load_log_pitcher ON research_load_log (pitcher_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_research_load_log_context ON research_load_log (context, ts DESC);
```

- [ ] **Step 2: Add `research_sources` column to `daily_entries`**

Run via Supabase MCP:
```sql
ALTER TABLE daily_entries ADD COLUMN IF NOT EXISTS research_sources text[];
```

- [ ] **Step 3: Add `research_sources` to the whitelist in `db.py`**

In `pitcher_program_app/bot/services/db.py`, line 176, add `"research_sources"` to the `_DAILY_ENTRY_COLUMNS` set:

Change:
```python
_DAILY_ENTRY_COLUMNS = {
    "pitcher_id", "date", "rotation_day", "days_since_outing", "pre_training",
    "plan_narrative", "morning_brief", "plan_generated", "actual_logged",
    "bot_observations", "arm_care", "lifting", "throwing", "warmup", "mobility", "notes",
    "completed_exercises", "soreness_response",
}
```

To:
```python
_DAILY_ENTRY_COLUMNS = {
    "pitcher_id", "date", "rotation_day", "days_since_outing", "pre_training",
    "plan_narrative", "morning_brief", "plan_generated", "actual_logged",
    "bot_observations", "arm_care", "lifting", "throwing", "warmup", "mobility", "notes",
    "completed_exercises", "soreness_response", "research_sources",
}
```

- [ ] **Step 4: Commit**

```bash
cd pitcher_program_app
git add bot/services/db.py
git commit -m "feat: add research_sources to daily_entries whitelist"
```

---

## Task 5: Wire Resolver into Knowledge Retrieval (Backward Compat Wrappers)

**Files:**
- Modify: `pitcher_program_app/bot/services/knowledge_retrieval.py`

- [ ] **Step 1: Replace routing logic with resolver wrappers**

At the top of `knowledge_retrieval.py`, add the import (after line 19):
```python
from bot.services.research_resolver import resolve_research, clear_cache as _clear_resolver_cache
```

Replace the `retrieve_research_for_plan` function (lines 136-208) with:
```python
def retrieve_research_for_plan(pitcher_profile: dict, max_chars: int = 12000) -> str:
    """Load research docs relevant to a pitcher's profile for plan generation.

    Thin wrapper around resolve_research() for backward compatibility.
    """
    payload = resolve_research(pitcher_profile, "plan_gen", max_chars=max_chars)
    return payload.combined_text
```

Replace the `retrieve_knowledge` function (lines 98-133) with:
```python
def retrieve_knowledge(question: str, pitcher_profile: dict = None, max_docs: int = 3, max_chars: int = 8000) -> str:
    """Keyword-match a question against research docs + exercise library.

    Used for Q&A. Returns formatted context string for prompt injection.
    """
    # Use resolver for research docs
    profile = pitcher_profile or {}
    payload = resolve_research(profile, "coach_chat", user_message=question, max_chars=max_chars)
    results = [payload.combined_text] if payload.combined_text else []

    # Exercise library search (not in resolver — different data source)
    keywords = _extract_keywords(question)
    exercises = _search_exercises(question, keywords)
    for ex in exercises[:3]:
        results.append(_format_exercise(ex))

    if not results:
        return ""

    combined = "\n\n---\n\n".join(results)
    if len(combined) > max_chars:
        combined = combined[:max_chars]

    return combined
```

In `classify_and_generate_research`, replace the cache clear (line 376):
```python
        _research_cache = {}
```
With:
```python
        _research_cache = {}
        _clear_resolver_cache()
```

- [ ] **Step 2: Verify existing tests still pass (if any)**

Run: `cd pitcher_program_app && python -m pytest tests/ -v -k "knowledge" 2>/dev/null || echo "No existing knowledge tests"`

- [ ] **Step 3: Commit**

```bash
cd pitcher_program_app
git add bot/services/knowledge_retrieval.py
git commit -m "refactor: wire knowledge_retrieval through unified resolver"
```

---

## Task 6: Wire Resolver into Plan Generator

**Files:**
- Modify: `pitcher_program_app/bot/services/plan_generator.py`

- [ ] **Step 1: Update import** (line 9)

Change:
```python
from bot.services.knowledge_retrieval import retrieve_research_for_plan
```
To:
```python
from bot.services.research_resolver import resolve_research
```

- [ ] **Step 2: Update research retrieval call** (line 210)

Change:
```python
    relevant_research = retrieve_research_for_plan(profile)
```
To:
```python
    research_payload = resolve_research(profile, "plan_gen", triage_result)
    relevant_research = research_payload.combined_text
```

- [ ] **Step 3: Persist research_sources on the plan result**

In the `python_plan` dict (around line 266-283), add `research_sources`:

After line 282 (`"source_reason": None,`), add:
```python
        "research_sources": [doc.id for doc in research_payload.loaded_docs],
```

Also in the LLM success path — find where `plan_result` is assembled (around line 370-380) and add:
```python
                "research_sources": [doc.id for doc in research_payload.loaded_docs],
```

- [ ] **Step 4: Enhance `_build_python_brief` with research awareness**

In `_build_python_brief()` (around line 41-61), add after the existing brief construction:

```python
    # This will be called with research_docs parameter in the future
    # For now, the caller appends research context after calling this function
```

Actually, simpler: in `generate_plan()` after the `python_plan` is built (after line 283), add:
```python
    # Enhance Python fallback brief with research context
    if research_payload.loaded_docs:
        top_doc = research_payload.loaded_docs[0]
        python_plan["morning_brief"] += f" Today's plan is informed by the {top_doc.title}."
```

- [ ] **Step 5: Run existing tests**

Run: `cd pitcher_program_app && python -m pytest tests/ -v 2>&1 | tail -20`

- [ ] **Step 6: Commit**

```bash
cd pitcher_program_app
git add bot/services/plan_generator.py
git commit -m "feat: wire plan generator through unified resolver, persist research_sources"
```

---

## Task 7: Triage Vocabulary Migration

**Files:**
- Modify: `pitcher_program_app/bot/services/triage.py`

- [ ] **Step 1: Import vocabulary at top of file** (after line 3)

```python
from bot.services.vocabulary import MODIFICATION_TAGS, get_mod_description
```

- [ ] **Step 2: Replace freeform modification strings with tag keys**

This is a search-and-replace across triage.py. Each `modifications.append("...")` becomes `modifications.append("tag_key")`. The human-readable description lives in `MODIFICATION_TAGS` and is looked up by downstream consumers.

Key replacements:

Line 117:
```python
# Old:
modifications.append("Elevated FPM volume — tightness flagged with elbow history")
# New:
modifications.append("fpm_volume")
```

Line 154:
```python
# Old:
modifications.append("Reduce all loads to RPE 5-6")
# New:
modifications.append("rpe_cap_56")
```

Line 155:
```python
# Old:
modifications.append("No high-intent throwing — recovery plyo + light catch only")
# New:
modifications.append("no_high_intent_throw")
```

Line 173:
```python
# Old:
modifications.append("Reduce loads to RPE 6-7")
# New:
modifications.append("rpe_cap_67")
```

Line 174:
```python
# Old:
modifications.append("Maintain compounds at reduced intensity")
# New:
modifications.append("maintain_compounds_reduced")
```

Line 175:
```python
# Old:
modifications.append("Cap throwing at Hybrid B — no compression throws or pulldowns")
# New:
modifications.append("cap_hybrid_b")
```

Line 215:
```python
# Old:
modifications.append("Modified green — proceed with awareness")
# New:
modifications.append("modified_green")
```

Line 233:
```python
# Old:
modifications.append("Primer session only — start within 48h")
# New:
modifications.append("primer_session")
```

Line 234:
```python
# Old:
modifications.append("Low volume, activation focus")
# New:
modifications.append("low_volume_activation")
```

Line 255:
```python
# Old:
modifications.append("Elevated FPM volume per injury history flag")
# New:
modifications.append("elevated_fpm_history")
```

In `_red_result` (line 277-278):
```python
# Old:
modifications.extend([
    "No lifting today — mobility and recovery only",
    "No throwing — light catch only if arm feels OK",
])
# New:
modifications.extend(["no_lifting", "no_throwing"])
```

**Keep the `Ongoing: {ongoing}` line (261) as-is** — this is dynamic content from injury_history, not a tag.

- [ ] **Step 3: Update downstream consumers that read modification descriptions**

In `plan_generator.py`, the `_build_python_brief` and `_build_python_notes` functions read `triage_result.get("modifications")`. These now receive tag keys instead of description strings. Update them to use `get_mod_description()`:

In `_build_python_notes` (plan_generator.py around line 63-68):
```python
from bot.services.vocabulary import get_mod_description

def _build_python_notes(triage_result, flag_level, checkin_inputs):
    notes = []
    mods = triage_result.get("modifications", [])
    for mod in mods:
        # Convert tag keys to human-readable descriptions
        notes.append(get_mod_description(mod))
    # ... rest stays the same
```

- [ ] **Step 4: Run triage tests**

Run: `cd pitcher_program_app && python -m pytest tests/ -v -k "triage" 2>&1 | tail -20`

If existing triage tests assert on the old freeform strings, update those assertions to use the new tag keys.

- [ ] **Step 5: Commit**

```bash
cd pitcher_program_app
git add bot/services/triage.py bot/services/plan_generator.py
git commit -m "refactor: triage emits vocabulary tag keys instead of freeform modification strings"
```

---

## Task 8: Exercise Pool Vocabulary Migration

**Files:**
- Modify: `pitcher_program_app/bot/services/exercise_pool.py`

- [ ] **Step 1: Replace hardcoded `INJURY_TO_FLAG` with vocabulary import**

At the top of `exercise_pool.py`, replace lines 26-38:

```python
# Old:
# Map injury areas from pitcher profiles to modification_flags keys
INJURY_TO_FLAG = {
    "medial_elbow": "ucl_history",
    "ucl": "ucl_history",
    "forearm": "ucl_history",
    "shoulder": "shoulder_impingement",
    "shoulder_impingement": "shoulder_impingement",
    "low_back": "low_back_history",
    "lumbar": "low_back_history",
    "hip": "poor_hip_mobility",
    "knee": "knee_history",
    "oblique": "oblique_strain",
}
```

With:
```python
from bot.services.vocabulary import INJURY_AREAS

# Build INJURY_TO_FLAG from vocabulary for exercise library compatibility
# The exercise library uses modification_flags keys like "ucl_history", "shoulder_impingement"
# These map from vocabulary injury areas to exercise library flag keys
INJURY_TO_FLAG = {
    "medial_elbow": "ucl_history",
    "ucl": "ucl_history",
    "forearm": "ucl_history",
    "shoulder": "shoulder_impingement",
    "shoulder_impingement": "shoulder_impingement",
    "low_back": "low_back_history",
    "lumbar": "low_back_history",
    "hip": "poor_hip_mobility",
    "knee": "knee_history",
    "oblique": "oblique_strain",
}
# NOTE: INJURY_TO_FLAG stays because exercise library modification_flags use different
# keys than vocabulary.py. The vocabulary unifies research routing; this dict maps
# to exercise library schema. They coexist intentionally.
```

- [ ] **Step 2: Commit**

```bash
cd pitcher_program_app
git add bot/services/exercise_pool.py
git commit -m "refactor: document exercise_pool INJURY_TO_FLAG relationship to vocabulary"
```

Note: This task is intentionally small. The exercise pool's `INJURY_TO_FLAG` maps to exercise library `modification_flags` keys (like `ucl_history`, `shoulder_impingement`) which are different from the vocabulary's `research_triggers`. Both are needed. The key change is that vocabulary.py is now the canonical reference for injury areas — if a new area is added, the developer adds it to vocabulary.py first and then adds the exercise library mapping here.

---

## Task 9: Coverage Tests

**Files:**
- Create: `pitcher_program_app/tests/test_research_coverage.py`

- [ ] **Step 1: Write the coverage tests**

```python
# tests/test_research_coverage.py
"""CI coverage tests — ensure every modification tag and injury area has matching research."""

import pytest


def test_every_modification_tag_has_research():
    """Every MODIFICATION_TAG with non-empty research_triggers must have at least
    one research doc whose triggers match."""
    from bot.services.vocabulary import MODIFICATION_TAGS
    from bot.services.research_resolver import _load_index

    index = _load_index()
    all_doc_triggers = set()
    for doc_id, (fm, _) in index.items():
        all_doc_triggers.update(fm.get("triggers", []))

    for tag, meta in MODIFICATION_TAGS.items():
        for trigger in meta["research_triggers"]:
            if trigger:  # skip empty trigger lists (e.g. modified_green)
                assert trigger in all_doc_triggers, (
                    f"Modification tag '{tag}' expects research trigger '{trigger}' "
                    f"but no research doc declares it in frontmatter. "
                    f"Available doc triggers: {sorted(all_doc_triggers)}"
                )


def test_every_injury_area_has_critical_research():
    """Every INJURY_AREA must have at least one priority:critical research doc
    whose applies_to includes it (or 'any')."""
    from bot.services.vocabulary import INJURY_AREAS
    from bot.services.research_resolver import _load_index

    index = _load_index()

    for area in INJURY_AREAS:
        has_critical = False
        for doc_id, (fm, _) in index.items():
            if fm["priority"] != "critical":
                continue
            applies = fm.get("applies_to", [])
            if area in applies or "any" in applies:
                has_critical = True
                break
        assert has_critical, (
            f"Injury area '{area}' has no priority:critical research doc. "
            f"Add applies_to: [{area}] to a critical doc or create one."
        )


def test_no_orphan_research_docs():
    """Every research doc should have at least one trigger or applies_to entry."""
    from bot.services.research_resolver import _load_index

    index = _load_index()
    for doc_id, (fm, _) in index.items():
        has_routing = (
            fm.get("triggers", []) or
            fm.get("applies_to", [])
        )
        assert has_routing, (
            f"Research doc '{doc_id}' has no triggers and no applies_to — "
            f"it will never be loaded by the resolver."
        )
```

- [ ] **Step 2: Run the coverage tests**

Run: `cd pitcher_program_app && python -m pytest tests/test_research_coverage.py -v`

If any test fails, it means the frontmatter migration (Task 2) is incomplete or a vocabulary entry (Task 1) has a trigger that no research doc declares. Fix the frontmatter or add the trigger to the appropriate doc.

- [ ] **Step 3: Commit**

```bash
cd pitcher_program_app
git add tests/test_research_coverage.py
git commit -m "test: add CI coverage tests for research↔vocabulary mapping"
```

---

## Task 10: Coach Chat Prompt Template

**Files:**
- Create: `pitcher_program_app/bot/prompts/coach_chat_prompt.md`

- [ ] **Step 1: Write the prompt template**

```markdown
# Coach Chat Prompt (Research-Aware)

You are a pitching intelligence coach for UChicago baseball. You combine deep sports science knowledge with empathetic, conversational coaching. You are NOT a doctor — flag medical concerns to the trainer.

## Your Pitcher Right Now

{pitcher_context}

## Current Triage State

{triage_state}

## Research Context (Loaded Protocols)

The following research documents are loaded for this pitcher's current state. Reference them by name when they inform your advice. Do NOT cite docs not in this list.

{research_context}

## Recent History

{recent_history}

## Pitcher's Message

{user_message}

## Instructions

Respond with a JSON object. No markdown fences, no preamble, ONLY the JSON:

{
  "reply": "Your conversational, empathetic response. Lead with acknowledgment of how they feel. Reference loaded research by protocol name when relevant (e.g. 'per the FPM protocol'). Be warm but direct.",
  "mutation_card": {
    "type": "swap | rest | hold | addition",
    "title": "Short action title (e.g. 'Swap pressing for pulling' or 'Rest today')",
    "rationale": "One sentence explaining why, referencing the specific protocol that drives this decision.",
    "actions": [
      {"action": "swap", "from_exercise_id": "ex_XXX", "to_exercise_id": "ex_YYY", "rx": "3x10"},
      {"action": "remove", "exercise_id": "ex_XXX"},
      {"action": "add", "exercise_id": "ex_XXX", "rx": "3x10"}
    ],
    "applies_to_date": "today"
  },
  "lookahead": "One sentence about the next 2-3 days — reference upcoming outings, rotation position, or recovery trajectory."
}

Rules for mutation_card:
- ALWAYS include a mutation_card, even when the answer is rest.
- For rest/recovery: use type "rest" or "hold", empty actions array, rationale explains why rest is the right call.
- For active changes: use type "swap", "addition", or combine actions. Use real exercise IDs from the loaded plan.
- applies_to_date is "today" unless the change applies to tomorrow's plan.
- The rationale MUST reference one of the loaded research documents by name.

Rules for reply:
- Lead with empathy — acknowledge the feeling or concern first.
- Be conversational, not clinical. This is a teammate, not a patient.
- Keep it under 3 sentences unless the topic needs more.
- If the pitcher mentions something that sounds medical (numbness, sharp pain, swelling), flag it: "That's worth mentioning to the trainer."

Rules for lookahead:
- Always include a lookahead. Think 2-3 days ahead.
- Reference the next outing if known, or the pitcher's rotation position.
- Connect today's decision to the long arc: "You've got a start in 4 days — let's keep this quiet."
```

- [ ] **Step 2: Commit**

```bash
cd pitcher_program_app
git add bot/prompts/coach_chat_prompt.md
git commit -m "feat: add research-aware coach chat prompt template"
```

---

## Task 11: Coach Chat Integration — Telegram Q&A Handler

**Files:**
- Modify: `pitcher_program_app/bot/handlers/qa.py`
- Create: `pitcher_program_app/tests/test_coach_chat.py`

- [ ] **Step 1: Write tests for structured output parsing**

```python
# tests/test_coach_chat.py
"""Tests for research-aware coach chat structured output."""

import json
import pytest


def test_parse_coach_response_valid():
    from bot.handlers.qa import _parse_coach_response
    raw = json.dumps({
        "reply": "Hey, I hear you on the elbow.",
        "mutation_card": {
            "type": "rest",
            "title": "Rest today",
            "rationale": "Per the FPM protocol.",
            "actions": [],
            "applies_to_date": "today",
        },
        "lookahead": "Start in 3 days.",
    })
    result = _parse_coach_response(raw)
    assert result is not None
    assert result["reply"] == "Hey, I hear you on the elbow."
    assert result["mutation_card"]["type"] == "rest"
    assert result["lookahead"] == "Start in 3 days."


def test_parse_coach_response_malformed():
    from bot.handlers.qa import _parse_coach_response
    result = _parse_coach_response("This is just plain text, no JSON.")
    assert result is None


def test_parse_coach_response_partial_json():
    from bot.handlers.qa import _parse_coach_response
    raw = '{"reply": "Hey", "mutation_card": {"type": "rest"'  # truncated
    result = _parse_coach_response(raw)
    assert result is None


def test_extract_reply_from_malformed():
    from bot.handlers.qa import _extract_reply_fallback
    raw = '{"reply": "Some text here", "mutation_card": broken'
    result = _extract_reply_fallback(raw)
    assert "Some text here" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pitcher_program_app && python -m pytest tests/test_coach_chat.py -v`
Expected: FAIL with "cannot import name '_parse_coach_response'"

- [ ] **Step 3: Update `qa.py` with research-aware flow**

Add the following functions at the bottom of `qa.py` (before the `_build_qa_context` function):

```python
def _parse_coach_response(raw: str) -> dict | None:
    """Parse structured JSON from the LLM's coach chat response.

    Returns dict with reply, mutation_card, lookahead or None if malformed.
    """
    try:
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)

        parsed = json.loads(cleaned)
        if "reply" in parsed:
            return parsed
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_reply_fallback(raw: str) -> str:
    """Best-effort extraction of the reply field from malformed JSON."""
    match = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
    if match:
        return match.group(1).replace('\\"', '"').replace('\\n', '\n')
    return raw[:500]  # last resort: return raw text truncated
```

Add the import at the top of `qa.py` (line 4):
```python
import json
```

Now update the `handle_question` function. Replace lines 62-128 with the research-aware flow:

```python
    try:
        profile = load_profile(pitcher_id)
        pitcher_context = _build_qa_context(profile, pitcher_id)

        # Check for research-aware trigger
        from bot.services.research_resolver import should_fire_research, resolve_research
        from bot.services.context_manager import get_recent_entries as _get_recent

        # Get recent triage from today's entry if available
        recent = _get_recent(pitcher_id, n=1)
        recent_triage = None
        if recent:
            last = recent[0]
            pre = last.get("pre_training") or {}
            if pre.get("flag_level"):
                recent_triage = {
                    "flag_level": pre["flag_level"],
                    "modifications": (last.get("plan_generated") or {}).get("modifications_applied", []),
                }

        should_fire, fire_reason = should_fire_research(profile, recent_triage, question)

        if should_fire:
            # Research-aware path: structured output with mutation card
            payload = resolve_research(profile, "coach_chat", recent_triage, question)

            coach_prompt = load_prompt("coach_chat_prompt.md")

            # Build triage state block
            if recent_triage:
                triage_state = f"Flag: {recent_triage['flag_level']}\nModifications: {', '.join(recent_triage.get('modifications', []))}"
            else:
                flags = profile.get("active_flags", {})
                triage_state = f"Flag: {flags.get('current_flag_level', 'unknown')}\nArm feel: {flags.get('current_arm_feel', 'N/A')}/5"

            user_prompt = coach_prompt.replace("{pitcher_context}", pitcher_context)
            user_prompt = user_prompt.replace("{triage_state}", triage_state)
            user_prompt = user_prompt.replace("{research_context}", payload.combined_text or "No specific research loaded.")
            user_prompt = user_prompt.replace("{recent_history}", "")
            user_prompt = user_prompt.replace("{user_message}", question)

            system_prompt = load_prompt("system_prompt.md")
            history = context.user_data.get("conversation_history", [])

            q_lower = question.lower()
            needs_reasoning = any(kw in q_lower for kw in _REASONING_KEYWORDS)
            if needs_reasoning:
                response = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, history=history)
            else:
                response = await call_llm(system_prompt, user_prompt, history=history)

            # Parse structured response
            parsed = _parse_coach_response(response)
            if parsed:
                reply_text = parsed["reply"]
                if parsed.get("lookahead"):
                    reply_text += f"\n\n{parsed['lookahead']}"
                await update.message.reply_text(reply_text)
                # Mutation card is only visible in mini-app — Telegram gets text-only
            else:
                # Fallback: try to extract reply, send as plain text
                fallback = _extract_reply_fallback(response)
                await update.message.reply_text(fallback)
                from bot.services.research_resolver import _log_research_load
                _log_research_load(pitcher_id, "coach_chat", fire_reason, [], 0, degraded=True)

        else:
            # Standard Q&A path (no trigger fired)
            system_prompt = load_prompt("system_prompt.md")
            qa_prompt = load_prompt("qa_prompt.md")
            knowledge = retrieve_knowledge(question, pitcher_profile=profile)

            if not knowledge:
                from bot.services.knowledge_retrieval import classify_and_generate_research
                generated = await classify_and_generate_research(question)
                if generated:
                    knowledge = generated

            if not knowledge:
                knowledge = web_search_fallback(question, pitcher_id)

            user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
            user_prompt = user_prompt.replace("{question}", question)
            user_prompt = user_prompt.replace("{knowledge_context}", knowledge)

            history = context.user_data.get("conversation_history", [])

            q_lower = question.lower()
            needs_reasoning = any(kw in q_lower for kw in _REASONING_KEYWORDS)
            if needs_reasoning:
                response = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, history=history)
            else:
                response = await call_llm(system_prompt, user_prompt, history=history)

            await update.message.reply_text(response)

        # Record in history
        history = context.user_data.get("conversation_history", [])
        history.append({"role": "user", "content": question})
        reply_for_history = parsed["reply"] if should_fire and parsed else response
        history.append({"role": "assistant", "content": reply_for_history})
        context.user_data["conversation_history"] = history[-6:]

        append_context(pitcher_id, "interaction", f"Q: {question[:80]} | A: {reply_for_history[:200]}")

        try:
            from bot.services.health_monitor import record_qa_success
            record_qa_success(pitcher_id)
        except Exception:
            pass
```

- [ ] **Step 4: Run tests**

Run: `cd pitcher_program_app && python -m pytest tests/test_coach_chat.py -v`
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd pitcher_program_app
git add bot/handlers/qa.py tests/test_coach_chat.py
git commit -m "feat: research-aware coach chat with structured output in Telegram handler"
```

---

## Task 12: Coach Chat Integration — API `/chat` Endpoint

**Files:**
- Modify: `pitcher_program_app/api/routes.py`

- [ ] **Step 1: Update the free-text Q&A branch in `post_chat`**

In `api/routes.py`, the free-text Q&A branch starts at line 728. Replace lines 728-850 (the entire `else:` branch for free-text) with:

```python
        else:
            # Free-text Q&A — research-aware path
            question = msg if isinstance(msg, str) else str(msg)
            if not question.strip():
                return {"messages": [{"type": "text", "content": "What's on your mind?"}]}

            profile = load_profile(pitcher_id)

            from bot.handlers.qa import _build_qa_context, _parse_coach_response, _extract_reply_fallback, _REASONING_KEYWORDS
            from bot.services.research_resolver import should_fire_research, resolve_research
            pitcher_context = _build_qa_context(profile, pitcher_id)

            # Get recent triage
            recent = get_recent_entries(pitcher_id, n=1)
            recent_triage = None
            if recent:
                last = recent[0]
                pre = last.get("pre_training") or {}
                if pre.get("flag_level"):
                    recent_triage = {
                        "flag_level": pre["flag_level"],
                        "modifications": (last.get("plan_generated") or {}).get("modifications_applied", []),
                    }

            should_fire, fire_reason = should_fire_research(profile, recent_triage, question)

            # Include plan context if viewing a specific plan
            plan_context = body.get("plan_context")
            if plan_context:
                plan_data = plan_context.get("plan_data", {})
                pc_exercises = plan_data.get("lifting", {}).get("exercises", [])
                if pc_exercises:
                    exercise_list = ", ".join(f"{ex['name']} {ex.get('rx','')}" for ex in pc_exercises)
                    pitcher_context += f"\n\nViewing plan:\nTitle: {plan_data.get('title', '')}\nExercises: {exercise_list}"

            history = body.get("history", [])

            if should_fire:
                # Research-aware path
                payload = resolve_research(profile, "coach_chat", recent_triage, question)
                coach_prompt = load_prompt("coach_chat_prompt.md")

                if recent_triage:
                    triage_state = f"Flag: {recent_triage['flag_level']}\nModifications: {', '.join(recent_triage.get('modifications', []))}"
                else:
                    flags = profile.get("active_flags", {})
                    triage_state = f"Flag: {flags.get('current_flag_level', 'unknown')}\nArm feel: {flags.get('current_arm_feel', 'N/A')}/5"

                user_prompt = coach_prompt.replace("{pitcher_context}", pitcher_context)
                user_prompt = user_prompt.replace("{triage_state}", triage_state)
                user_prompt = user_prompt.replace("{research_context}", payload.combined_text or "No specific research loaded.")
                user_prompt = user_prompt.replace("{recent_history}", "")
                user_prompt = user_prompt.replace("{user_message}", question)
                system_prompt = load_prompt("system_prompt.md")

                q_lower = question.lower()
                if any(kw in q_lower for kw in _REASONING_KEYWORDS):
                    answer = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, history=history)
                else:
                    answer = await call_llm(system_prompt, user_prompt, history=history)

                messages = []
                parsed = _parse_coach_response(answer)
                if parsed:
                    messages.append({"type": "text", "content": parsed["reply"]})
                    if parsed.get("lookahead"):
                        messages.append({"type": "text", "content": parsed["lookahead"]})
                    if parsed.get("mutation_card"):
                        card = parsed["mutation_card"]
                        if card.get("actions"):
                            messages.append({
                                "type": "plan_mutation",
                                "content": card.get("title", "Suggested change"),
                                "mutations": card["actions"],
                                "rationale": card.get("rationale", ""),
                            })
                        else:
                            # Rest/hold card — render as text with rationale
                            messages.append({
                                "type": "text",
                                "content": f"**{card.get('title', 'Rest')}** — {card.get('rationale', '')}",
                            })
                else:
                    fallback = _extract_reply_fallback(answer)
                    messages.append({"type": "text", "content": fallback})

                _persist_chat(pitcher_id, f"Q: {question[:60]}", messages)
                return {"messages": messages}

            else:
                # Standard Q&A path
                system_prompt = load_prompt("system_prompt.md")
                qa_prompt = load_prompt("qa_prompt.md")
                knowledge = retrieve_knowledge(question, pitcher_profile=profile)

                user_prompt = qa_prompt.replace("{pitcher_context}", pitcher_context)
                user_prompt = user_prompt.replace("{question}", question)
                user_prompt = user_prompt.replace("{knowledge_context}", knowledge)

                q_lower = question.lower()
                if any(kw in q_lower for kw in _REASONING_KEYWORDS):
                    answer = await call_llm_reasoning(system_prompt, user_prompt, max_tokens=4000, history=history)
                else:
                    answer = await call_llm(system_prompt, user_prompt, history=history)

                messages = []
                clean_answer = answer
                plan_data_extracted = _extract_json_block(answer, "save_plan")
                mod_data = _extract_json_block(answer, "program_modification")
                mutation_data = _extract_json_block(answer, "plan_mutation")

                if mutation_data and mutation_data.get("mutations"):
                    clean_answer = _strip_json_block(answer, "plan_mutation")
                    messages.append({"type": "text", "content": clean_answer.strip()})
                    messages.append({
                        "type": "plan_mutation",
                        "content": "Coach suggests changes to your plan",
                        "mutations": mutation_data["mutations"],
                    })
                elif plan_data_extracted:
                    clean_answer = _strip_json_block(answer, "save_plan")
                    messages.append({"type": "text", "content": clean_answer.strip()})
                    messages.append({
                        "type": "save_plan",
                        "content": plan_data_extracted.get("title", "Suggested plan"),
                        "plan": plan_data_extracted,
                    })
                elif mod_data:
                    clean_answer = _strip_json_block(answer, "program_modification")
                    messages.append({"type": "text", "content": clean_answer.strip()})
                else:
                    messages.append({"type": "text", "content": answer})

                _persist_chat(pitcher_id, f"Q: {question[:60]}", messages)
                return {"messages": messages}
```

- [ ] **Step 2: Add the research docs metadata endpoint**

After the existing routes, add:

```python
@router.get("/research/docs")
async def get_research_docs(ids: str = Query(...)):
    """Return metadata for research docs by ID list.

    Used by the daily plan 'why' bottom sheet to show doc titles and summaries.
    """
    from bot.services.research_resolver import _load_index
    doc_ids = [d.strip() for d in ids.split(",") if d.strip()]
    index = _load_index()
    result = []
    for doc_id in doc_ids:
        if doc_id in index:
            fm, _ = index[doc_id]
            result.append({
                "id": doc_id,
                "title": fm.get("title", doc_id),
                "summary": fm.get("summary", ""),
            })
    return result
```

- [ ] **Step 3: Commit**

```bash
cd pitcher_program_app
git add api/routes.py
git commit -m "feat: research-aware coach chat in API + research docs metadata endpoint"
```

---

## Task 13: Morning Notification — Two-Pass LLM Enrichment

**Files:**
- Create: `pitcher_program_app/bot/prompts/morning_message.md`
- Modify: `pitcher_program_app/bot/main.py`

- [ ] **Step 1: Write the morning message prompt template**

```markdown
# Morning Message Prompt

You are a pitching intelligence coach writing a morning check-in message to a college pitcher. Keep it warm, conversational, and brief (2-4 sentences).

## Pitcher Context

Name: {first_name}
Role: {role}
Days since outing: {days_since_outing}
Rotation length: {rotation_length}

## Yesterday

{yesterday_context}

## Biometrics (WHOOP)

{whoop_context}

## Proactive Suggestion

{suggestion_context}

## Research Context

{research_context}

## Draft Message (rewrite this naturally)

{draft_message}

## Instructions

Rewrite the draft as natural conversational prose. Lead with the most important thing — if research is loaded, weave it into the message naturally (e.g. "per the FPM protocol, we're keeping pressing off the menu today"). Do NOT reference docs not in the RESEARCH CONTEXT section above. End with the arm check-in prompt.

Return ONLY the message text. No JSON, no markdown fences. Keep it to 2-4 sentences plus the arm question.
```

- [ ] **Step 2: Update `_send_morning_checkin` in `bot/main.py`**

Replace the `_send_morning_checkin` function (lines 446-529) with:

```python
async def _send_morning_checkin(context) -> None:
    """Send a contextual morning check-in — research-aware with LLM enrichment."""
    pitcher_id = context.job.data["pitcher_id"]
    chat_id = context.job.data["chat_id"]

    from bot.utils import build_rating_keyboard
    from bot.services.context_manager import load_profile, load_log
    reply_markup = build_rating_keyboard("arm_feel")

    try:
        profile = load_profile(pitcher_id)
        first_name = profile.get("name", "").split()[0] or "Hey"
        flags = profile.get("active_flags", {})
        days = flags.get("days_since_outing", 0)
        rotation_len = profile.get("rotation_length", 7)

        # Yesterday's data
        log = load_log(pitcher_id)
        entries = log.get("entries", [])
        yesterday = (datetime.now(CHICAGO_TZ).date() - timedelta(days=1)).isoformat()
        yesterday_entry = next((e for e in entries if e.get("date") == yesterday), None)

        # ── Pass 1: Build deterministic draft (always exists) ──
        lines = []

        if days <= 1:
            pitches = flags.get("last_outing_pitches")
            if pitches:
                lines.append(f"{first_name} — day after, {pitches} pitches yesterday. Recovery day.")
            else:
                lines.append(f"{first_name} — day after your outing. Recovery focus.")
        elif days == 2:
            lines.append(f"{first_name} — day 2 post-outing. Body should be bouncing back.")
        elif days >= rotation_len - 1:
            lines.append(f"{first_name} — start day approaching. Keeping it light.")
        elif yesterday_entry and (yesterday_entry.get("pre_training") or {}).get("arm_feel"):
            yest_feel = yesterday_entry["pre_training"]["arm_feel"]
            if yest_feel >= 4:
                lines.append(f"{first_name} — arm felt good yesterday ({yest_feel}/5). Let's keep it rolling.")
            elif yest_feel == 3:
                lines.append(f"{first_name} — arm was a 3 yesterday. Let's see where you're at today.")
            else:
                lines.append(f"{first_name} — arm was at {yest_feel} yesterday. Checking in on that.")
        else:
            lines.append(f"{first_name} — day {days}, let's get your plan set.")

        # WHOOP context
        whoop_context = ""
        try:
            from bot.services.whoop import pull_whoop_data, is_linked
            wd = pull_whoop_data(pitcher_id) if is_linked(pitcher_id) else None
            if wd and wd.get("recovery_score") is not None:
                rec = wd["recovery_score"]
                if rec >= 67:
                    lines.append(f"WHOOP has you at {rec}% recovery — green light.")
                    whoop_context = f"WHOOP recovery: {rec}% (green)"
                elif rec >= 34:
                    lines.append(f"WHOOP recovery at {rec}% — I'll factor that into your plan.")
                    whoop_context = f"WHOOP recovery: {rec}% (moderate)"
                else:
                    lines.append(f"WHOOP recovery low at {rec}% — dialing things back today.")
                    whoop_context = f"WHOOP recovery: {rec}% (low)"
            elif wd and wd.get("yesterday_strain") is not None:
                lines.append(f"Yesterday's strain: {wd['yesterday_strain']:.1f}")
                whoop_context = f"Yesterday strain: {wd['yesterday_strain']:.1f}"
        except Exception:
            pass

        # Next-day suggestion
        suggestion_context = ""
        try:
            from bot.services.db import get_training_model
            model = get_training_model(pitcher_id)
            suggestion = (model.get("current_week_state") or {}).get("next_day_suggestion") or {}
            confidence = suggestion.get("confidence", "low")
            reasoning = suggestion.get("reasoning", "")
            if confidence == "high" and reasoning:
                lines.append(f"{reasoning}.")
                suggestion_context = reasoning
            elif confidence == "medium" and reasoning:
                lines.append(f"Thinking {reasoning.lower()}.")
                suggestion_context = reasoning
        except Exception:
            pass

        lines.append("")
        lines.append("How's the arm? (1-5)")
        draft_msg = "\n".join(lines)

        # ── Research check: should we enrich with LLM? ──
        from bot.services.research_resolver import should_fire_research, resolve_research

        # Build a pseudo-triage from yesterday's entry
        recent_triage = None
        if yesterday_entry:
            pre = yesterday_entry.get("pre_training") or {}
            if pre.get("flag_level"):
                recent_triage = {
                    "flag_level": pre["flag_level"],
                    "modifications": (yesterday_entry.get("plan_generated") or {}).get("modifications_applied", []),
                }

        should_fire, fire_reason = should_fire_research(profile, recent_triage)

        if should_fire:
            # ── Pass 2: LLM enrichment (15s deadline) ──
            try:
                payload = resolve_research(profile, "morning", recent_triage)
                research_context = payload.combined_text or "No specific research loaded."

                from bot.services.llm import call_llm, load_prompt
                morning_prompt = load_prompt("morning_message.md")

                role = profile.get("role", "starter")
                yesterday_ctx = ""
                if yesterday_entry:
                    pre = yesterday_entry.get("pre_training") or {}
                    yesterday_ctx = f"Arm feel: {pre.get('arm_feel', 'N/A')}/5, Flag: {pre.get('flag_level', 'green')}"

                prompt = morning_prompt.replace("{first_name}", first_name)
                prompt = prompt.replace("{role}", role)
                prompt = prompt.replace("{days_since_outing}", str(days))
                prompt = prompt.replace("{rotation_length}", str(rotation_len))
                prompt = prompt.replace("{yesterday_context}", yesterday_ctx)
                prompt = prompt.replace("{whoop_context}", whoop_context or "No WHOOP data")
                prompt = prompt.replace("{suggestion_context}", suggestion_context or "No suggestion")
                prompt = prompt.replace("{research_context}", research_context)
                prompt = prompt.replace("{draft_message}", draft_msg)

                llm_msg = await call_llm(
                    "You write concise morning check-in messages for college pitchers.",
                    prompt, timeout=15,
                )

                if llm_msg and len(llm_msg.strip()) > 10:
                    # LLM succeeded — use its prose, ensure arm question is at the end
                    if "1-5" not in llm_msg and "arm" not in llm_msg.lower():
                        llm_msg += "\n\nHow's the arm? (1-5)"
                    msg = llm_msg.strip()
                else:
                    msg = draft_msg
            except Exception as e:
                logger.warning("Morning LLM enrichment failed for %s: %s", pitcher_id, e)
                msg = draft_msg
        else:
            msg = draft_msg

    except Exception:
        msg = "Morning — how's the arm? (1-5)"

    await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup)
```

- [ ] **Step 3: Commit**

```bash
cd pitcher_program_app
git add bot/prompts/morning_message.md bot/main.py
git commit -m "feat: two-pass morning notification with research-aware LLM enrichment"
```

---

## Task 14: Daily Plan "Why" Affordance — Frontend

**Files:**
- Modify: `pitcher_program_app/mini-app/src/components/DailyCard.jsx`

- [ ] **Step 1: Read current DailyCard to understand the structure**

Read `mini-app/src/components/DailyCard.jsx` to find where the lifting block header is rendered.

- [ ] **Step 2: Add the ResearchWhySheet component**

Create a new component inline within `DailyCard.jsx` (or as a separate file if DailyCard is already large). The component:

```jsx
// Add at the top of DailyCard.jsx or in a separate file
import { useState, useEffect } from 'react';

function ResearchWhySheet({ researchSources, onClose }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const apiUrl = import.meta.env.VITE_API_URL;

  useEffect(() => {
    if (!researchSources?.length) {
      setLoading(false);
      return;
    }
    fetch(`${apiUrl}/api/research/docs?ids=${researchSources.join(',')}`)
      .then(r => r.json())
      .then(data => { setDocs(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [researchSources, apiUrl]);

  if (loading) return <div className="p-4 text-center text-gray-400">Loading...</div>;
  if (!docs.length) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40"
         onClick={onClose}>
      <div className="w-full max-w-lg rounded-t-2xl bg-white p-5 pb-8"
           onClick={e => e.stopPropagation()}>
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-gray-300" />
        <h3 className="mb-3 text-lg font-semibold text-gray-900">
          Why today looks different
        </h3>
        <p className="mb-4 text-sm text-gray-500">Your plan is informed by:</p>
        <div className="space-y-3">
          {docs.map(doc => (
            <div key={doc.id} className="rounded-lg border border-gray-200 p-3">
              <p className="font-medium text-gray-800">{doc.title}</p>
              <p className="mt-1 text-sm text-gray-500">{doc.summary}</p>
            </div>
          ))}
        </div>
        <button
          onClick={onClose}
          className="mt-4 w-full rounded-lg bg-maroon-600 py-2.5 text-sm font-medium text-white"
          style={{ backgroundColor: '#800000' }}
        >
          Got it
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add the info icon trigger to the lifting block header**

Find where the lifting block header is rendered in DailyCard. Add an info icon button that opens the ResearchWhySheet:

```jsx
// Inside the lifting block header area, add:
const [showWhySheet, setShowWhySheet] = useState(false);
const researchSources = entry?.plan_generated?.research_sources || entry?.research_sources || [];

// In the JSX, next to the lifting block header:
{researchSources.length > 0 && (
  <button
    onClick={() => setShowWhySheet(true)}
    className="ml-2 inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 hover:bg-gray-200"
    title="Why today looks different"
  >
    ⓘ why
  </button>
)}

{/* Bottom sheet */}
{showWhySheet && (
  <ResearchWhySheet
    researchSources={researchSources}
    onClose={() => setShowWhySheet(false)}
  />
)}
```

- [ ] **Step 4: Test locally**

Run: `cd pitcher_program_app/mini-app && npm run dev`

Navigate to a daily plan page. If the entry has `research_sources`, the "why" button should appear. Clicking it should open the bottom sheet with doc titles and summaries.

- [ ] **Step 5: Commit**

```bash
cd pitcher_program_app
git add mini-app/src/components/DailyCard.jsx
git commit -m "feat: daily plan 'why today looks different' bottom sheet"
```

---

## Task 15: Dead File Audit & Relocation

**Files:**
- Move/archive files in `data/knowledge/` and repo root `research/`

- [ ] **Step 1: Read and assess each dead file**

Read:
- `pitcher_program_app/data/knowledge/extended_knowledge.md` (first 30 lines)
- `pitcher_program_app/data/knowledge/FINAL_research_base.md` (first 30 lines)
- `research/00_INDEX.md` (full)
- Sample 2-3 of the repo-root research files to assess overlap with `data/knowledge/research/`

For each file, decide: **adopt** (move to `data/knowledge/research/` + add frontmatter), **archive** (move to `data/knowledge/_archive/`), or **delete** (if duplicate).

- [ ] **Step 2: Create archive directory**

```bash
mkdir -p pitcher_program_app/data/knowledge/_archive
```

- [ ] **Step 3: Execute relocations**

Based on the assessment:
- If `FINAL_research_base.md` at top level is a duplicate of the one in `research/` → move to `_archive/`
- If `extended_knowledge.md` has unique content → move to `research/`, add frontmatter
- For repo-root `research/` files that are strategic (not runtime) → move to `_archive/` with a README explaining they're reference-only

```bash
# Example (adjust based on assessment):
mv pitcher_program_app/data/knowledge/FINAL_research_base.md pitcher_program_app/data/knowledge/_archive/
mv pitcher_program_app/data/knowledge/extended_knowledge.md pitcher_program_app/data/knowledge/research/
# Add frontmatter to extended_knowledge.md after moving
```

- [ ] **Step 4: If any repo-root research files are adopted, add frontmatter**

Follow the same schema as Task 2 for any files moved into `data/knowledge/research/`.

- [ ] **Step 5: Re-run coverage tests**

Run: `cd pitcher_program_app && python -m pytest tests/test_research_coverage.py -v`

Verify all tests still pass with the new file layout.

- [ ] **Step 6: Commit**

```bash
cd pitcher_program_app
git add data/knowledge/
git commit -m "chore: dead file audit — relocate orphan research docs, archive duplicates"
```

---

## Task 16: Add `pyyaml` Dependency

**Files:**
- Modify: `pitcher_program_app/requirements.txt`

- [ ] **Step 1: Add pyyaml to requirements**

The resolver uses `yaml.safe_load()` for frontmatter parsing. Check if pyyaml is already in requirements:

```bash
cd pitcher_program_app && grep -i yaml requirements.txt
```

If not present, add:
```
PyYAML>=6.0
```

- [ ] **Step 2: Commit**

```bash
cd pitcher_program_app
git add requirements.txt
git commit -m "chore: add pyyaml dependency for research frontmatter parsing"
```

---

## Task 17: Integration Smoke Test

**Files:**
- No new files — manual verification

- [ ] **Step 1: Run all tests**

```bash
cd pitcher_program_app && python -m pytest tests/ -v
```

All tests should pass: vocabulary, resolver, coverage, coach chat parsing.

- [ ] **Step 2: Verify resolver loads docs correctly**

```bash
cd pitcher_program_app && python -c "
from bot.services.research_resolver import resolve_research, should_fire_research

# Test with Benner's profile (UCL history)
profile = {
    'pitcher_id': 'pitcher_benner_001',
    'injury_history': [{'area': 'medial_elbow', 'flag_level': 'yellow'}],
    'active_flags': {'current_flag_level': 'green', 'active_modifications': []},
}
triage = {'flag_level': 'yellow', 'modifications': ['fpm_volume']}

fire, reason = should_fire_research(profile, triage)
print(f'Should fire: {fire} ({reason})')

payload = resolve_research(profile, 'plan_gen', triage)
print(f'Loaded {len(payload.loaded_docs)} docs:')
for doc in payload.loaded_docs:
    print(f'  [{doc.priority}] {doc.id}: {doc.title}')
print(f'Total chars: {len(payload.combined_text)}')
"
```

Expected: should fire, loads critical docs (tightness_triage_framework, recovery_physiology, ucl_flexor_pronator_protection, fpm_strain_protocol) plus any standard docs matching medial_elbow.

- [ ] **Step 3: Verify vocabulary → triage → resolver chain**

```bash
cd pitcher_program_app && python -c "
from bot.services.vocabulary import MODIFICATION_TAGS, get_research_triggers_for_mod

# Verify that triage tag keys have research triggers
for tag in ['fpm_volume', 'rpe_cap_67', 'no_high_intent_throw']:
    triggers = get_research_triggers_for_mod(tag)
    print(f'{tag}: triggers={triggers}')
"
```

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
cd pitcher_program_app
git add -A
git commit -m "fix: integration test fixes for research-aware coaching"
```

---

## Execution Order & Dependencies

```
Task 1 (vocabulary)
  ↓
Task 2 (frontmatter migration) ← needs vocabulary for trigger names
  ↓
Task 16 (pyyaml dependency) ← needed before resolver runs
  ↓
Task 3 (resolver) ← needs frontmatter + vocabulary
  ↓
Task 4 (Supabase migration) ← needed before resolver can log
  ↓
Task 5 (knowledge_retrieval wrappers) ← needs resolver
  ↓
Task 7 (triage vocabulary) ← needs vocabulary
  ↓
Task 8 (exercise_pool vocabulary) ← needs vocabulary
  ↓
Task 6 (plan_generator wiring) ← needs resolver + triage vocab
  ↓
Task 9 (coverage tests) ← needs everything above
  ↓
Task 10 (coach chat prompt) ← independent, but before 11/12
  ↓
Task 11 (Telegram Q&A handler) ← needs resolver + prompt
Task 12 (API /chat endpoint) ← needs resolver + prompt (parallel with 11)
  ↓
Task 13 (morning notification) ← needs resolver + prompt
  ↓
Task 14 (daily plan why UI) ← needs API endpoint from 12
  ↓
Task 15 (dead file audit) ← can run anytime after Task 2
  ↓
Task 17 (integration smoke test) ← last
```

Tasks 11 and 12 can run in parallel. Task 15 can run anytime after Task 2.
