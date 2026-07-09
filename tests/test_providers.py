import json

import httpx
import pytest
import respx

from codex_advisor.config import ProviderConfig
from codex_advisor.providers import AdvisorError, call_advisor

OPENAI = ProviderConfig(
    kind="openai", base_url="https://api.openai.com/v1", api_key_env="TEST_OPENAI_KEY"
)
ANTHROPIC = ProviderConfig(
    kind="anthropic", base_url="https://api.anthropic.com", api_key_env="TEST_ANTHROPIC_KEY"
)
GEMINI = ProviderConfig(
    kind="gemini",
    base_url="https://generativelanguage.googleapis.com",
    api_key_env="TEST_GEMINI_KEY",
)


@pytest.fixture(autouse=True)
def keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-openai-secret")
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "sk-ant-secret")
    monkeypatch.setenv("TEST_GEMINI_KEY", "sk-gem-secret")


@respx.mock
def test_openai_adapter() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": "advice!"}}]}
        )
    )
    assert call_advisor(OPENAI, "gpt-5.2", "sys", "user") == "advice!"
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer sk-openai-secret"
    body = json.loads(request.content)
    assert body["model"] == "gpt-5.2"
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][1] == {"role": "user", "content": "user"}


@respx.mock
def test_anthropic_adapter() -> None:
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200, json={"content": [{"type": "text", "text": "advice!"}]}
        )
    )
    assert call_advisor(ANTHROPIC, "claude-opus-4-8", "sys", "user") == "advice!"
    request = route.calls.last.request
    assert request.headers["x-api-key"] == "sk-ant-secret"
    body = json.loads(request.content)
    assert body["system"] == "sys"
    assert body["messages"] == [{"role": "user", "content": "user"}]


@respx.mock
def test_gemini_adapter() -> None:
    respx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"
    ).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "advice!"}]}}]}
        )
    )
    assert call_advisor(GEMINI, "gemini-2.5-pro", "sys", "user") == "advice!"


def test_missing_key_names_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_OPENAI_KEY")
    with pytest.raises(AdvisorError) as exc:
        call_advisor(OPENAI, "gpt-5.2", "sys", "user")
    assert "TEST_OPENAI_KEY" in str(exc.value)


def test_unknown_kind() -> None:
    bad = ProviderConfig(kind="mystery", base_url="https://x", api_key_env="TEST_OPENAI_KEY")
    with pytest.raises(AdvisorError):
        call_advisor(bad, "m", "sys", "user")


@respx.mock
def test_retries_once_on_5xx() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]}),
        ]
    )
    assert call_advisor(OPENAI, "gpt-5.2", "sys", "user") == "ok"
    assert route.call_count == 2


@respx.mock
def test_non_retryable_error_raises_with_redacted_body() -> None:
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(400, text="bad request: key sk-openai-secret invalid")
    )
    with pytest.raises(AdvisorError) as exc:
        call_advisor(OPENAI, "gpt-5.2", "sys", "user")
    assert "sk-openai-secret" not in str(exc.value)
    assert "400" in str(exc.value)


@respx.mock
def test_redaction_happens_before_truncation() -> None:
    # キーが500文字境界をまたいでも断片が漏れない
    text = "x" * 492 + "sk-openai-secret" + "y" * 100
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(400, text=text)
    )
    with pytest.raises(AdvisorError) as exc:
        call_advisor(OPENAI, "gpt-5.2", "sys", "user")
    assert "sk-o" not in str(exc.value)


def test_invalid_base_url_raises_advisor_error() -> None:
    bad = ProviderConfig(kind="openai", base_url="https://x:abc", api_key_env="TEST_OPENAI_KEY")
    with pytest.raises(AdvisorError) as exc:
        call_advisor(bad, "gpt-5.2", "sys", "user")
    assert "sk-openai-secret" not in str(exc.value)


@respx.mock
def test_transport_error_is_retried_and_redacted() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        side_effect=[
            httpx.ConnectError("connect failed (auth sk-openai-secret)"),
            httpx.ConnectError("connect failed (auth sk-openai-secret)"),
        ]
    )
    with pytest.raises(AdvisorError) as exc:
        call_advisor(OPENAI, "gpt-5.2", "sys", "user")
    assert route.call_count == 2
    assert "sk-openai-secret" not in str(exc.value)
