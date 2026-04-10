# tests/test_research_coverage.py
"""CI coverage tests — ensure every modification tag and injury area has matching research."""

import pytest
from bot.services.research_resolver import clear_cache


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_cache()
    yield
    clear_cache()


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
            if trigger:
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
