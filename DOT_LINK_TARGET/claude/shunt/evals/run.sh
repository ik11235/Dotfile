#!/bin/bash
# hook の判定テスト。  bash ~/.claude/shunt/evals/run.sh
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXTURES="$SCRIPT_DIR/.fixtures"
PASSED=0; FAILED=0; TOTAL=0

setup_fixtures() {
  rm -rf "$FIXTURES"; mkdir -p "$FIXTURES"
  local n; n=$(jq '.evals | length' "$1")
  for ((i=0;i<n;i++)); do
    local lines; lines=$(jq -r ".evals[$i].fixture.lines // empty" "$1"); [ -z "$lines" ] && continue
    local p; p=$(jq -r ".evals[$i].input.tool_input.file_path // .evals[$i].input.tool_input.command" "$1" | grep -o '{{FIXTURES}}/[^ "|>]*' | head -1 | sed "s|{{FIXTURES}}|$FIXTURES|")
    local hr; hr=$(jq -r ".evals[$i].fixture.home_relative // empty" "$1"); if [ -n "$hr" ]; then p="$HOME/$hr"; mkdir -p "$(dirname "$p")"; fi
    [ -z "$p" ] && continue
    if [ "$lines" -eq 0 ]; then : > "$p"; else seq 1 "$lines" | awk '{print "line "NR}' > "$p"; fi
  done
}

run_suite() {
  local hook="$1" file="$2" label="$3"
  setup_fixtures "$file"
  echo; echo "$label"; echo "──────────────────────────────────────────────"
  local n; n=$(jq '.evals | length' "$file")
  for ((i=0;i<n;i++)); do
    local name expected reason input env_json actual
    name=$(jq -r ".evals[$i].name" "$file"); expected=$(jq -r ".evals[$i].expected" "$file"); reason=$(jq -r ".evals[$i].reason" "$file")
    input=$(jq -c ".evals[$i].input" "$file" | sed "s|{{FIXTURES}}|$FIXTURES|g")
    env_json=$(jq -c ".evals[$i].env // {}" "$file")
    actual=$(printf '%s' "$input" | env $(printf '%s' "$env_json" | jq -r 'to_entries[] | "\(.key)=\(.value)"') bash "$hook" 2>/dev/null | jq -r '.hookSpecificOutput.permissionDecision // "INVALID"')
    TOTAL=$((TOTAL+1))
    if [ "$actual" = "$expected" ]; then printf "  \033[32mPASS\033[0m  %-28s %s\n" "$name" "$reason"; PASSED=$((PASSED+1))
    else printf "  \033[31mFAIL\033[0m  %-28s expected=%s got=%s\n" "$name" "$expected" "$actual"; FAILED=$((FAILED+1)); fi
  done
  rm -rf "$FIXTURES" "$HOME/.claude/shunt/evals/.fixtures-home"
}

run_suite "$SCRIPT_DIR/../hooks/check-file-size" "$SCRIPT_DIR/hook-evals.json" "Read hook (check-file-size)"
run_suite "$SCRIPT_DIR/../hooks/check-bash-read" "$SCRIPT_DIR/bash-hook-evals.json" "Bash hook (check-bash-read)"
echo; printf "Total: \033[32m%d passed\033[0m, \033[31m%d failed\033[0m, %d total\n" "$PASSED" "$FAILED" "$TOTAL"
[ "$FAILED" -gt 0 ] && exit 1; exit 0
