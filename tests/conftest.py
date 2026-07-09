from pathlib import Path

import pytest


@pytest.fixture
def isolated_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """テストが実環境の ~/.codex を触らないよう全パスを tmp に向ける。"""
    monkeypatch.setenv("CODEX_ADVISOR_CONFIG", str(tmp_path / "advisor.toml"))
    monkeypatch.setenv("CODEX_ADVISOR_ENV", str(tmp_path / "advisor.env"))
    monkeypatch.setenv("CODEX_ADVISOR_SESSIONS", str(tmp_path / "sessions"))
    return tmp_path
