"""Structured-output LLM calls (Responses API + Pydantic) with usage and latency capture."""

import time
from typing import TypeVar

from openai.lib._parsing._responses import type_to_text_format_param
from pydantic import BaseModel, ValidationError

from .clients import openai_client
from .schemas import LLMUsage

T = TypeVar("T", bound=BaseModel)


class LLMOutputError(RuntimeError):
    pass


def structured_call(
    *,
    step: str,
    model: str,
    instructions: str,
    input: str,
    schema: type[T],
    effort: str | None = None,
    max_output_tokens: int | None = None,
    attempts: int = 2,
) -> tuple[T, LLMUsage]:
    """Return the parsed, validated object and the usage of the successful call."""
    kwargs = {"reasoning": {"effort": effort}} if effort else {}
    if max_output_tokens:
        kwargs["max_output_tokens"] = max_output_tokens
    last_error: Exception | None = None
    text_format = {"format": type_to_text_format_param(schema)}
    for _ in range(attempts):
        start = time.perf_counter()
        # responses.parse validates each output chunk separately and breaks when the JSON spans several chunks
        response = openai_client().responses.create(
            model=model, instructions=instructions, input=input, text=text_format, store=False, **kwargs
        )
        if response.status != "completed":
            last_error = LLMOutputError(f"{step}: status={response.status} {response.incomplete_details}")
            continue
        try:
            parsed = schema.model_validate_json(response.output_text)
        except ValidationError as exc:
            last_error = exc
            continue
        return parsed, _usage(step, model, response, time.perf_counter() - start)
    raise LLMOutputError(f"{step}: failed after {attempts} attempts: {last_error}") from last_error


def _usage(step: str, model: str, response, seconds: float) -> LLMUsage:
    usage = response.usage
    if usage is None:
        return LLMUsage(step=step, model=model, seconds=round(seconds, 2))
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return LLMUsage(
        step=step,
        model=model,
        seconds=round(seconds, 2),
        input_tokens=usage.input_tokens,
        cached_tokens=getattr(input_details, "cached_tokens", 0) or 0,
        output_tokens=usage.output_tokens,
        reasoning_tokens=getattr(output_details, "reasoning_tokens", 0) or 0,
    )
