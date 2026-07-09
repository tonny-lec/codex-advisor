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
    assert "[advice from anthropic/claude-opus-4-8]" in result
    assert "hello world" in fake_advisor["user"]
    assert "plan ok?" in fake_advisor["user"]
    assert "src/x.py" in fake_advisor["user"]
    assert fake_advisor["model"] == "claude-opus-4-8"
    assert "advisor" in fake_advisor["system"].lower()  # advisor_prompt.md が使われる


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
