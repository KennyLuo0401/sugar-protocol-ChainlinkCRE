# Sugar Protocol — LLM Analysis Engine
# Sends article text to OpenAI API with Framework C prompts,
# parses structured JSON output into validated Pydantic models.

from __future__ import annotations

import asyncio
import json
import re
import logging
from typing import Optional

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

import config
from interfaces import AnalysisDepth, AnalyzeError
from .schemas import AnalysisResult, TokenUsage
from .prompts.framework_c import get_system_prompt

logger = logging.getLogger(__name__)

# GPT-4o-mini pricing (per 1M tokens, as of 2024)
_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini-2024-07-18": {"input": 0.15, "output": 0.60},
}


def _fix_json(raw: str) -> str:
    """Attempt to fix common LLM JSON errors.

    Handles:
    - Markdown code fences (```json ... ```)
    - Trailing commas before ] or }
    - Single-line // comments
    """
    # Strip markdown code fences
    raw = raw.strip()
    if raw.startswith("```"):
        # Remove opening fence (with optional language tag)
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    # Remove single-line comments (// ...)
    raw = re.sub(r"//[^\n]*", "", raw)

    # Remove trailing commas: ,] or ,}
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    return raw


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate API cost in USD."""
    pricing = _PRICING.get(model, _PRICING.get("gpt-4o-mini"))
    if pricing is None:
        return 0.0
    input_cost = prompt_tokens * pricing["input"] / 1_000_000
    output_cost = completion_tokens * pricing["output"] / 1_000_000
    return round(input_cost + output_cost, 6)


async def analyze_article(
    text: str,
    depth: AnalysisDepth,
    language: str = "zh",
    model: Optional[str] = None,
) -> AnalysisResult:
    """Analyze article text using OpenAI API with Framework C prompt.

    Args:
        text: Article full text to analyze.
        depth: Analysis depth (SHALLOW, STANDARD, FULL, DEEP).
        language: "zh" or "en" for prompt language.
        model: OpenAI model to use. Defaults to config.DEFAULT_MODEL.

    Returns:
        AnalysisResult with validated entities, claims, omissions, and conflict_graph.

    Raises:
        AnalyzeError: If all retries fail or JSON parsing fails.
    """
    if not text or not text.strip():
        raise AnalyzeError(reason="Empty article text", model=model or config.DEFAULT_MODEL)

    model = model or config.DEFAULT_MODEL
    api_key = config.OPENAI_API_KEY
    if not api_key:
        raise AnalyzeError(reason="OPENAI_API_KEY not set", model=model)

    client = AsyncOpenAI(api_key=api_key, timeout=config.LLM_TIMEOUT, max_retries=0)
    system_prompt = get_system_prompt(depth, language)

    # Truncate overly long text (Jina Reader often includes site chrome)
    max_chars = 10000
    if len(text) > max_chars:
        text = text[:max_chars]
        logger.info("Truncated text from %d to %d chars", len(text), max_chars)

    last_error: Optional[Exception] = None

    for attempt in range(config.LLM_MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw_response = response.choices[0].message.content or ""

            # Parse token usage
            usage = response.usage
            token_usage = TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            )

            # Parse JSON with fixup
            fixed_json = _fix_json(raw_response)
            try:
                parsed = json.loads(fixed_json)
            except json.JSONDecodeError as e:
                logger.warning("JSON parse failed on attempt %d: %s", attempt + 1, e)
                last_error = e
                if attempt < config.LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)
                continue

            # Validate with Pydantic
            result = AnalysisResult(
                article_type=parsed.get("article_type", "unknown"),
                entities=parsed.get("entities", []),
                claims=parsed.get("claims", []),
                omissions=parsed.get("omissions", []),
                conflict_graph=parsed.get("conflict_graph", []),
                raw_response=raw_response,
                model=model,
                token_usage=token_usage,
                cost=_estimate_cost(
                    model,
                    token_usage.prompt_tokens,
                    token_usage.completion_tokens,
                ),
            )

            logger.info(
                "Analysis complete: %d entities, %d claims, %d tokens, $%.4f",
                len(result.entities),
                len(result.claims),
                token_usage.total_tokens,
                result.cost,
            )
            return result

        except (APITimeoutError, RateLimitError) as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning("API error on attempt %d/%d: %s. Retrying in %ds...",
                           attempt + 1, config.LLM_MAX_RETRIES, e, wait)
            if attempt < config.LLM_MAX_RETRIES - 1:
                await asyncio.sleep(wait)

        except APIError as e:
            last_error = e
            logger.error("OpenAI API error: %s", e)
            if attempt < config.LLM_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)

    raise AnalyzeError(
        reason=f"All {config.LLM_MAX_RETRIES} retries failed. Last error: {last_error}",
        model=model,
    )
