"""Knowledge retrieval for Q&A. Searches research base and exercise library."""

import json
import os
import re
import logging
from bot.config import KNOWLEDGE_DIR

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "between",
    "through", "during", "before", "after", "above", "below", "and", "but",
    "or", "nor", "not", "so", "if", "then", "than", "too", "very", "just",
    "how", "what", "why", "when", "where", "which", "who", "whom", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "it", "its", "they", "their", "he", "she", "him", "her",
}


def retrieve_knowledge(question: str, max_chunks: int = 2, max_tokens: int = 1000) -> str:
    """Search research base and exercise library for relevant knowledge.

    Returns formatted context string for prompt injection, or empty string.
    """
    keywords = _extract_keywords(question)
    if not keywords:
        return ""

    results = []

    # Search research sections
    sections = _load_research_sections()
    scored = [(s, _score_section(s, keywords)) for s in sections]
    scored.sort(key=lambda x: x[1], reverse=True)

    for section, score in scored[:max_chunks]:
        if score > 0:
            results.append(section["content"])

    # Search exercises
    exercises = _search_exercises(question, keywords)
    for ex in exercises[:3]:
        results.append(_format_exercise(ex))

    if not results:
        return ""

    combined = "\n\n---\n\n".join(results)
    # Rough token limit (4 chars ≈ 1 token)
    if len(combined) > max_tokens * 4:
        combined = combined[: max_tokens * 4]

    return combined


def _load_research_sections() -> list[dict]:
    """Split research markdown files by ## or ### headers into chunks."""
    sections = []

    for filename in ["FINAL_research_base.md", "extended_knowledge.md"]:
        path = os.path.join(KNOWLEDGE_DIR, filename)
        if not os.path.exists(path):
            continue
        with open(path, "r") as f:
            content = f.read()

        # Split by ## headers
        parts = re.split(r"(?=^##\s)", content, flags=re.MULTILINE)
        for part in parts:
            part = part.strip()
            if not part or len(part) < 30:
                continue
            # Extract title from first line
            title_match = re.match(r"^#{2,3}\s+(.+)", part)
            title = title_match.group(1) if title_match else ""
            sections.append({
                "title": title.lower(),
                "content": part,
                "source": filename,
            })

    return sections


def _score_section(section: dict, keywords: list[str]) -> float:
    """Score a section by keyword overlap. Title matches weighted 3x."""
    if not keywords:
        return 0.0

    title = section["title"]
    content_lower = section["content"].lower()
    score = 0.0

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title:
            score += 3.0
        if kw_lower in content_lower:
            score += 1.0

    return score / len(keywords)


def _search_exercises(question: str, keywords: list[str]) -> list[dict]:
    """Search exercise library by name, aliases, tags, and category."""
    lib_path = os.path.join(KNOWLEDGE_DIR, "exercise_library.json")
    if not os.path.exists(lib_path):
        return []

    try:
        with open(lib_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    exercises = data.get("exercises", [])
    scored = []

    for ex in exercises:
        score = 0.0
        searchable = " ".join([
            ex.get("name", ""),
            " ".join(ex.get("aliases", [])),
            " ".join(ex.get("tags", [])),
            ex.get("category", ""),
            ex.get("subcategory", ""),
            ex.get("pitching_relevance", ""),
        ]).lower()

        for kw in keywords:
            if kw.lower() in searchable:
                # Name/alias match worth more
                name_field = (ex.get("name", "") + " " + " ".join(ex.get("aliases", []))).lower()
                if kw.lower() in name_field:
                    score += 3.0
                else:
                    score += 1.0

        if score > 0:
            scored.append((ex, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [ex for ex, _ in scored]


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text, removing stop words."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def _format_exercise(ex: dict) -> str:
    """Format an exercise entry for prompt injection."""
    parts = [f"**{ex.get('name', 'Unknown')}**"]

    if ex.get("category"):
        parts.append(f"Category: {ex['category']}")
    if ex.get("muscles_primary"):
        parts.append(f"Primary muscles: {', '.join(ex['muscles_primary'])}")
    if ex.get("pitching_relevance"):
        parts.append(f"Pitching relevance: {ex['pitching_relevance']}")

    rx = ex.get("prescription", {})
    if rx:
        for phase, details in rx.items():
            if isinstance(details, dict):
                sets = details.get("sets", "")
                reps = details.get("reps", "")
                intensity = details.get("intensity", "")
                parts.append(f"  {phase}: {sets}x{reps} @ {intensity}")

    return "\n".join(parts)
