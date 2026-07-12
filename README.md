# codex-advisor

OpenAI Codex CLI に Claude Code の advisor 相当の「セカンドオピニオン」を追加する
個人用 MCP サーバー。既定では、ChatGPT でログイン済みの Codex CLI を介して
GPT を利用する。Codex CLI の ChatGPT認証またはAPIキー認証、OpenAI API・Claude・Gemini、および OpenAI
互換エンドポイントの任意モデルにも切り替えられる。

## 公開範囲と利用条件

このリポジトリは公開準備中の実験的な個人用ツールです。公開しても、現時点で
マルチユーザー対応、互換性の保証、運用サポート SLA は提供しません。

ライセンス: この個人開発ではライセンスを付与していません。リポジトリには
`LICENSE` ファイルを含めていません。

## セットアップ

前提: Python 3.12以上、uv、Codex CLI 0.144.1以上。`codex/` providerは
既定でChatGPTログインを使う。

```bash
bash install.sh                # advisor.toml / advisor.env 作成 + MCP 登録 + AGENTS.md 誘導
codex login status             # ChatGPT認証を使う場合に確認
vi ~/.codex/advisor.env        # API provider または Codex API認証で使うキーを記入
```

`install.sh` は既存の `advisor.toml` を上書きしない。旧版から移行する場合は、
下記の `model` を手動で変更する。

## 使い方

- Codex が計画前・エラー反復時・完了宣言前に自動で `consult_advisor` を呼ぶ
- 手動相談: 「advisor に相談して」
- ChatGPT認証のGPT: `model = "codex/gpt-5.6-sol"`（既定）
- Codex APIキーのGPT: `model = "codex/gpt-5.6-sol"` に加えて、下記の `[providers.codex]` を設定
- OpenAI API: `model = "openai/<Chat Completions 対応モデル ID>"`
- モデル切替: 「advisor を codex/gpt-5.6-sol にして」(または `~/.codex/advisor.toml` の `model =` を編集)
- 無効化: 「advisor を off にして」または `advisor.toml` で `enabled = false`

`codex/` と `openai/` は同居できる。`codex/` は隔離した Codex CLI 経由で、認証方式を
`chatgpt`（既定）または `api` から明示的に選ぶ。`openai/` は直接HTTP呼び出しで
`OPENAI_API_KEY` を使う。1回の相談では `model` が示す一方だけを使い、認証失敗時に
別の認証方式や `openai/` へ自動フォールバックしない。

## 設定 (~/.codex/advisor.toml)

```toml
enabled = true
model = "codex/gpt-5.6-sol"            # "<provider>/<model>"。モデル名は無検証
max_context_chars = 400000            # advisor に渡す会話の上限(古い方から切り詰め)
max_consults_per_session = 20         # セッションあたり相談回数上限
reasoning = "medium"      # 任意: low/medium/high/xhigh。デフォルトは medium。reasoning = "" でプロバイダ既定に戻せる

# Codex CLI のAPIキー認証を使う場合だけ指定(ChatGPT認証が既定)
[providers.codex]
auth_method = "api"                    # chatgpt または api
api_key_env = "OPENAI_API_KEY"         # 省略時はCodex CLI保存済み認証を使う

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

API キーは `~/.codex/advisor.env` のみに置く。ChatGPT認証の `codex/` 子プロセスには
advisor用credentialを渡さない。API認証の `codex/` では、設定した `api_key_env` の
値だけを子プロセス用の `CODEX_API_KEY` として渡し、それ以外のcredentialは除去する。
環境変数を指定しない場合は、Codex CLIの `codex login --with-api-key` で保存した認証を使う。
`api_key_env` を指定した場合、その変数が未設定なら保存済み認証へ切り替えずエラーにする。
子Codexは
一時directory、read-only sandbox、ephemeral sessionで実行し、shell・Web・MCP・
app・subagent等を無効化する。APIエラーに含まれる選択providerのキー値は伏せ字化する。

データ送信: `consult_advisor` は、現在のセッションから復元した user/assistant メッセージ、
tool call、tool result を、設定された advisor provider に送信します。`codex/` では
ログイン中のChatGPT workspace、API providerでは各APIアカウントのデータ処理条件が
適用されます。transcript の秘密情報は自動除去されません。

## 開発

```bash
uv run pytest -q          # テスト
uv run ruff check src tests && uv run pyright   # lint+型
```
