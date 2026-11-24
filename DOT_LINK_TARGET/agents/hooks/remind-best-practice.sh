#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

hook_init
marker_file="${HOME}/.agents/skills/best-practice/.last-run"

if [ ! -f "$marker_file" ] || [ -n "$(find "$marker_file" -maxdepth 0 -mtime +14 -print 2>/dev/null)" ]; then
  hook_emit_message "/best-practice によるルール見直しが 2 週間以上行われていません。設定の陳腐化を防ぐため /best-practice の実行を検討してください"
else
  hook_emit_noop
fi
