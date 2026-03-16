"""Web research fallback for Q&A. MVP: logs unanswered questions."""

import os
import logging
from datetime import datetime
from bot.config import KNOWLEDGE_DIR

logger = logging.getLogger(__name__)


def web_search_fallback(question: str, pitcher_id: str) -> str:
    """Fallback when knowledge retrieval returns nothing.

    MVP: logs the question to unanswered_questions.md for manual review.
    Returns empty string (signals no web result found).

    TODO: Wire in a real search API (e.g., Tavily, SerpAPI) here.
    The flow would be:
        1. Search for the question
        2. Parse top 2-3 results
        3. Return relevant snippets as context
    """
    _log_unanswered(question, pitcher_id)
    return ""


def _log_unanswered(question: str, pitcher_id: str) -> None:
    """Append an unanswered question to the tracking file."""
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    path = os.path.join(KNOWLEDGE_DIR, "unanswered_questions.md")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
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
