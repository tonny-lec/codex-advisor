from pathlib import Path
from typing import Any

import pytest

from codex_advisor import server
from codex_advisor.providers import AdvisorError


@pytest.fixture(autouse=True)
def reset_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "_consult_count", 0)


@pytest.fixture
def fake_advisor(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    def fake(provider: Any, model: str, system_prompt: str, user_content: str, **kw: Any) -> str:
        calls.update(provider=provider, model=model, system=system_prompt, user=user_content)
        calls["reasoning"] = kw.get("reasoning", "")
        calls["credential_env_names"] = kw.get("credential_env_names", set())
        return "do X first"

    monkeypatch.setattr(server.providers, "call_advisor", fake)
    return calls


def _write_rollout(tmp_path: Path) -> None:
    d = tmp_path / "sessions" / "2026" / "07" / "10"
    d.mkdir(parents=True)
    (d / "rollout-x.jsonl").write_text(
        '{"type":"response_item","payload":{"type":"message","role":"user",'
        '"content":[{"type":"input_text","text":"hello world"}]}}\n',
        encoding="utf-8",
    )


def test_consult_success_attaches_transcript(
    isolated_paths: Path, fake_advisor: dict[str, Any]
) -> None:
    _write_rollout(isolated_paths)
    result = server.consult_advisor("plan ok?", context_hint="src/x.py")
    assert "do X first" in result
    assert "[advice from codex/gpt-5.6-sol]" in result
    assert "hello world" in fake_advisor["user"]
    assert "plan ok?" in fake_advisor["user"]
    assert "src/x.py" in fake_advisor["user"]
    assert fake_advisor["model"] == "gpt-5.6-sol"
    assert "advisor" in fake_advisor["system"].lower()  # advisor_prompt.md が使われる
    assert "untrusted evidence" in fake_advisor["system"]
    assert fake_advisor["credential_env_names"] == {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
    }


def test_consult_passes_reasoning_setting(
    isolated_paths: Path, fake_advisor: dict[str, Any]
) -> None:
    (isolated_paths / "advisor.toml").write_text('reasoning = "high"\n', encoding="utf-8")
    _write_rollout(isolated_paths)
    server.consult_advisor("plan ok?")
    assert fake_advisor["reasoning"] == "high"


def test_consult_passes_custom_provider_credentials(
    isolated_paths: Path, fake_advisor: dict[str, Any]
) -> None:
    (isolated_paths / "advisor.toml").write_text(
        'model = "codex/gpt-5.6-sol"\n'
        '[providers.custom]\n'
        'kind = "openai"\n'
        'base_url = "https://example.test/v1"\n'
        'api_key_env = "CUSTOM_PROVIDER_KEY"\n',
        encoding="utf-8",
    )

    server.consult_advisor("q")

    assert "CUSTOM_PROVIDER_KEY" in fake_advisor["credential_env_names"]


def test_recursive_child_call_returns_before_loading_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_ADVISOR_CHILD", "1")

    def should_not_run() -> None:
        raise AssertionError("config must not be loaded")

    monkeypatch.setattr(server.cfg_mod, "load_config", should_not_run)

    result = server.consult_advisor("q")

    assert result == "advisor unavailable: recursive child consultation was blocked"
    assert server._consult_count == 0


def test_consult_reloads_model_between_calls(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models: list[str] = []

    def fake(provider: Any, model: str, *args: Any, **kwargs: Any) -> str:
        models.append(model)
        return "ok"

    monkeypatch.setattr(server.providers, "call_advisor", fake)
    config_path = isolated_paths / "advisor.toml"
    config_path.write_text('model = "codex/gpt-5.6-sol"\n', encoding="utf-8")
    server.consult_advisor("first")
    config_path.write_text('model = "openai/gpt-5.2"\n', encoding="utf-8")
    server.consult_advisor("second")

    assert models == ["gpt-5.6-sol", "gpt-5.2"]


def test_consult_disabled(isolated_paths: Path, fake_advisor: dict[str, Any]) -> None:
    (isolated_paths / "advisor.toml").write_text("enabled = false", encoding="utf-8")
    assert "disabled" in server.consult_advisor("q")


def test_consult_limit(isolated_paths: Path, fake_advisor: dict[str, Any]) -> None:
    (isolated_paths / "advisor.toml").write_text("max_consults_per_session = 1", encoding="utf-8")
    _write_rollout(isolated_paths)
    server.consult_advisor("q1")
    assert "limit" in server.consult_advisor("q2")


def test_consult_unknown_provider(isolated_paths: Path, fake_advisor: dict[str, Any]) -> None:
    (isolated_paths / "advisor.toml").write_text('model = "nope/some-model"', encoding="utf-8")
    result = server.consult_advisor("q")
    assert "unknown provider" in result
    assert "providers.nope" in result


def test_consult_without_rollout_still_answers(
    isolated_paths: Path, fake_advisor: dict[str, Any]
) -> None:
    result = server.consult_advisor("q")
    assert "do X first" in result
    assert "no session transcript" in result


def test_consult_api_error_reported_not_raised(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_rollout(isolated_paths)

    def boom(*a: Any, **kw: Any) -> str:
        raise AdvisorError("HTTP 500 from openai: oops")

    monkeypatch.setattr(server.providers, "call_advisor", boom)
    result = server.consult_advisor("q")
    assert "advisor unavailable" in result
    assert "HTTP 500" in result


def test_warning_prefix_on_broken_config(
    isolated_paths: Path, fake_advisor: dict[str, Any]
) -> None:
    (isolated_paths / "advisor.toml").write_text("enabled = [broken", encoding="utf-8")
    _write_rollout(isolated_paths)
    assert server.consult_advisor("q").startswith("[advisor warning]")


def test_consult_survives_unreadable_rollout_file(
    isolated_paths: Path, fake_advisor: dict[str, Any]
) -> None:
    d = isolated_paths / "sessions" / "2026" / "07" / "10"
    d.mkdir(parents=True)
    (d / "rollout-x.jsonl").write_bytes(b"\xff\xfe broken")
    result = server.consult_advisor("q")
    assert "do X first" in result  # 相談自体は成立する(question のみ)
    assert "no session transcript" in result


def test_consult_survives_unexpected_provider_error(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a: Any, **kw: Any) -> str:
        raise RuntimeError("totally unexpected")

    monkeypatch.setattr(server.providers, "call_advisor", boom)
    result = server.consult_advisor("q")
    assert "advisor unavailable" in result


def test_consult_survives_find_latest_rollout_error(
    isolated_paths: Path, fake_advisor: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(root: Path) -> Path | None:
        raise OSError("stat race")

    monkeypatch.setattr(server.rollout, "find_latest_rollout", boom)
    result = server.consult_advisor("q")
    assert "do X first" in result
    assert "no session transcript" in result


def test_consult_reports_prompt_load_failure(
    isolated_paths: Path, fake_advisor: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> str:
        raise FileNotFoundError("advisor_prompt.md missing")

    monkeypatch.setattr(server, "_system_prompt", boom)
    result = server.consult_advisor("q")
    assert "advisor unavailable" in result
