from pathlib import Path

import pytest

from codex_advisor import config, server


def test_get_reports_current_settings(isolated_paths: Path) -> None:
    out = server.advisor_config("get")
    assert "anthropic/claude-opus-4-8" in out
    assert "enabled" in out


def test_get_shows_warnings_on_broken_config(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text("enabled = [broken", encoding="utf-8")
    out = server.advisor_config("get")
    assert out.startswith("[advisor warning]")


def test_set_changes_model_and_reenables(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text("enabled = false", encoding="utf-8")
    out = server.advisor_config("set", model="gemini/gemini-2.5-pro")
    assert "gemini/gemini-2.5-pro" in out
    cfg = config.load_config()
    assert cfg.model == "gemini/gemini-2.5-pro"
    assert cfg.enabled is True


def test_set_accepts_arbitrary_model_names(isolated_paths: Path) -> None:
    out = server.advisor_config("set", model="openrouter/meta-llama/llama-4-behemoth")
    assert "error" not in out
    assert config.load_config().model == "openrouter/meta-llama/llama-4-behemoth"


def test_set_rejects_model_without_slash(isolated_paths: Path) -> None:
    assert "error" in server.advisor_config("set", model="gpt-5.2")


def test_set_requires_model(isolated_paths: Path) -> None:
    assert "error" in server.advisor_config("set")


def test_off_disables(isolated_paths: Path) -> None:
    out = server.advisor_config("off")
    assert "disabled" in out
    assert config.load_config().enabled is False


def test_unknown_action(isolated_paths: Path) -> None:
    assert "error" in server.advisor_config("dance")


def test_set_reports_write_failure(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**updates: object) -> None:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(server.cfg_mod, "set_config_values", boom)
    out = server.advisor_config("set", model="openai/gpt-5.2")
    assert "error" in out
    assert "read-only filesystem" in out


def test_off_reports_write_failure(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**updates: object) -> None:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(server.cfg_mod, "set_config_values", boom)
    out = server.advisor_config("off")
    assert "error" in out
