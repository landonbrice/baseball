import yaml
from pathlib import Path
from bot.services.vocabulary import MODIFICATION_TAGS

PHRASES_PATH = Path(__file__).parent.parent / "data" / "knowledge" / "modification_phrases.yaml"


def _load():
    with open(PHRASES_PATH) as f:
        return yaml.safe_load(f)


def test_every_modification_tag_has_phrase_entry():
    phrases = _load()
    missing = [t for t in MODIFICATION_TAGS if t not in phrases]
    assert not missing, f"MODIFICATION_TAGS without phrase entry: {missing}"


def test_every_entry_has_short_and_detail():
    phrases = _load()
    for tag, entry in phrases.items():
        assert "short" in entry, f"{tag}: missing 'short'"
        assert "detail" in entry, f"{tag}: missing 'detail'"
        assert isinstance(entry["short"], str) and entry["short"].strip()
        assert isinstance(entry["detail"], str) and entry["detail"].strip()


def test_no_orphan_phrase_entries():
    phrases = _load()
    orphans = [t for t in phrases if t not in MODIFICATION_TAGS]
    assert not orphans, f"Phrase entries not in MODIFICATION_TAGS: {orphans}"
