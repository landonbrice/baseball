"""Unified LLM call function. Wraps the configured provider (DeepSeek by default).

Supports model routing:
- call_llm(): uses deepseek-chat (fast, cheap, good for daily plans and Q&A)
- call_llm_reasoning(): uses deepseek-reasoner (slower, deeper, for complex protocols)

The reasoning model is used for multi-day programs, return-to-throw progressions,
and any request that needs the depth of a real coaching plan.
"""

import asyncio
import os
import logging
from bot.config import LLM_CONFIG, DEEPSEEK_API_KEY

logger = logging.getLogger(__name__)

# Timeouts (seconds) for each model tier
FAST_TIMEOUT = 20
REASONING_TIMEOUT = 45


def load_prompt(prompt_name: str) -> str:
    """Load a prompt template from bot/prompts/."""
    prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    path = os.path.join(prompts_dir, prompt_name)
    with open(path, "r") as f:
        return f.read()


async def call_llm(
    system_prompt: str, user_message: str, max_tokens: int = None,
    history: list = None, model: str = None, timeout: int = None,
) -> str:
    """Call the configured LLM and return the response text.

    Args:
        system_prompt: The system prompt (with context stuffed in).
        user_message: The user-facing message or structured input.
        max_tokens: Override for max response tokens.
        history: Optional conversation history (list of {role, content} dicts).
        model: Override model name (e.g. "deepseek-reasoner" for complex tasks).
        timeout: Override timeout in seconds.
    """
    provider = LLM_CONFIG["provider"]
    model = model or LLM_CONFIG["model"]
    tokens = max_tokens or LLM_CONFIG["max_tokens"]
    temperature = LLM_CONFIG["temperature"]
    is_reasoning = model == LLM_CONFIG.get("model_reasoning", "deepseek-reasoner")
    timeout = timeout or (REASONING_TIMEOUT if is_reasoning else FAST_TIMEOUT)

    if provider == "deepseek":
        return await _call_deepseek(system_prompt, user_message, model, tokens, temperature, history, timeout)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


async def call_llm_reasoning(
    system_prompt: str, user_message: str, max_tokens: int = 4000,
    history: list = None,
) -> str:
    """Call the reasoning model for complex multi-step protocol generation.

    Used for: multi-day programs, return-to-throw progressions, post-outing
    recovery protocols, anything needing deep domain reasoning.

    Uses deepseek-reasoner which does chain-of-thought before answering.
    Higher token budget (4000) for detailed output.
    """
    model = LLM_CONFIG.get("model_reasoning", "deepseek-reasoner")
    logger.info(f"Using reasoning model: {model}")
    return await call_llm(
        system_prompt, user_message, max_tokens=max_tokens,
        history=history, model=model, timeout=REASONING_TIMEOUT,
    )


async def _call_deepseek(
    system_prompt: str, user_message: str, model: str, max_tokens: int,
    temperature: float, history: list = None, timeout: int = FAST_TIMEOUT,
) -> str:
    """Call DeepSeek's OpenAI-compatible API with timeout."""
    from openai import AsyncOpenAI, APIError

    client = AsyncOpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
        timeout=timeout,
    )

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            ),
            timeout=timeout,
        )
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        logger.error(f"DeepSeek timeout after {timeout}s ({model})")
        raise TimeoutError(f"LLM call timed out after {timeout}s")
    except APIError as e:
        logger.error(f"DeepSeek API error ({model}): {e}")
        raise
