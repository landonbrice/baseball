"""Unit tests for the deterministic repair plane (`_normalize_authored_dict`).

Each normalization class was observed in a real live-LLM run (see the
docstring in author.py). These tests synthesize the observed near-miss
shapes and assert the normalizer rearranges them into schema-valid form —
the full Pydantic gate still runs after normalization in production.
"""

from bot.services.program_engine.author import _normalize_authored_dict
from bot.services.program_engine.schemas import PitcherProgram


def _exercise(**over):
    ex = {"exercise_id": "ex_002", "sets": 3, "reps": "5", "superset_group": None}
    ex.update(over)
    return ex


def _block(**over):
    b = {"block_name": "Lower Strength", "exercises": [_exercise()]}
    b.update(over)
    return b


def _day(i, **over):
    d = {
        "day_index": i,
        "template_key": f"wk1_d{i + 1}",
        "date": f"2026-07-{13 + i:02d}",
        "anchor_kind": "calendar_relative",
        "lifting_blocks": [],
    }
    d.update(over)
    return d


def _program(days):
    return {
        "pitcher_id": "landon_brice",
        "goal": "return_to_play",
        "total_weeks": 1,
        "knowledge_version": "test_kv_12345678",
        "generated_at": "2026-07-13T00:00:00Z",
        "phases": [
            {
                "phase_id": "base",
                "name": "Base",
                "week_count": 1,
                "phase_type": "base",
                "intent_summary": "Rebuild base.",
            }
        ],
        "days": days,
        "rationale": {
            "phase_logic": "test",
            "individualization_notes": "test",
            "cited_research_doc_ids": [],
            "citations": [],
        },
    }


def test_migrant_days_lifted_out_of_lifting_blocks():
    """Runs #4/#8/#9: a bracket slip nests day N+1 (and recursively all later
    days) inside day N's lifting_blocks. The normalizer must flatten the chain
    back into the days array in chronological order."""
    day2 = _day(2)
    day1 = _day(1, lifting_blocks=[_block(), day2])  # day2 nested in day1
    day0 = _day(0, lifting_blocks=[_block(), day1])  # day1 nested in day0
    data = _normalize_authored_dict(_program([day0]))

    assert [d["day_index"] for d in data["days"]] == [0, 1, 2]
    for d in data["days"]:
        for b in d["lifting_blocks"]:
            assert "block_name" in b  # only real blocks remain

    PitcherProgram.model_validate(data)  # full schema gate passes


def test_stray_day_fields_moved_from_block_to_day():
    """The same bracket slip strands the day's trailing day_focus/cues inside
    its last lifting block."""
    block = _block(day_focus="Heavy lower day.", cues=["Brace hard."])
    day = _day(0, lifting_blocks=[block])
    data = _normalize_authored_dict(_program([day]))

    d0 = data["days"][0]
    assert d0["day_focus"] == "Heavy lower day."
    assert d0["cues"] == ["Brace hard."]
    assert "day_focus" not in d0["lifting_blocks"][0]
    assert "cues" not in d0["lifting_blocks"][0]
    PitcherProgram.model_validate(data)


def test_stray_fields_do_not_overwrite_existing_day_fields():
    block = _block(day_focus="from block")
    day = _day(0, lifting_blocks=[block], day_focus="from day")
    data = _normalize_authored_dict(_program([day]))
    assert data["days"][0]["day_focus"] == "from day"


def test_empty_superset_group_coerced_to_none():
    """Run #7: model emits "" for ungrouped exercises."""
    day = _day(0, lifting_blocks=[_block(exercises=[_exercise(superset_group="")])])
    data = _normalize_authored_dict(_program([day]))
    assert data["days"][0]["lifting_blocks"][0]["exercises"][0]["superset_group"] is None
    PitcherProgram.model_validate(data)


def test_overlong_capped_strings_clipped():
    """Run #8 attempt 1: one over-cap intent_summary killed a valid program."""
    day = _day(0, day_focus="x" * 300, lifting_blocks=[_block(block_name="b" * 100)])
    prog = _program([day])
    prog["phases"][0]["intent_summary"] = "y" * 500
    data = _normalize_authored_dict(prog)

    assert len(data["days"][0]["day_focus"]) == 120
    assert len(data["days"][0]["lifting_blocks"][0]["block_name"]) == 60
    assert len(data["phases"][0]["intent_summary"]) == 240
    PitcherProgram.model_validate(data)


def test_null_lifting_blocks_becomes_empty_list():
    day = _day(0, lifting_blocks=None)
    data = _normalize_authored_dict(_program([day]))
    assert data["days"][0]["lifting_blocks"] == []
    PitcherProgram.model_validate(data)
