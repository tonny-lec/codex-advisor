from __future__ import annotations

import json
from pathlib import Path

TRUNCATION_MARKER = "(古い履歴は省略)"


def find_latest_rollout(root: Path) -> Path | None:
    """sessions ルート配下で最終更新が最新の rollout ファイル = 現在セッションとみなす。"""
    candidates = list(root.glob("*/*/*/rollout-*.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _text_from_content(content: object) -> str:
    if not isinstance(content, list):
        return ""
    parts = [
        c.get("text", "")
        for c in content
        if isinstance(c, dict) and c.get("type") in ("input_text", "output_text")
    ]
    return "\n".join(p for p in parts if p)


def build_transcript(path: Path, max_chars: int) -> str:
    blocks: list[str] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict) or item.get("type") != "response_item":
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            kind = payload.get("type")
            if kind == "message":
                role = payload.get("role")
                if role not in ("user", "assistant"):
                    continue  # developer(権限説明等)は除外
                text = _text_from_content(payload.get("content"))
                if text:
                    blocks.append(f"[{role}]\n{text}")
            elif kind == "function_call":
                blocks.append(
                    f"[tool call] {payload.get('name', '?')}({payload.get('arguments', '')})"
                )
            elif kind == "custom_tool_call":
                blocks.append(f"[tool call] {payload.get('name', '?')}\n{payload.get('input', '')}")
            elif kind in ("function_call_output", "custom_tool_call_output"):
                blocks.append(f"[tool result]\n{payload.get('output', '')}")
            # reasoning(暗号化済み)ほかは無視
    transcript = "\n\n".join(blocks)
    if len(transcript) > max_chars:
        transcript = TRUNCATION_MARKER + "\n" + transcript[-max_chars:]
    return transcript
