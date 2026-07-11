#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
MARKER_START="<!-- codex-advisor:start -->"

mkdir -p "$CODEX_HOME"

if [[ ! -f "$CODEX_HOME/advisor.toml" ]]; then
  cat > "$CODEX_HOME/advisor.toml" <<'EOF'
enabled = true
model = "codex/gpt-5.6-sol"
reasoning = "medium"
max_context_chars = 400000
max_consults_per_session = 20
EOF
  echo "created $CODEX_HOME/advisor.toml"
fi

if [[ ! -f "$CODEX_HOME/advisor.env" ]]; then
  cat > "$CODEX_HOME/advisor.env" <<'EOF'
# API keys for codex-advisor. Read only by the MCP server process.
# Uncomment and fill in the providers you use:
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# GEMINI_API_KEY=
EOF
  chmod 600 "$CODEX_HOME/advisor.env"
  echo "created $CODEX_HOME/advisor.env (add your API keys here)"
fi

if ! codex mcp get advisor >/dev/null 2>&1; then
  codex mcp add advisor -- uv --directory "$REPO_DIR" run codex-advisor
  echo "registered MCP server 'advisor'"
fi

# 承認プロンプトなしで advisor ツールを呼べるようにする(これが無いと
# codex exec や自動相談でツール呼び出しがキャンセルされる)
advisor_has_approval_mode() {
  awk '
    /^\[mcp_servers\.advisor\]$/ { in_advisor = 1; next }
    /^\[/ { in_advisor = 0 }
    in_advisor && /^[[:space:]]*default_tools_approval_mode[[:space:]]*=/ { found = 1 }
    END { exit(found ? 0 : 1) }
  ' "$CODEX_HOME/config.toml" 2>/dev/null
}

if ! advisor_has_approval_mode; then
  sed -i '/^\[mcp_servers\.advisor\]$/a default_tools_approval_mode = "approve"' \
    "$CODEX_HOME/config.toml"
  if advisor_has_approval_mode; then
    echo "set default_tools_approval_mode=approve for 'advisor'"
  fi
fi

if ! grep -qF "$MARKER_START" "$CODEX_HOME/AGENTS.md" 2>/dev/null; then
  cat >> "$CODEX_HOME/AGENTS.md" <<EOF

$MARKER_START
# Advisor
You have a consult_advisor tool backed by a separately configured advisor
model. Consult it at decision points: before committing to a non-trivial
implementation plan, when the same error persists after two fix attempts, and
before declaring a complex task complete. Also consult it whenever the user
asks. When the user asks to change or disable the advisor model, use the
advisor_config tool instead of editing files.
<!-- codex-advisor:end -->
EOF
  echo "added advisor guidance to $CODEX_HOME/AGENTS.md"
fi

echo "install complete"
