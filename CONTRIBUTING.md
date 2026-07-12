# Contributing

このプロジェクトは実験的な個人用ツールです。Issue や Pull Request を送る場合は、
変更の目的と検証結果を短く説明してください。外部からの貢献に対するサポート SLA、
互換性保証、採用の約束はありません。

## セキュリティとデータ

- 実際の API キー、認証情報、個人情報、社内情報、Codex の実 transcript をコミット・
  Issue・Pull Request に含めないでください。
- fixture と再現手順には合成データを使ってください。
- 脆弱性は public issue に投稿せず、[SECURITY.md](SECURITY.md) の手順に従ってください。

## 開発環境と検証

Python 3.12 以上と uv を使います。

```bash
uv sync --locked
uv run pytest -q
uv run ruff check src tests
uv run pyright
bash -n install.sh
```

install script を変更した場合は、ShellCheck も実行してください。

```bash
uv run --with shellcheck-py shellcheck install.sh
```

## 変更方針

- 受け入れ条件を満たす最小の変更にしてください。
- セキュリティ境界、credential の扱い、transcript の送信範囲を変更する場合は、
  回帰テストと README/SECURITY.md の説明を同時に更新してください。
- `uv.lock` は `pyproject.toml` と同期した状態を保ってください。
- ローカルの `~/.codex`、`.env`、`.superpowers`、生成物をコミットしないでください。
