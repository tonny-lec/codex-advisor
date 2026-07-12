# codex-advisor

OpenAI Codex CLI に Claude Code の advisor 相当の「セカンドオピニオン」を追加する
個人用 MCP サーバー。既定では、ChatGPT でログイン済みの Codex CLI を介して
GPT をサブスクリプション利用する。OpenAI API・Claude・Gemini、および OpenAI
互換エンドポイントの任意モデルにも切り替えられる。

## 公開範囲と利用条件

このリポジトリは公開準備中の実験的な個人用ツールです。公開しても、現時点で
マルチユーザー対応、互換性の保証、運用サポート SLA は提供しません。

この個人開発ではライセンスを付与しません。リポジトリが公開されていることだけを
根拠に、利用・改変・再配布の許可があるとは解釈しないでください。

## セットアップ

前提: Python 3.12以上、uv、Codex CLI 0.144.1以上。`codex/` providerには
ChatGPTログインが必要。

```bash
bash install.sh                # advisor.toml / advisor.env 作成 + MCP 登録 + AGENTS.md 誘導
codex login status             # codex/ 利用時は Logged in using ChatGPT を確認
vi ~/.codex/advisor.env        # API provider も使う場合だけ API キーを記入
```

`install.sh` は既存の `advisor.toml` を上書きしない。旧版から移行する場合は、
下記の `model` を手動で変更する。

## 使い方

- Codex が計画前・エラー反復時・完了宣言前に自動で `consult_advisor` を呼ぶ
- 手動相談: 「advisor に相談して」
- サブスクリプションGPT: `model = "codex/gpt-5.6-sol"`
- OpenAI API: `model = "openai/<Chat Completions 対応モデル ID>"`
- モデル切替: 「advisor を codex/gpt-5.6-sol にして」(または `~/.codex/advisor.toml` の `model =` を編集)
- 無効化: 「advisor を off にして」または `advisor.toml` で `enabled = false`

`codex/` と `openai/` は同居できる。前者はChatGPTサブスクリプション、後者は
`OPENAI_API_KEY` のAPI従量課金である。1回の相談では `model` が示す一方だけを使い、
`codex/` 失敗時に `openai/` へ自動フォールバックしない。

## 設定 (~/.codex/advisor.toml)

```toml
enabled = true
model = "codex/gpt-5.6-sol"            # "<provider>/<model>"。モデル名は無検証
max_context_chars = 400000            # advisor に渡す会話の上限(古い方から切り詰め)
max_consults_per_session = 20         # セッションあたり相談回数上限
reasoning = "medium"      # 任意: low/medium/high/xhigh。デフォルトは medium。reasoning = "" でプロバイダ既定に戻せる

# OpenAI 互換エンドポイントの追加例(OpenRouter / ollama など)
[providers.openrouter]
kind = "openai"
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"
```

`advisor.toml` は相談ごとに読み直すため、モデル切替にMCP再起動は不要。
`advisor.env` はMCP起動時にだけ読むため、APIキーの追加・変更後はCodexセッションを
再起動する。

`xhigh` は `codex/` と `openai/` providerで利用できる。選択モデルが非対応の場合は
下流のCodex CLIまたはAPIがエラーを返し、値を自動変更しない。Anthropic/Geminiでは
意味の異なる値へ推測変換せず、相談実行前に明示的な非対応エラーを返す。

## セキュリティ

API キーは `~/.codex/advisor.env` のみに置く。`codex/` の子プロセスには、
組み込み・カスタムproviderを含むadvisor用credentialを渡さない。子Codexは
一時directory、read-only sandbox、ephemeral sessionで実行し、shell・Web・MCP・
app・subagent等を無効化する。APIエラーに含まれる選択providerのキー値は伏せ字化する。

advisorには現在セッションの会話・ツール呼び出し・結果が送られる。`codex/` では
ログイン中のChatGPT workspace、API providerでは各APIアカウントのデータ処理条件が
適用される。transcript自体に秘密情報を含めないこと。

このツールには transcript 全体を対象にした秘密情報スキャナはありません。秘密情報、
個人情報、社内情報を含むセッションで `consult_advisor` を使わないでください。

## 開発

```bash
uv run pytest -q          # テスト
uv run ruff check src tests && uv run pyright   # lint+型
```
