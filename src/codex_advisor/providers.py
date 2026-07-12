from __future__ import annotations

import os
import time
from collections.abc import Collection
from typing import Any, Callable

import httpx

from codex_advisor import codex_cli
from codex_advisor.config import ProviderConfig
from codex_advisor.errors import AdvisorError

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRY_WAIT_SECONDS = 1.0
REASONING_BUDGET_TOKENS = {"low": 2048, "medium": 8192, "high": 16384}


def _redact(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


def _openai_request(
    p: ProviderConfig, model: str, key: str, system: str, user: str, reasoning: str
) -> httpx.Request:
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if reasoning:
        body["reasoning_effort"] = reasoning
    return httpx.Request(
        "POST",
        f"{p.base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=body,
    )


def _openai_parse(data: Any) -> str:
    return data["choices"][0]["message"]["content"]


def _anthropic_request(
    p: ProviderConfig, model: str, key: str, system: str, user: str, reasoning: str
) -> httpx.Request:
    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 8192,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if reasoning:
        # enabled+budget_tokens は claude-fable-5 / Opus 4.7+ で 400。
        # adaptive + output_config.effort は 4.6 以降の全系統で有効。
        body["thinking"] = {"type": "adaptive"}
        body["output_config"] = {"effort": reasoning}
    return httpx.Request(
        "POST",
        f"{p.base_url.rstrip('/')}/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        json=body,
    )


def _anthropic_parse(data: Any) -> str:
    return "\n".join(
        block["text"] for block in data["content"] if block.get("type") == "text"
    )


def _gemini_request(
    p: ProviderConfig, model: str, key: str, system: str, user: str, reasoning: str
) -> httpx.Request:
    body: dict[str, Any] = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
    }
    if reasoning:
        budget = REASONING_BUDGET_TOKENS[reasoning]
        body["generationConfig"] = {"thinkingConfig": {"thinkingBudget": budget}}
    return httpx.Request(
        "POST",
        f"{p.base_url.rstrip('/')}/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key},
        json=body,
    )


def _gemini_parse(data: Any) -> str:
    return "\n".join(
        part["text"] for part in data["candidates"][0]["content"]["parts"] if "text" in part
    )


_BUILDERS: dict[str, Callable[[ProviderConfig, str, str, str, str, str], httpx.Request]] = {
    "openai": _openai_request,
    "anthropic": _anthropic_request,
    "gemini": _gemini_request,
}
_PARSERS: dict[str, Callable[[Any], str]] = {
    "openai": _openai_parse,
    "anthropic": _anthropic_parse,
    "gemini": _gemini_parse,
}


def call_advisor(
    provider: ProviderConfig,
    model: str,
    system_prompt: str,
    user_content: str,
    *,
    timeout: float = 120.0,
    reasoning: str = "",
    credential_env_names: Collection[str] = (),
) -> str:
    if reasoning == "xhigh" and provider.kind not in {"codex", "openai"}:
        raise AdvisorError(
            "reasoning 'xhigh' is supported only by codex and openai providers"
        )
    if provider.kind == "codex":
        return codex_cli.call_codex_advisor(
            model,
            system_prompt,
            user_content,
            reasoning=reasoning,
            credential_env_names=credential_env_names,
            auth_method=provider.auth_method or "chatgpt",
            api_key_env=provider.api_key_env,
        )
    api_key = os.environ.get(provider.api_key_env, "")
    if not api_key:
        raise AdvisorError(
            f"environment variable {provider.api_key_env} is not set; "
            "add it to ~/.codex/advisor.env"
        )
    if provider.kind not in _BUILDERS:
        raise AdvisorError(
            f"unknown provider kind {provider.kind!r} (expected openai/anthropic/gemini)"
        )
    try:
        request = _BUILDERS[provider.kind](
            provider, model, api_key, system_prompt, user_content, reasoning
        )
    except Exception as e:
        raise AdvisorError(f"invalid provider request: {_redact(str(e), api_key)}") from e
    last_error = ""
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.send(request)
        except httpx.HTTPError as e:
            last_error = _redact(str(e), api_key)
            continue
        if response.status_code in RETRYABLE_STATUS and attempt == 0:
            last_error = f"HTTP {response.status_code}"
            time.sleep(RETRY_WAIT_SECONDS)
            continue
        if response.status_code != 200:
            body = _redact(response.text, api_key)[:500]
            raise AdvisorError(f"HTTP {response.status_code} from {provider.kind}: {body}")
        try:
            return _PARSERS[provider.kind](response.json())
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise AdvisorError(f"unexpected {provider.kind} response shape: {e}") from e
    raise AdvisorError(f"request to {provider.kind} failed after retry: {last_error}")
