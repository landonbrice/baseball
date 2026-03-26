"""Knowledge retrieval. Keyword-matches research docs + searches exercise library.

Research docs in data/knowledge/research/ have YAML front matter with keywords:
    ---
    keywords: [tight, forearm, ucl, pronator, ...]
    type: core_research
    ---

Two retrieval modes:
- retrieve_knowledge(question): keyword-matches query against research docs (for Q&A)
- retrieve_research_for_plan(pitcher_profile): loads docs relevant to a pitcher's
  injury areas + always loads triage and recovery (for plan generation)
"""

import json
import os
import re
import logging
from bot.config import KNOWLEDGE_DIR

logger = logging.getLogger(__name__)

RESEARCH_DIR = os.path.join(KNOWLEDGE_DIR, "research")

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

# Cache: maps filename -> (keywords, type, content)
_research_cache: dict[str, tuple[list[str], str, str]] = {}


def _parse_front_matter(text: str) -> tuple[list[str], str]:
    """Extract keywords and type from YAML front matter.

    Returns (keywords_list, doc_type).
    """
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return [], ""
    keywords = []
    doc_type = ""
    for line in match.group(1).split("\n"):
        line = line.strip()
        if line.startswith("keywords:"):
            raw = line[len("keywords:"):].strip()
            if raw.startswith("[") and raw.endswith("]"):
                keywords = [k.strip().strip("\"'") for k in raw[1:-1].split(",") if k.strip()]
        elif line.startswith("type:"):
            doc_type = line[len("type:"):].strip()
    return keywords, doc_type


def _strip_front_matter(text: str) -> str:
    """Remove YAML front matter from content for injection."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL)


def _load_research_index() -> dict[str, tuple[list[str], str, str]]:
    """Scan research/ directory and build keyword index.

    Returns dict: filename -> (keywords, type, content_without_frontmatter)
    Caches results after first call.
    """
    global _research_cache
    if _research_cache:
        return _research_cache

    if not os.path.exists(RESEARCH_DIR):
        logger.warning(f"Research directory not found: {RESEARCH_DIR}")
        return {}

    for filename in os.listdir(RESEARCH_DIR):
        if not filename.endswith(".md") or filename == "INDEX.md":
            continue
        filepath = os.path.join(RESEARCH_DIR, filename)
        try:
            with open(filepath, "r") as f:
                content = f.read()
            keywords, doc_type = _parse_front_matter(content)
            if keywords:
                _research_cache[filename] = (keywords, doc_type, _strip_front_matter(content))
        except Exception as e:
            logger.warning(f"Error reading research file {filename}: {e}")

    logger.info(f"Loaded {len(_research_cache)} research docs with keywords")
    return _research_cache


def retrieve_knowledge(question: str, max_docs: int = 3, max_chars: int = 8000) -> str:
    """Keyword-match a question against research docs + exercise library.

    Used for Q&A. Returns formatted context string for prompt injection.
    """
    query_lower = question.lower()
    results = []

    # 1. Keyword-match research docs
    index = _load_research_index()
    scored_docs = []
    for filename, (keywords, doc_type, content) in index.items():
        matches = sum(1 for kw in keywords if kw in query_lower)
        if matches > 0:
            scored_docs.append((filename, matches, content))

    # Sort by match count, take top N
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    for filename, score, content in scored_docs[:max_docs]:
        results.append(content)
        logger.info(f"Knowledge match: {filename} (score={score})")

    # 2. Search exercise library
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


def retrieve_research_for_plan(pitcher_profile: dict, max_chars: int = 12000) -> str:
    """Load research docs relevant to a pitcher's profile for plan generation.

    Always loads: tightness_triage_framework, recovery_physiology.
    Conditionally loads based on injury areas:
      - medial_elbow/forearm → ucl_flexor_pronator_protection, FPM
      - shoulder → arm_care_program
    Also loads docs matching the pitcher's active modifications.

    Returns combined research text for injection into plan prompt.
    """
    index = _load_research_index()
    loaded = {}  # filename -> content (dedup)

    # Always load triage + recovery for plan generation
    always_load = ["tightness_triage_framework.md", "recovery_physiology.md"]
    for filename in always_load:
        if filename in index:
            loaded[filename] = index[filename][2]

    # Load based on pitcher injury areas
    injury_areas = set()
    for injury in pitcher_profile.get("injury_history", []):
        area = injury.get("area", "").lower()
        if area:
            injury_areas.add(area)

    # Map injury areas to research keywords for matching
    injury_keywords = set()
    for area in injury_areas:
        if area in ("medial_elbow", "forearm"):
            injury_keywords.update(["ucl", "flexor", "pronator", "fpm", "forearm", "medial", "elbow"])
        elif area in ("shoulder",):
            injury_keywords.update(["shoulder", "scapular", "arm care", "external rotation"])
        elif area in ("lower_back",):
            injury_keywords.update(["workload", "load management", "strength"])
        elif area in ("oblique",):
            injury_keywords.update(["workload", "training"])

    # Match injury keywords against research docs
    for filename, (keywords, doc_type, content) in index.items():
        if filename in loaded:
            continue
        if any(ik in keywords for ik in injury_keywords):
            loaded[filename] = content

    # Also load based on active modifications
    mods = (pitcher_profile.get("active_flags") or {}).get("active_modifications", [])
    mod_keywords = set()
    for mod in mods:
        mod_lower = mod.lower()
        if "fpm" in mod_lower or "pronator" in mod_lower:
            mod_keywords.update(["fpm", "flexor", "pronator", "ucl"])
        if "pressing" in mod_lower or "shoulder" in mod_lower:
            mod_keywords.update(["shoulder", "arm care"])
        if "axial" in mod_lower:
            mod_keywords.update(["workload", "load"])

    for filename, (keywords, doc_type, content) in index.items():
        if filename in loaded:
            continue
        if any(mk in keywords for mk in mod_keywords):
            loaded[filename] = content

    if not loaded:
        return ""

    combined = "\n\n---\n\n".join(loaded.values())
    if len(combined) > max_chars:
        combined = combined[:max_chars]

    logger.info(f"Plan research: loaded {len(loaded)} docs ({', '.join(loaded.keys())})")
    return combined


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


# ── Research Generation (ported from arm-care-bot) ──

RESEARCH_SYSTEM_PROMPT = """\
You are a sports science research synthesizer. Your task is to produce a comprehensive, \
well-structured research document on the given topic, specifically oriented toward \
college pitchers managing arm health and training.

Structure your output as a Markdown document with:
1. YAML front matter (delimited by ---) containing a keywords field with 8-15 lowercase \
search terms relevant to this topic, and a type field set to "core_research"
2. A clear H1 title
3. Sections covering: mechanisms/physiology, current evidence, practical applications \
for a college pitcher, and key takeaways
4. Cite specific studies or established findings where possible (author, year or \
"established finding")
5. Be thorough but focus on actionable knowledge — this document will be used as \
reference material for an AI assistant advising pitchers

Keep the document between 1500-4000 words. Prioritize depth and accuracy over breadth.\
"""


async def classify_and_generate_research(question: str):
    """Classify a question and generate new research if needed.

    Called when retrieve_knowledge() finds no matching docs.
    Returns the new research content if generated, or None.
    """
    from bot.services.llm import call_llm, call_llm_reasoning

    # Build list of existing topics
    index = _load_research_index()
    existing_topics = [fn.replace(".md", "").replace("_", " ") for fn in index.keys()]

    # Classify: QUICK or RESEARCH
    try:
        classification_response = await call_llm(
            "You classify questions from college pitchers about training and arm care.\n\n"
            f"Existing research files cover: {', '.join(existing_topics)}\n\n"
            "Classify as QUICK (answerable with existing knowledge) or RESEARCH "
            "(needs a new deep-dive document).\n"
            "Return ONLY valid JSON:\n"
            'QUICK: {"type": "quick"}\n'
            'RESEARCH: {"type": "research", "topic": "<concise>", '
            '"filename": "<snake_case>", "keywords": ["kw1", "kw2", ...]}\n',
            question,
            max_tokens=200,
        )
        import json as _json
        result = _json.loads(classification_response.strip())
    except Exception as e:
        logger.warning(f"Research classification failed: {e}")
        return None

    if result.get("type") != "research":
        return None

    topic = result.get("topic", question[:50])
    filename = result.get("filename", "auto_research")
    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    logger.info(f"Generating research: {topic} → {filename}")

    # Generate the research document using reasoning model
    try:
        content = await call_llm_reasoning(
            RESEARCH_SYSTEM_PROMPT,
            f"Topic: {topic}\n\nOriginal question: {question}\n\nProduce the research document.",
            max_tokens=4000,
        )
    except Exception as e:
        logger.error(f"Research generation failed: {e}")
        return None

    # Save to research directory
    save_path = os.path.join(RESEARCH_DIR, filename)
    try:
        with open(save_path, "w") as f:
            f.write(content)
        logger.info(f"Saved new research: {save_path}")

        # Update INDEX.md
        from datetime import date
        index_path = os.path.join(RESEARCH_DIR, "INDEX.md")
        row = f"| {filename} | {topic} | {date.today().isoformat()} | Auto-generated |\n"
        if os.path.exists(index_path):
            with open(index_path, "a") as f:
                f.write(row)
        else:
            with open(index_path, "w") as f:
                f.write("# Research Index\n\n| File | Topic | Date | Key Finding |\n|---|---|---|---|\n" + row)

        # Clear cache so new doc is discoverable
        global _research_cache
        _research_cache = {}

        # data_sync disabled — Supabase is source of truth

        return content
    except Exception as e:
        logger.error(f"Failed to save research: {e}")
        return None
