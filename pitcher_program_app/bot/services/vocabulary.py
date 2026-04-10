# bot/services/vocabulary.py
"""Shared vocabulary — canonical injury areas and modification tags.

Single source of truth consumed by triage, exercise_pool, and research_resolver.
Adding a new injury area or modification tag here is the ONLY place you need to
update — downstream consumers import from this module.
"""

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
    keywords = set()
    for meta in INJURY_AREAS.values():
        keywords.update(meta["keywords"])
    return keywords


def get_research_triggers_for_injury(area: str) -> list[str]:
    meta = INJURY_AREAS.get(area, {})
    return meta.get("research_triggers", [])


def get_research_triggers_for_mod(tag: str) -> list[str]:
    meta = MODIFICATION_TAGS.get(tag, {})
    return meta.get("research_triggers", [])


def get_mod_description(tag: str) -> str:
    meta = MODIFICATION_TAGS.get(tag, {})
    return meta.get("description", tag.replace("_", " "))
