"""Unified LLM call function. Wraps the configured provider (DeepSeek by default)."""

import os
import logging
from bot.config import LLM_CONFIG, DEEPSEEK_API_KEY

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

    if provider == "deepseek":
        return await _call_deepseek(system_prompt, user_message, model, tokens, temperature)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def _call_deepseek(
    system_prompt: str, user_message: str, model: str, max_tokens: int, temperature: float
) -> str:
    """Call DeepSeek's OpenAI-compatible API."""
    from openai import AsyncOpenAI, APIError

    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content
    except APIError as e:
        logger.error(f"DeepSeek API error: {e}")
        raise
