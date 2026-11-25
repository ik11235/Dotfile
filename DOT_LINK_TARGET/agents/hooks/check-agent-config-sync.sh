#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

hook_init

sync_bin=""
if [ -x "${HOME}/.bin/agent-config-sync" ]; then
  sync_bin="${HOME}/.bin/agent-config-sync"
elif command -v agent-config-sync >/dev/null 2>&1; then
  sync_bin=$(command -v agent-config-sync)
fi

if [ -z "$sync_bin" ]; then
  hook_emit_noop
  exit 0
fi

check_out=""
check_rc=0
check_out=$("$sync_bin" check 2>/dev/null) || check_rc=$?

if [ "$check_rc" -eq 1 ] && [ -n "$check_out" ]; then
  summary=$(printf '%s' "$check_out" | tr '\n' ',' | sed 's/,$//; s/,/, /g')
  hook_emit_message "subagents 設定に差分があります（${summary}）。Antigravity 側で直接編集した内容があれば先に \`agent-config-sync check --diff\` で確認して正本（~/.claude/agents/）へ反映し、その後 \`agent-config-sync sync\` を実行してください"
else
  hook_emit_noop
fi
