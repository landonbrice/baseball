"""Web research fallback for Q&A. Uses Tavily API if available, else logs."""

import os
import logging
from datetime import datetime
from bot.config import KNOWLEDGE_DIR, CHICAGO_TZ

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def web_search_fallback(question: str, pitcher_id: str) -> str:
    """Fallback when knowledge retrieval returns nothing.

    If TAVILY_API_KEY is set, searches the web and returns relevant snippets.
    Otherwise, logs the question for manual review and returns empty string.
    """
    if TAVILY_API_KEY:
        try:
            return _tavily_search(question)
        except Exception as e:
            logger.warning(f"Web search failed, falling back to log: {e}")

    _log_unanswered(question, pitcher_id)
    return ""


def _tavily_search(question: str) -> str:
    """Search using Tavily API and return formatted snippets."""
    import httpx

    resp = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": TAVILY_API_KEY,
            "query": f"baseball pitcher training {question}",
            "search_depth": "basic",
            "max_results": 3,
            "include_answer": True,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    parts = []

    # Use the AI-generated answer if available
    answer = data.get("answer")
    if answer:
        parts.append(f"Web summary: {answer}")

    # Add top result snippets
    for result in data.get("results", [])[:3]:
        title = result.get("title", "")
        content = result.get("content", "")
        if content:
            parts.append(f"- {title}: {content[:300]}")

    return "\n".join(parts) if parts else ""


def _log_unanswered(question: str, pitcher_id: str) -> None:
    """Append an unanswered question to the tracking file."""
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    path = os.path.join(KNOWLEDGE_DIR, "unanswered_questions.md")

    timestamp = datetime.now(CHICAGO_TZ).strftime("%Y-%m-%d %H:%M")
    entry = f"- [{timestamp}] ({pitcher_id}) {question}\n"

    try:
        with open(path, "a") as f:
            if os.path.getsize(path) == 0:
                f.write("# Unanswered Questions\n\n")
            f.write(entry)
    except OSError:
        # File doesn't exist yet — create with header
        with open(path, "w") as f:
            f.write("# Unanswered Questions\n\n")
            f.write(entry)

    logger.info(f"Logged unanswered question from {pitcher_id}: {question[:80]}")
