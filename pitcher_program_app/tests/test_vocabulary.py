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
        # Tags with empty research_triggers are valid (e.g. modified_green, expected_soreness_override)
        if meta["research_triggers"]:
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
