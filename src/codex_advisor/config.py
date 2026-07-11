from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

BUILTIN_PROVIDERS: dict[str, dict[str, str]] = {
    "codex": {
        "kind": "codex",
        "base_url": "",
        "api_key_env": "",
    },
    "openai": {
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
    "anthropic": {
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "kind": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "api_key_env": "GEMINI_API_KEY",
    },
}

DEFAULT_MODEL = "codex/gpt-5.6-sol"
DEFAULT_MAX_CONTEXT_CHARS = 400_000
DEFAULT_MAX_CONSULTS = 20
DEFAULT_REASONING = "medium"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))


def config_path() -> Path:
    return Path(os.environ.get("CODEX_ADVISOR_CONFIG", str(codex_home() / "advisor.toml")))


def env_file_path() -> Path:
    return Path(os.environ.get("CODEX_ADVISOR_ENV", str(codex_home() / "advisor.env")))


def sessions_root() -> Path:
    return Path(os.environ.get("CODEX_ADVISOR_SESSIONS", str(codex_home() / "sessions")))


@dataclass
class ProviderConfig:
    kind: str
    base_url: str
    api_key_env: str


@dataclass
class AdvisorConfig:
    enabled: bool = True
    model: str = DEFAULT_MODEL
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS
    max_consults_per_session: int = DEFAULT_MAX_CONSULTS
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    reasoning: str = DEFAULT_REASONING
    warnings: list[str] = field(default_factory=list)


def _coerce_int(raw: dict, key: str, default: int, warnings: list[str]) -> int:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        warnings.append(f"{key} must be an integer; using default {default}")
        return default
    return value


def _merged_providers(overrides: object) -> dict[str, ProviderConfig]:
    providers = {name: ProviderConfig(**spec) for name, spec in BUILTIN_PROVIDERS.items()}
    if not isinstance(overrides, dict):
        return providers
    for name, spec in overrides.items():
        if not isinstance(spec, dict):
            continue
        base = providers.get(name)
        providers[name] = ProviderConfig(
            kind=str(spec.get("kind", base.kind if base else "openai")),
            base_url=str(spec.get("base_url", base.base_url if base else "")),
            api_key_env=str(spec.get("api_key_env", base.api_key_env if base else "")),
        )
    return providers


def _coerce_reasoning(raw: dict, warnings: list[str]) -> str:
    # If key is absent, use DEFAULT_REASONING
    if "reasoning" not in raw:
        return DEFAULT_REASONING
    # If present, validate the value (allow explicit empty string)
    value = str(raw.get("reasoning", ""))
    if value not in ("", "low", "medium", "high"):
        warnings.append(f"reasoning must be one of low/medium/high; ignoring {value!r}")
        return DEFAULT_REASONING
    return value


def load_config() -> AdvisorConfig:
    path = config_path()
    raw: dict = {}
    warnings: list[str] = []
    if path.exists():
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as e:
            warnings.append(f"advisor.toml is broken; using defaults ({e})")
            raw = {}
    return AdvisorConfig(
        enabled=bool(raw.get("enabled", True)),
        model=str(raw.get("model", DEFAULT_MODEL)),
        max_context_chars=_coerce_int(
            raw, "max_context_chars", DEFAULT_MAX_CONTEXT_CHARS, warnings
        ),
        max_consults_per_session=_coerce_int(
            raw, "max_consults_per_session", DEFAULT_MAX_CONSULTS, warnings
        ),
        providers=_merged_providers(raw.get("providers", {})),
        reasoning=_coerce_reasoning(raw, warnings),
        warnings=warnings,
    )


def set_config_values(**updates: object) -> None:
    """advisor.toml の一部キーを、他のキーを保ったまま更新する。"""
    path = config_path()
    raw: dict = {}
    if path.exists():
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
            raw = {}
    raw.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(raw), encoding="utf-8")


def split_model(model: str) -> tuple[str, str]:
    provider, sep, name = model.partition("/")
    if not sep or not provider or not name:
        raise ValueError(f"model must be in '<provider>/<model>' form, got {model!r}")
    return provider, name


def load_env_file() -> None:
    """advisor.env の KEY=VALUE を、未設定の環境変数にだけ流し込む。"""
    path = env_file_path()
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
