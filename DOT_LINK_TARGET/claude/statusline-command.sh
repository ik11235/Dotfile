#!/bin/sh
# statusLine command for Claude Code
# Based on zsh prompt: PROMPT="%n@%m% " RPROMPT="%1(v|[gitbranch]|)[cwd]"
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty' | awk '{printf "%.2f", $1}')
branch=$(git -C "$cwd" branch --show-current --no-optional-locks 2>/dev/null)
user=$(whoami)
host=$(hostname -s)
suffix=""
if [ -n "$ctx_pct" ]; then
  suffix="${suffix} ctx:${ctx_pct}%"
fi
if [ -n "$cost" ] && [ "$cost" != "0.00" ]; then
  suffix="${suffix} \$${cost}"
fi
if [ -n "$branch" ]; then
  printf "%s@%s [%s] [%s]%s" "$user" "$host" "$branch" "$cwd" "$suffix"
else
  printf "%s@%s [%s]%s" "$user" "$host" "$cwd" "$suffix"
fi
