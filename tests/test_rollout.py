import os
import shutil
import time
from pathlib import Path

from codex_advisor import rollout

FIXTURE = Path(__file__).parent / "fixtures" / "rollout_sample.jsonl"


def _day_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sessions" / "2026" / "07" / "10"
    d.mkdir(parents=True)
    return d


def test_find_latest_rollout_picks_newest_mtime(tmp_path: Path) -> None:
    d = _day_dir(tmp_path)
    old = d / "rollout-old.jsonl"
    new = d / "rollout-new.jsonl"
    shutil.copy(FIXTURE, old)
    shutil.copy(FIXTURE, new)
    past = time.time() - 100
    os.utime(old, (past, past))
    assert rollout.find_latest_rollout(tmp_path / "sessions") == new


def test_find_latest_rollout_none_when_missing(tmp_path: Path) -> None:
    assert rollout.find_latest_rollout(tmp_path / "sessions") is None


def test_build_transcript_contents() -> None:
    text = rollout.build_transcript(FIXTURE, max_chars=100_000)
    assert "[user]\nREADME を作って" in text
    assert "[assistant]\nREADME.md を作成しました" in text
    assert '[tool call] exec_command({"cmd": "ls"})' in text
    assert "[tool call] apply_patch" in text
    assert "[tool result]" in text
    # 除外対象が混入していないこと
    assert "AAAA" not in text  # reasoning(暗号化)
    assert "permissions instructions" not in text  # developer ロール
    assert "token_count" not in text  # event_msg


def test_build_transcript_truncates_at_block_boundary() -> None:
    text = rollout.build_transcript(FIXTURE, max_chars=60)
    assert text.startswith("(古い履歴は省略)")
    body = text.removeprefix("(古い履歴は省略)\n")
    assert body.startswith("[")  # ブロック先頭から始まる(途中で切れない)
    assert "[assistant]\nREADME.md を作成しました" in body
    assert "README を作って" not in text


def test_build_transcript_single_oversized_block_falls_back() -> None:
    # 最新ブロック単体が上限超過でも全損させず末尾を残す
    text = rollout.build_transcript(FIXTURE, max_chars=5)
    assert text.startswith("(古い履歴は省略)\n")
    assert len(text) <= len("(古い履歴は省略)\n") + 5
