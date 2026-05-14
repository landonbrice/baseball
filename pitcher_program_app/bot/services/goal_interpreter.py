"""Plan 7 / A11: map a natural-language goal description to a canonical goal_tag.

Called synchronously from the Build form on a 60s budget when the pitcher picks
the "Other / describe..." chip. Returns one of the existing tags in the domain's
template pool, or "unknown" if the description doesn't match.
"""
from __future__ import annotations

import logging

from bot.services import db

INTERPRET_TIMEOUT = 60  # L6 locked
logger = logging.getLogger(__name__)


async def interpret_goal(text: str, domain: str) -> str:
    """Returns a goal_tag string, or "unknown" on no-match.

    LLM call is the slow path; if it times out or fails, returns "unknown" so
    the caller can show an inline error rather than a 500.
    """
    from bot.services.llm import call_llm, load_prompt

    if not text or not text.strip():
        return "unknown"
    if domain not in ("throwing", "lifting"):
        raise ValueError(f"domain must be 'throwing' or 'lifting', got {domain!r}")

    # Build the candidate-tag list dynamically from block_library
    rows = (
        db.get_client().table("block_library")
        .select("goal_tags").eq("domain", domain).execute()
    ).data or []
    candidate_tags = sorted({
        tag for row in rows for tag in (row.get("goal_tags") or [])
    })
    if not candidate_tags:
        return "unknown"

    system = load_prompt("goal_interpreter.md")
    user = (
        f"Domain: {domain}\n"
        f"Available goal tags: {', '.join(candidate_tags)}\n"
        f"Pitcher described their goal as: \"{text}\"\n\n"
        "Return ONE tag from the list that best matches the description, "
        "or the literal string 'unknown' if no tag fits. "
        "Reply with ONLY the tag string — no quotes, no explanation."
    )
    try:
        raw = await call_llm(
            system_prompt=system,
            user_message=user,
            history=[],
            timeout=INTERPRET_TIMEOUT,
        )
    except Exception:
        logger.warning("goal_interpreter LLM call failed", exc_info=True)
        return "unknown"
    tag = (raw or "").strip().lower()
    return tag if tag in candidate_tags else "unknown"
