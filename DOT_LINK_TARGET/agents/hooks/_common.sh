# shellcheck shell=bash
# Claude Code / Antigravity / Codex 共通のフック補助関数。
# 呼び出し元スクリプトから source して使う。

HOOK_STDIN=""
HOOK_IS_ANTIGRAVITY=0
HOOK_EVENT_NAME=""

hook_init() {
  # stdin が TTY でない場合のみ builtin read で読む（$(cat) は閉じた fd 0 でパイプが fd 0 を再利用しハングする）
  HOOK_STDIN=""
  if [ ! -t 0 ]; then
    IFS= read -r -d '' HOOK_STDIN 2>/dev/null || true
  fi

  if [ -n "$HOOK_STDIN" ] && command -v jq >/dev/null 2>&1; then
    HOOK_EVENT_NAME=$(printf '%s' "$HOOK_STDIN" | jq -r '.hookEventName // empty' 2>/dev/null || true)
    if [ -n "$HOOK_EVENT_NAME" ]; then
      HOOK_IS_ANTIGRAVITY=1
    fi
  fi
}

hook_project_dir() {
  local dir=""
  if [ -n "$HOOK_STDIN" ] && command -v jq >/dev/null 2>&1; then
    dir=$(printf '%s' "$HOOK_STDIN" | jq -r '[.cwd, .workspacePaths[0]] | map(select(type == "string" and length > 0)) | first // empty' 2>/dev/null || true)
  fi
  if [ -z "$dir" ]; then
    dir="${CLAUDE_PROJECT_DIR:-$PWD}"
  fi
  printf '%s' "$dir"
}

hook_emit_message() {
  local msg=$1
  if [ "$HOOK_IS_ANTIGRAVITY" -eq 1 ]; then
    if [ "$HOOK_EVENT_NAME" = "Stop" ]; then
      # Antigravity の Stop は continue を返すと再実行になるため、通知のみ用途では停止を許可する
      printf '{"decision":"allow"}\n'
    else
      jq -cn --arg msg "$msg" '{injectSteps:[{systemMessage:{systemMessage:$msg}}]}'
    fi
  else
    if command -v jq >/dev/null 2>&1; then
      jq -cn --arg msg "$msg" '{systemMessage:$msg}'
    else
      printf '{"systemMessage":"%s"}\n' "$msg"
    fi
  fi
}

hook_emit_noop() {
  if [ "$HOOK_IS_ANTIGRAVITY" -eq 1 ]; then
    if [ "$HOOK_EVENT_NAME" = "Stop" ]; then
      printf '{"decision":"allow"}\n'
    else
      printf '{}\n'
    fi
  fi
}
