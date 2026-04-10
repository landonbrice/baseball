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


_index_cache: dict[str, tuple[dict, str]] = {}


def _parse_frontmatter(text: str) -> dict:
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
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)


def _load_index() -> dict[str, tuple[dict, str]]:
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

            if not fm["id"]:
                logger.warning("Research doc %s missing 'id' in frontmatter", filename)
        except Exception as e:
            logger.warning("Error reading research file %s: %s", filename, e)

    logger.info("Research index: %d docs loaded", len(_index_cache))
    return _index_cache


def clear_cache():
    global _index_cache
    _index_cache = {}


def should_fire_research(
    pitcher_profile: dict,
    triage_result: dict | None = None,
    user_message: str | None = None,
) -> tuple[bool, str]:
    if triage_result:
        flag = triage_result.get("flag_level", "green")
        if flag in ("yellow", "red", "modified_green"):
            return True, f"flag_level={flag}"

        mods = triage_result.get("modifications", [])
        if mods:
            first_mod = mods[0] if isinstance(mods[0], str) else str(mods[0])
            return True, f"recent_mod:{first_mod}"

    active_mods = (pitcher_profile.get("active_flags") or {}).get("active_modifications", [])
    if active_mods:
        return True, f"recent_mod:{active_mods[0]}"

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
    index = _load_index()
    loaded: dict[str, tuple[DocRef, str]] = {}

    injury_areas = set()
    for injury in pitcher_profile.get("injury_history", []):
        area = injury.get("area", "").lower()
        if area:
            injury_areas.add(area)

    injury_triggers = set()
    for area in injury_areas:
        injury_triggers.update(get_research_triggers_for_injury(area))

    mod_triggers = set()
    if triage_result:
        for mod in triage_result.get("modifications", []):
            mod_key = mod if isinstance(mod, str) else str(mod)
            mod_triggers.update(get_research_triggers_for_mod(mod_key))

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
