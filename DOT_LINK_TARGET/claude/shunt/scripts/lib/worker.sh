#!/bin/bash
# 作業用（軽量）モデル呼び出しの共通部。
# SHUNT_WORKER=claude (既定) | gemini
#   claude: claude -p --model $SHUNT_CLAUDE_MODEL  (既定 claude-haiku-4-5-20251001)
#   gemini: gemini -p -m $SHUNT_GEMINI_MODEL       (既定 gemini-2.5-flash)
# 本文は stdin で渡す（argv 経由にしないので ARG_MAX に縛られない）。

SHUNT_WORKER="${SHUNT_WORKER:-claude}"
SHUNT_CLAUDE_MODEL="${SHUNT_CLAUDE_MODEL:-claude-haiku-4-5-20251001}"
SHUNT_GEMINI_MODEL="${SHUNT_GEMINI_MODEL:-gemini-2.5-flash}"
SHUNT_TIMEOUT_SECONDS="${SHUNT_TIMEOUT_SECONDS:-180}"
SHUNT_MAX_PAYLOAD_BYTES="${SHUNT_MAX_PAYLOAD_BYTES:-2000000}"
SHUNT_LOG="${SHUNT_LOG:-$HOME/.claude/shunt/usage.log}"

SHUNT_TMPFILES=()
shunt_tmpfile() {
  local f
  f=$(mktemp) || return 1
  SHUNT_TMPFILES+=("$f")
  trap 'rm -f "${SHUNT_TMPFILES[@]}"' EXIT
  printf -v "$1" '%s' "$f"
}

shunt_preflight() {
  local missing=""
  command -v jq >/dev/null 2>&1 || missing="$missing jq"
  case "$SHUNT_WORKER" in
    claude) command -v claude >/dev/null 2>&1 || missing="$missing claude" ;;
    gemini) command -v gemini >/dev/null 2>&1 || missing="$missing gemini" ;;
    *) echo "Error: unknown SHUNT_WORKER=$SHUNT_WORKER (claude|gemini)" >&2; return 1 ;;
  esac
  if [ -n "$missing" ]; then
    echo "Error: missing required command(s):$missing" >&2
    return 1
  fi
  return 0
}

# $1 system prompt, $2 message file → stdout に回答
shunt_invoke() {
  local system_prompt="$1" message_file="$2" bytes rc out
  bytes=$(wc -c < "$message_file" | tr -d ' ')
  if [ "$bytes" -gt "$SHUNT_MAX_PAYLOAD_BYTES" ]; then
    echo "Error: request is $bytes bytes, over SHUNT_MAX_PAYLOAD_BYTES=$SHUNT_MAX_PAYLOAD_BYTES. Send fewer files." >&2
    return 1
  fi

  local timeout_cmd=()
  if command -v timeout >/dev/null 2>&1; then timeout_cmd=(timeout "$SHUNT_TIMEOUT_SECONDS");
  elif command -v gtimeout >/dev/null 2>&1; then timeout_cmd=(gtimeout "$SHUNT_TIMEOUT_SECONDS"); fi

  case "$SHUNT_WORKER" in
    claude)
      # --setting-sources "": settings/hooks/CLAUDE.md を読まない（--bare は keychain 認証を読めず Not logged in になる）。--tools "": ファイルは本文で渡すのでツール不要
      out=$("${timeout_cmd[@]}" claude -p --no-session-persistence --setting-sources "" \
              --model "$SHUNT_CLAUDE_MODEL" --tools "" \
              --system-prompt "$system_prompt" < "$message_file" 2>/dev/null)
      rc=$? ;;
    gemini)
      out=$({ printf '%s\n\n' "$system_prompt"; cat "$message_file"; } | \
            GEMINI_CLI_TRUST_WORKSPACE=true "${timeout_cmd[@]}" gemini -p -m "$SHUNT_GEMINI_MODEL" 2>/dev/null \
            | grep -v '^Ripgrep is not available')
      rc=$? ;;
  esac

  if [ "$rc" -eq 124 ]; then
    echo "Error: worker timed out after ${SHUNT_TIMEOUT_SECONDS}s. Raise SHUNT_TIMEOUT_SECONDS or split the files." >&2
    return 1
  fi
  if [ "$rc" -ne 0 ] || [ -z "$out" ]; then
    echo "Error: worker ($SHUNT_WORKER) failed (rc=$rc) or returned nothing." >&2
    return 1
  fi
  printf '%s\n' "$out"
}

# 使用ログ: 日時 / モード / worker / 入力概算トークン / 出力概算トークン
shunt_log() {
  local mode="$1" in_bytes="$2" out_bytes="$3"
  mkdir -p "$(dirname "$SHUNT_LOG")" 2>/dev/null
  printf '%s\t%s\t%s\t%s\t%s\n' "$(date +%Y-%m-%dT%H:%M:%S)" "$mode" "$SHUNT_WORKER" "$((in_bytes / 4))" "$((out_bytes / 4))" >> "$SHUNT_LOG" 2>/dev/null
}
