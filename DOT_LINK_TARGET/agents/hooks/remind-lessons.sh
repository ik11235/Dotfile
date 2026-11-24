#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

hook_init
project_dir=$(hook_project_dir)
lessons_file="${project_dir}/tasks/lessons.md"

if [ -f "$lessons_file" ] && [ -n "$(find "$lessons_file" -maxdepth 0 -mtime +7 -print 2>/dev/null)" ]; then
  hook_emit_message "tasks/lessons.md が 1 週間以上更新されていません。今回のセッションで学びがあったか確認してください"
else
  hook_emit_noop
fi
