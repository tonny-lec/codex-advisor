import os
import subprocess
from pathlib import Path

from codex_advisor import config

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_installer_default_model_matches_runtime_default() -> None:
    installer = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    assert f'model = "{config.DEFAULT_MODEL}"' in installer


def test_readme_documents_both_openai_billing_routes() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert 'model = "codex/gpt-5.6-sol"' in readme
    assert 'model = "openai/<Chat Completions 対応モデル ID>"' in readme
    assert "自動フォールバックしない" in readme


def _isolated_installer_env(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        '[mcp_servers.advisor]\ncommand = "uv"\n', encoding="utf-8"
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_codex = fake_bin / "codex"
    fake_codex.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    fake_codex.chmod(0o755)
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    return codex_home, env


def test_installer_is_idempotent_in_isolated_codex_home(tmp_path: Path) -> None:
    codex_home, env = _isolated_installer_env(tmp_path)

    first = subprocess.run(
        ["bash", "install.sh"], cwd=REPO_ROOT, env=env, text=True, capture_output=True
    )
    assert first.returncode == 0, first.stderr
    advisor_toml = (codex_home / "advisor.toml").read_text(encoding="utf-8")
    agents = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
    assert 'model = "codex/gpt-5.6-sol"' in advisor_toml
    assert agents.count("<!-- codex-advisor:start -->") == 1
    assert (codex_home / "advisor.env").stat().st_mode & 0o777 == 0o600
    assert 'default_tools_approval_mode = "approve"' in (
        codex_home / "config.toml"
    ).read_text(encoding="utf-8")

    second = subprocess.run(
        ["bash", "install.sh"], cwd=REPO_ROOT, env=env, text=True, capture_output=True
    )
    assert second.returncode == 0, second.stderr
    assert (codex_home / "advisor.toml").read_text(encoding="utf-8") == advisor_toml
    assert (codex_home / "AGENTS.md").read_text(encoding="utf-8") == agents


def test_installer_preserves_existing_advisor_config(tmp_path: Path) -> None:
    codex_home, env = _isolated_installer_env(tmp_path)
    existing = 'enabled = true\nmodel = "openai/gpt-5.2"\n'
    (codex_home / "advisor.toml").write_text(existing, encoding="utf-8")

    result = subprocess.run(
        ["bash", "install.sh"], cwd=REPO_ROOT, env=env, text=True, capture_output=True
    )

    assert result.returncode == 0, result.stderr
    assert (codex_home / "advisor.toml").read_text(encoding="utf-8") == existing


def test_installer_checks_approval_mode_only_in_advisor_section(tmp_path: Path) -> None:
    codex_home, env = _isolated_installer_env(tmp_path)
    (codex_home / "config.toml").write_text(
        '[apps._default]\ndefault_tools_approval_mode = "prompt"\n\n'
        '[mcp_servers.advisor]\ncommand = "uv"\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "install.sh"], cwd=REPO_ROOT, env=env, text=True, capture_output=True
    )

    assert result.returncode == 0, result.stderr
    advisor_section = (codex_home / "config.toml").read_text(encoding="utf-8").split(
        "[mcp_servers.advisor]", maxsplit=1
    )[1]
    assert 'default_tools_approval_mode = "approve"' in advisor_section
