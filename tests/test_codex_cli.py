from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from codex_advisor import codex_cli
from codex_advisor.errors import AdvisorError


def _successful_run(captured: dict[str, Any], advice: str = "use the smaller change") -> Any:
    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(command=command, **kwargs)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(advice, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="noisy transcript", stderr="")

    return fake_run


def test_call_builds_isolated_command_and_uses_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(codex_cli.subprocess, "run", _successful_run(captured))

    result = codex_cli.call_codex_advisor(
        "gpt-5.6-sol", "system role", "transcript needle", reasoning="high"
    )

    assert result == "use the smaller change"
    command = captured["command"]
    assert command[:5] == ["codex", "--ask-for-approval", "never", "exec", "--ignore-user-config"]
    for expected in (
        "--ignore-rules",
        "--strict-config",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--model",
        "gpt-5.6-sol",
        'forced_login_method="chatgpt"',
        'model_reasoning_effort="high"',
        "features.shell_tool=false",
        "features.apps=false",
        "features.plugins=false",
        "features.multi_agent=false",
        "features.goals=false",
        "features.browser_use=false",
        "features.computer_use=false",
        "features.image_generation=false",
        'web_search="disabled"',
        "--output-last-message",
        "-",
    ):
        assert expected in command
    assert "transcript needle" not in command
    assert captured["input"].startswith("# Advisor role\n\nsystem role")
    assert "# Untrusted advisor input" in captured["input"]
    assert "transcript needle" in captured["input"]
    assert captured["text"] is True
    assert captured["capture_output"] is True
    assert captured["check"] is False
    assert captured["timeout"] == codex_cli.CODEX_TIMEOUT_SECONDS
    temp_dir = Path(captured["cwd"])
    assert command[command.index("-C") + 1] == str(temp_dir)
    assert not temp_dir.exists()


def test_empty_reasoning_omits_override(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(codex_cli.subprocess, "run", _successful_run(captured))

    codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user", reasoning="")

    assert not any("model_reasoning_effort" in arg for arg in captured["command"])


def test_api_auth_forwards_only_selected_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-secret")
    monkeypatch.setenv("CUSTOM_CODEX_KEY", "codex-api-secret")
    monkeypatch.setenv("CODEX_API_KEY", "other-codex-secret")
    monkeypatch.setattr(codex_cli.subprocess, "run", _successful_run(captured))

    codex_cli.call_codex_advisor(
        "gpt-5.6-sol",
        "sys",
        "user",
        auth_method="api",
        api_key_env="CUSTOM_CODEX_KEY",
        credential_env_names={"CUSTOM_CODEX_KEY"},
    )

    command = captured["command"]
    assert 'forced_login_method="api"' in command
    child_env = captured["env"]
    assert child_env["CODEX_API_KEY"] == "codex-api-secret"
    assert "CUSTOM_CODEX_KEY" not in child_env
    assert "OPENAI_API_KEY" not in child_env
    assert "ambient-openai-secret" not in child_env.values()


def test_api_auth_can_use_codex_cli_stored_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai-secret")
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    captured: dict[str, Any] = {}
    monkeypatch.setattr(codex_cli.subprocess, "run", _successful_run(captured))

    codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user", auth_method="api")

    assert 'forced_login_method="api"' in captured["command"]
    assert "OPENAI_API_KEY" not in captured["env"]
    assert "CODEX_API_KEY" not in captured["env"]


def test_api_auth_explicit_key_env_must_be_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUSTOM_CODEX_KEY", raising=False)
    calls = 0

    def should_not_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("Codex CLI must not start without the explicit API key")

    monkeypatch.setattr(codex_cli.subprocess, "run", should_not_run)

    with pytest.raises(AdvisorError, match="CUSTOM_CODEX_KEY.*Codex API authentication"):
        codex_cli.call_codex_advisor(
            "gpt-5.6-sol",
            "sys",
            "user",
            auth_method="api",
            api_key_env="CUSTOM_CODEX_KEY",
        )
    assert calls == 0


def test_unknown_api_auth_method_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def should_not_run(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("Codex CLI must not start with an unknown auth method")

    monkeypatch.setattr(codex_cli.subprocess, "run", should_not_run)

    with pytest.raises(AdvisorError, match="unsupported Codex authentication method"):
        codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user", auth_method="automatic")
    assert calls == 0


def test_api_auth_error_redacts_selected_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 7, stdout="", stderr="invalid key codex-api-secret"
        )

    monkeypatch.setenv("OPENAI_API_KEY", "codex-api-secret")
    monkeypatch.setattr(codex_cli.subprocess, "run", fail)

    with pytest.raises(AdvisorError) as exc:
        codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user", auth_method="api")
    assert "codex-api-secret" not in str(exc.value)
    assert "***" in str(exc.value)
    assert "API key" in str(exc.value)


def test_child_environment_scrubs_credentials_without_mutating_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    secrets = {
        "OPENAI_API_KEY": "openai-secret",
        "CODEX_API_KEY": "codex-secret",
        "CODEX_ACCESS_TOKEN": "access-secret",
        "ANTHROPIC_API_KEY": "anthropic-secret",
        "CUSTOM_CREDENTIAL": "custom-secret",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("CODEX_HOME", "/tmp/codex-home-test")
    monkeypatch.setattr(codex_cli.subprocess, "run", _successful_run(captured))

    codex_cli.call_codex_advisor(
        "gpt-5.6-sol",
        "sys",
        "user",
        credential_env_names={"ANTHROPIC_API_KEY", "CUSTOM_CREDENTIAL"},
    )

    child_env = captured["env"]
    for name in secrets:
        assert name not in child_env
        assert os.environ[name] == secrets[name]
    assert child_env["HOME"] == os.environ["HOME"]
    assert child_env["PATH"] == os.environ["PATH"]
    assert child_env["CODEX_HOME"] == "/tmp/codex-home-test"
    assert child_env["CODEX_ADVISOR_CHILD"] == "1"


def test_nonzero_exit_redacts_stderr_and_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(
            command,
            7,
            stdout=kwargs["input"],
            stderr="auth failed: secret-value " + "x" * 700,
        )

    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)

    with pytest.raises(AdvisorError) as exc:
        codex_cli.call_codex_advisor("gpt-bad", "sys", "user")

    message = str(exc.value)
    assert calls == 1
    assert "exit 7" in message
    assert "secret-value" not in message
    assert "***" in message
    assert "user" not in message
    assert len(message) < 600


def test_timeout_is_reported_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)

    with pytest.raises(AdvisorError, match="timed out after 300 seconds"):
        codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user")
    assert calls == 1


@pytest.mark.parametrize("mode", ["missing", "empty", "whitespace"])
def test_missing_or_empty_output_is_reported(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        output_path = Path(command[command.index("--output-last-message") + 1])
        if mode == "empty":
            output_path.write_text("", encoding="utf-8")
        elif mode == "whitespace":
            output_path.write_text("  \n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(codex_cli.subprocess, "run", fake_run)

    with pytest.raises(AdvisorError, match="empty advice"):
        codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user")


def test_missing_binary_and_os_error_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("codex")

    monkeypatch.setattr(codex_cli.subprocess, "run", missing)
    with pytest.raises(AdvisorError, match="Codex CLI was not found"):
        codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user")

    def broken(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise OSError("cannot spawn")

    monkeypatch.setattr(codex_cli.subprocess, "run", broken)
    with pytest.raises(AdvisorError, match="failed to start Codex CLI"):
        codex_cli.call_codex_advisor("gpt-5.6-sol", "sys", "user")
