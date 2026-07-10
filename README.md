# codex-advisor

OpenAI Codex CLI に Claude Code の advisor 相当の「セカンドオピニオン」を追加する
個人用 MCP サーバー。advisor モデルに制限はない — GPT・Claude・Gemini、
および OpenAI 互換エンドポイントの任意モデルを指定できる。

## セットアップ

```bash
bash install.sh                # advisor.toml / advisor.env 作成 + MCP 登録 + AGENTS.md 誘導
vi ~/.codex/advisor.env        # 使うプロバイダの API キーを記入(chmod 600 済み)
```

## 使い方

- Codex が計画前・エラー反復時・完了宣言前に自動で `consult_advisor` を呼ぶ
- 手動相談: 「advisor に相談して」
- モデル切替: 「advisor を gemini/gemini-2.5-pro にして」(または `~/.codex/advisor.toml` の `model =` を編集)
- 無効化: 「advisor を off にして」または `advisor.toml` で `enabled = false`

## 設定 (~/.codex/advisor.toml)

```toml
enabled = true
model = "anthropic/claude-opus-4-8"   # "<provider>/<model>"。モデル名は無検証
max_context_chars = 400000            # advisor に渡す会話の上限(古い方から切り詰め)
max_consults_per_session = 20         # セッションあたり相談回数上限
reasoning = "high"        # 任意: low/medium/high。未設定はプロバイダ既定(Claude=思考なし, Gemini=動的思考)

# OpenAI 互換エンドポイントの追加例(OpenRouter / ollama など)
[providers.openrouter]
kind = "openai"
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"
```

## セキュリティ

API キーは `~/.codex/advisor.env` のみに置く。設定ファイル・会話・ツール結果・
エラーメッセージにキー値は一切出力されない。

## 開発

```bash
uv run pytest -q          # テスト
uv run ruff check src tests && uv run pyright   # lint+型
```
