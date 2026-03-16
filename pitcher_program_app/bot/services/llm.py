"""Unified LLM call function. Wraps the configured provider (Anthropic by default)."""

import os
import logging
from bot.config import LLM_CONFIG, ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template from bot/prompts/."""
    prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    path = os.path.join(prompts_dir, prompt_name)
    with open(path, "r") as f:
        return f.read()


async def call_llm(system_prompt: str, user_message: str, max_tokens: int = None) -> str:
    """Call the configured LLM and return the response text.

    Args:
        system_prompt: The system prompt (with context stuffed in).
        user_message: The user-facing message or structured input.
        max_tokens: Override for max response tokens.

    Returns:
        The LLM's response text.
    """
    provider = LLM_CONFIG["provider"]
    model = LLM_CONFIG["model"]
    tokens = max_tokens or LLM_CONFIG["max_tokens"]
    temperature = LLM_CONFIG["temperature"]

    if provider == "anthropic":
        return await _call_anthropic(system_prompt, user_message, model, tokens, temperature)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def _call_anthropic(
    system_prompt: str, user_message: str, model: str, max_tokens: int, temperature: float
) -> str:
    """Call Anthropic's Messages API."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        raise
