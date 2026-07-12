import os
from pathlib import Path

import pytest

from codex_advisor import config


def test_defaults_when_no_file(isolated_paths: Path) -> None:
    cfg = config.load_config()
    assert cfg.enabled is True
    assert cfg.model == "codex/gpt-5.6-sol"
    assert cfg.max_context_chars == 400_000
    assert cfg.max_consults_per_session == 20
    assert set(cfg.providers) == {"codex", "openai", "anthropic", "gemini"}
    assert cfg.providers["codex"] == config.ProviderConfig(
        kind="codex", base_url="", api_key_env="", auth_method="chatgpt"
    )
    assert cfg.providers["anthropic"].api_key_env == "ANTHROPIC_API_KEY"
    assert cfg.reasoning == "medium"
    assert cfg.warnings == []


def test_reasoning_defaults_to_medium(isolated_paths: Path) -> None:
    cfg = config.load_config()
    assert cfg.reasoning == "medium"


def test_reasoning_loads_valid_value(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text('reasoning = "high"\n', encoding="utf-8")
    cfg = config.load_config()
    assert cfg.reasoning == "high"


def test_reasoning_loads_xhigh(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text('reasoning = "xhigh"\n', encoding="utf-8")
    cfg = config.load_config()
    assert cfg.reasoning == "xhigh"
    assert cfg.warnings == []


def test_reasoning_invalid_value_falls_back(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text('reasoning = "ultra"\n', encoding="utf-8")
    cfg = config.load_config()
    assert cfg.reasoning == "medium"
    assert any("reasoning" in w for w in cfg.warnings)


def test_reasoning_explicit_empty_string_preserved(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text('reasoning = ""\n', encoding="utf-8")
    cfg = config.load_config()
    assert cfg.reasoning == ""
    assert cfg.warnings == []


def test_load_values_and_provider_override(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text(
        'enabled = false\n'
        'model = "openai/gpt-5.2"\n'
        'max_context_chars = 1000\n'
        '[providers.openrouter]\n'
        'kind = "openai"\n'
        'base_url = "https://openrouter.ai/api/v1"\n'
        'api_key_env = "OPENROUTER_API_KEY"\n',
        encoding="utf-8",
    )
    cfg = config.load_config()
    assert cfg.enabled is False
    assert cfg.model == "openai/gpt-5.2"
    assert cfg.max_context_chars == 1000
    assert cfg.providers["openrouter"].base_url == "https://openrouter.ai/api/v1"
    assert cfg.providers["openai"].kind == "openai"  # 組み込みは残る


def test_codex_api_authentication_settings_load(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text(
        '[providers.codex]\n'
        'auth_method = "api"\n'
        'api_key_env = "CUSTOM_CODEX_KEY"\n',
        encoding="utf-8",
    )

    cfg = config.load_config()

    assert cfg.providers["codex"].auth_method == "api"
    assert cfg.providers["codex"].api_key_env == "CUSTOM_CODEX_KEY"
    assert cfg.warnings == []


def test_invalid_codex_authentication_method_fails_closed(
    isolated_paths: Path,
) -> None:
    (isolated_paths / "advisor.toml").write_text(
        '[providers.codex]\nauth_method = "automatic"\n', encoding="utf-8"
    )

    cfg = config.load_config()

    assert cfg.providers["codex"].auth_method == "automatic"
    assert any("providers.codex.auth_method" in warning for warning in cfg.warnings)


def test_broken_toml_falls_back_to_defaults(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text("enabled = [broken", encoding="utf-8")
    cfg = config.load_config()
    assert cfg.enabled is True
    assert cfg.model == "codex/gpt-5.6-sol"
    assert cfg.warnings


def test_non_utf8_file_falls_back_to_defaults(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_bytes(b"\xff\xfe\x00broken")
    cfg = config.load_config()
    assert cfg.enabled is True
    assert cfg.model == "codex/gpt-5.6-sol"
    assert cfg.warnings


def test_non_integer_value_falls_back(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text('max_context_chars = "abc"', encoding="utf-8")
    cfg = config.load_config()
    assert cfg.max_context_chars == 400_000
    assert any("max_context_chars" in w for w in cfg.warnings)


def test_split_model() -> None:
    assert config.split_model("openai/gpt-5.2") == ("openai", "gpt-5.2")
    assert config.split_model("codex/gpt-5.6-sol") == ("codex", "gpt-5.6-sol")
    # モデル名側の追加スラッシュは許容(モデル名は検証しない)
    assert config.split_model("openrouter/meta-llama/llama-4") == ("openrouter", "meta-llama/llama-4")


def test_split_model_rejects_missing_slash() -> None:
    with pytest.raises(ValueError):
        config.split_model("gpt-5.2")


def test_set_config_values_preserves_other_keys(isolated_paths: Path) -> None:
    (isolated_paths / "advisor.toml").write_text(
        'model = "openai/gpt-5.2"\nmax_context_chars = 1000\n', encoding="utf-8"
    )
    config.set_config_values(enabled=False)
    cfg = config.load_config()
    assert cfg.enabled is False
    assert cfg.model == "openai/gpt-5.2"
    assert cfg.max_context_chars == 1000


def test_load_env_file_sets_missing_vars_only(
    isolated_paths: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADVISOR_TEST_KEY", raising=False)
    monkeypatch.setenv("ADVISOR_KEEP", "original")
    (isolated_paths / "advisor.env").write_text(
        '# comment line\nADVISOR_TEST_KEY="sk-test"\nADVISOR_KEEP=overwritten\n\n',
        encoding="utf-8",
    )
    config.load_env_file()
    assert os.environ["ADVISOR_TEST_KEY"] == "sk-test"
    assert os.environ["ADVISOR_KEEP"] == "original"
