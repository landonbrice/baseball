"""Canonical arm assessment classification.

The standard check-in flow must provide a numeric 1-10 arm-feel rating.
This module interprets that number together with required detail chips and
optional text into structured safety signals for triage, plan generation,
and coach visibility.
"""

import re
from typing import Iterable


VALID_DETAIL_TAGS = {
    "no_issues",
    "expected_soreness",
    "tight_sore",
    "heavy_dead",
    "sharp_pain",
    "numb_tingling",
    "forearm",
    "elbow",
    "shoulder",
    "different_than_normal",
    "other",
}

AREA_TAGS = {"forearm", "elbow", "shoulder"}
SENSATION_TAGS = {
    "tight_sore",
    "heavy_dead",
    "sharp_pain",
    "numb_tingling",
    "different_than_normal",
}
CONCERN_TAGS = SENSATION_TAGS | {"expected_soreness", "other"}
RED_FLAG_TAGS = {"sharp_pain", "numb_tingling", "different_than_normal"}
HIGH_PRIORITY_RED_FLAGS = {
    "sharp_pain",
    "numb_tingling",
    "swelling",
    "felt_a_pop",
    "grip_weakness",
}

AREA_PATTERNS = {
    "forearm": [r"\bforearm\b", r"\bflexor\b", r"\bpronator\b"],
    "elbow": [r"\belbow\b", r"\bmedial elbow\b", r"\bucl\b"],
    "shoulder": [r"\bshoulder\b"],
    "bicep": [r"\bbiceps?\b"],
    "lat": [r"\blat\b", r"\blats\b"],
    "scap": [r"\bscap\b", r"\bscapula\b"],
    "back": [r"\bback\b"],
}

SENSATION_PATTERNS = {
    "tight_sore": [
        r"\btight(?:ness)?\b", r"\bsore(?:ness)?\b", r"\bstiff(?:ness)?\b",
        r"\btender(?:ness)?\b", r"\bach(?:e|y|ing)?\b",
    ],
    "heavy_dead": [r"\bheavy\b", r"\bdead arm\b", r"\bsluggish\b", r"\bdrained\b"],
    "sharp_pain": [r"\bsharp\b", r"\bshooting\b", r"\bstabbing\b", r"\bneedle\b"],
    "numb_tingling": [
        r"\bnumb(?:ness)?\b", r"\btingl(?:e|ing)\b", r"\bpins and needles\b",
    ],
    "different_than_normal": [
        r"\bdifferent\b", r"\bweird\b", r"\boff\b", r"\bnot normal\b",
        r"\bunusual\b",
    ],
}

RED_FLAG_PATTERNS = {
    "swelling": [r"\bswell(?:ing)?\b", r"\binflamed\b"],
    "felt_a_pop": [r"\bpop(?:ped)?\b", r"\bfelt a pop\b"],
    "grip_weakness": [r"\bgrip\b.*\bweak", r"\bweak\b.*\bgrip"],
    "could_not_get_loose": [r"\bcould(?:n't| not) get loose\b", r"\bcan't get loose\b"],
    "pain_throwing": [r"\bpain\b.*\bthrow", r"\bthrow(?:ing)?\b.*\bpain\b"],
    "lost_velo": [r"\blost velo\b", r"\bvelocity down\b", r"\bvelo down\b"],
}

EXPECTED_SORENESS_PATTERNS = [
    r"\bexpected soreness\b", r"\bnormal soreness\b", r"\bregular soreness\b",
    r"\bday after soreness\b",
]

NO_ISSUES_PATTERNS = [
    r"\bno issues\b", r"\bfeels fine\b", r"\bfeel fine\b", r"\ball good\b",
    r"\bnothing wrong\b", r"\bno problems\b",
]

TREND_PATTERNS = {
    "better": [r"\bbetter\b", r"\bimprov(?:e|ing|ed)\b"],
    "worse": [r"\bworse\b", r"\bdeclin(?:e|ing|ed)\b", r"\bmore sore\b"],
    "new": [r"\bnew\b", r"\bfirst time\b"],
    "same": [r"\bsame\b", r"\bunchanged\b", r"\bnormal\b"],
}


def _normalize_tags(detail_tags: Iterable[str] | None) -> list[str]:
    tags: list[str] = []
    for raw in detail_tags or []:
        tag = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "tight/sore": "tight_sore",
            "heavy/dead": "heavy_dead",
            "sharp": "sharp_pain",
            "sharp_pain": "sharp_pain",
            "numb/tingling": "numb_tingling",
            "different_than_normal": "different_than_normal",
            "no_issue": "no_issues",
        }
        tag = aliases.get(tag, tag)
        if tag in VALID_DETAIL_TAGS and tag not in tags:
            tags.append(tag)
    return tags


def _has_pattern(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _signal_present(text: str, patterns: list[str]) -> bool:
    """Return true when a signal appears outside a nearby negation."""
    if not text:
        return False
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            before = text[max(0, match.start() - 32):match.start()].lower()
            phrase = text[max(0, match.start() - 16):match.end() + 16].lower()
            if re.search(r"\b(no|not|nothing|without|never)\W+(\w+\W+){0,3}$", before):
                continue
            if re.search(r"\bno\s+\w*\s*" + re.escape(match.group(0).lower()), phrase):
                continue
            return True
    return False


def _derive_trend(raw_text: str, recent_entries: list | None, arm_feel: int) -> str:
    text = (raw_text or "").lower()
    for trend, patterns in TREND_PATTERNS.items():
        if _has_pattern(text, patterns):
            return trend

    if recent_entries:
        for entry in recent_entries:
            prev = (entry.get("pre_training") or {}).get("arm_feel")
            if isinstance(prev, (int, float)):
                if arm_feel - prev >= 2:
                    return "better"
                if prev - arm_feel >= 2:
                    return "worse"
                return "same"
    return "unknown"


def _injury_area_overlap(areas: list[str], pitcher_profile: dict | None) -> bool:
    if not pitcher_profile:
        return False
    injuries = pitcher_profile.get("injury_history") or []
    injury_text = " ".join(str(injury.get("area", "")) for injury in injuries).lower()
    for area in areas:
        if area in injury_text:
            return True
        if area == "elbow" and "medial_elbow" in injury_text:
            return True
    return False


def _severity(arm_feel: int, sensations: list[str], red_flags: list[str], expected_soreness: bool) -> str:
    if any(flag in HIGH_PRIORITY_RED_FLAGS for flag in red_flags):
        return "high"
    if arm_feel <= 2:
        return "high"
    if arm_feel <= 4:
        return "moderate"
    if "heavy_dead" in sensations:
        return "moderate"
    if "tight_sore" in sensations:
        return "low" if arm_feel >= 7 or expected_soreness else "moderate"
    if red_flags:
        return "moderate"
    if sensations:
        return "low"
    return "none"


def _followup_prompt(arm_feel: int, areas: list[str], sensations: list[str], contradictions: list[str], red_flags: list[str]) -> str:
    area_text = areas[0] if areas else "arm"
    if "sensation_without_area" in contradictions:
        return "Where are you feeling that?"
    if "area_without_sensation" in contradictions:
        return f"What about the {area_text}?"
    if "expected_soreness_without_area" in contradictions:
        return "Where is the expected soreness?"
    if "high_arm_feel_with_red_flag" in contradictions:
        sensation = sensations[0].replace("_", " ") if sensations else "red-flag symptom"
        return (
            f"You rated the arm high but reported {sensation} around the {area_text}. "
            "Did that show up while throwing, lifting, or only with a specific movement?"
        )
    if "low_arm_feel_with_no_issues" in contradictions:
        return "You rated the arm low but selected no issues. Is the low score soreness, fatigue, or something else?"
    if red_flags:
        return "That detail can matter. Did it happen while throwing, lifting, or with a specific movement?"
    return ""


def _summary(arm_feel: int, areas: list[str], sensations: list[str], severity: str, red_flags: list[str], contradictions: list[str]) -> str:
    if "no_issues_with_concern_tags" in contradictions:
        return f"Arm {arm_feel}/10 with no issues plus concern tags selected."
    if not areas and not sensations and not red_flags:
        return f"Arm {arm_feel}/10 with no issues reported."
    parts = [f"Arm {arm_feel}/10"]
    if sensations:
        parts.append(", ".join(s.replace("_", " ") for s in sensations))
    if areas:
        parts.append("in " + ", ".join(areas))
    if red_flags:
        parts.append("red flags: " + ", ".join(red_flags))
    if contradictions:
        parts.append("follow up")
    return " - ".join(parts) + f" (severity {severity})."


async def classify_arm_assessment(
    numeric_arm_feel: int,
    detail_tags: list[str] | None = None,
    arm_report: str = "",
    pitcher_profile: dict | None = None,
    recent_entries: list | None = None,
    days_since_outing: int | None = None,
) -> dict:
    """Classify a numeric arm rating plus details into structured signals."""
    try:
        arm_feel = int(numeric_arm_feel)
    except (TypeError, ValueError) as exc:
        raise ValueError("numeric_arm_feel is required and must be 1-10") from exc
    if arm_feel < 1 or arm_feel > 10:
        raise ValueError("numeric_arm_feel must be between 1 and 10")

    raw_text = (arm_report or "").strip()
    text = raw_text.lower()
    tags = _normalize_tags(detail_tags)

    areas = [tag for tag in tags if tag in AREA_TAGS]
    for area, patterns in AREA_PATTERNS.items():
        if _signal_present(text, patterns) and area not in areas:
            areas.append(area)

    sensations = [tag for tag in tags if tag in SENSATION_TAGS]
    for sensation, patterns in SENSATION_PATTERNS.items():
        if _signal_present(text, patterns) and sensation not in sensations:
            sensations.append(sensation)

    red_flags = [tag for tag in sensations if tag in RED_FLAG_TAGS]
    for flag, patterns in RED_FLAG_PATTERNS.items():
        if _signal_present(text, patterns) and flag not in red_flags:
            red_flags.append(flag)

    if _injury_area_overlap(areas, pitcher_profile) and "injury_history_area" not in red_flags:
        # Not a red flag by itself, but useful for conservative triage logic.
        red_flags.append("injury_history_area")

    has_expected_soreness_signal = "expected_soreness" in tags or _has_pattern(text, EXPECTED_SORENESS_PATTERNS)
    expected_soreness = bool(has_expected_soreness_signal and areas and not any(flag in HIGH_PRIORITY_RED_FLAGS for flag in red_flags))

    no_issues = "no_issues" in tags or _has_pattern(text, NO_ISSUES_PATTERNS)
    concern_tags = [tag for tag in tags if tag in CONCERN_TAGS]

    contradictions = []
    if arm_feel >= 8 and red_flags:
        contradictions.append("high_arm_feel_with_red_flag")
    if arm_feel <= 4 and no_issues:
        contradictions.append("low_arm_feel_with_no_issues")
    if no_issues and concern_tags:
        contradictions.append("no_issues_with_concern_tags")
    if has_expected_soreness_signal and any(flag in HIGH_PRIORITY_RED_FLAGS for flag in red_flags):
        contradictions.append("expected_soreness_with_red_flag")
    if has_expected_soreness_signal and not areas:
        contradictions.append("expected_soreness_without_area")
    if sensations and not areas:
        contradictions.append("sensation_without_area")
    if areas and not sensations and not no_issues and not has_expected_soreness_signal:
        contradictions.append("area_without_sensation")

    severity = _severity(arm_feel, sensations, red_flags, expected_soreness)
    trend = _derive_trend(raw_text, recent_entries, arm_feel)
    needs_followup = bool(
        contradictions
        or any(flag in RED_FLAG_TAGS or flag in HIGH_PRIORITY_RED_FLAGS for flag in red_flags)
        or "other" in tags
    )
    if has_expected_soreness_signal and days_since_outing is not None and days_since_outing > 2:
        needs_followup = True

    confidence = "high"
    if raw_text and not tags:
        confidence = "medium"
    if not tags and not raw_text:
        confidence = "low"
    if contradictions:
        confidence = "medium"

    followup_prompt = _followup_prompt(arm_feel, areas, sensations, contradictions, red_flags) if needs_followup else ""

    return {
        "arm_feel": arm_feel,
        "raw_text": raw_text,
        "detail_tags": tags,
        "areas": areas,
        "sensations": sensations,
        "severity": severity,
        "trend": trend,
        "expected_soreness": expected_soreness,
        "red_flags": red_flags,
        "contradictions": contradictions,
        "confidence": confidence,
        "needs_followup": needs_followup,
        "followup_prompt": followup_prompt,
        "summary": _summary(arm_feel, areas, sensations, severity, red_flags, contradictions),
    }
