#!/bin/sh
# statusLine command for Claude Code
# Based on zsh prompt: PROMPT="%n@%m% " RPROMPT="%1(v|[gitbranch]|)[cwd]"
input=$(cat)
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd')
ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty' | awk '{printf "%.2f", $1}')
effort=$(echo "$input" | jq -r '.effort.level // empty')
thinking=$(echo "$input" | jq -r '.thinking.enabled // false')
# worktree.name は --worktree セッションのみ。EnterWorktree 等の linked worktree は workspace.git_worktree に入る
wt=$(echo "$input" | jq -r '.worktree.name // .workspace.git_worktree // empty')
rl5=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty | floor')
rl7=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty | floor')
branch=$(git --no-optional-locks -C "$cwd" branch --show-current 2>/dev/null)
user=$(whoami)
host=$(hostname -s)
suffix=""
if [ -n "$effort" ]; then
  suffix="${suffix} ${effort}"
fi
if [ "$thinking" = "true" ]; then
  suffix="${suffix}+T"
fi
if [ -n "$ctx_pct" ]; then
  suffix="${suffix} ctx:${ctx_pct}%"
fi
if [ -n "$cost" ] && [ "$cost" != "0.00" ]; then
  suffix="${suffix} \$${cost}"
fi
if [ -n "$rl5" ] || [ -n "$rl7" ]; then
  suffix="${suffix} rl:${rl5:--}/${rl7:--}%"
fi
if [ -n "$wt" ]; then
  suffix="${suffix} wt:${wt}"
fi
if [ -n "$branch" ]; then
  printf "%s@%s [%s] [%s]%s" "$user" "$host" "$branch" "$cwd" "$suffix"
else
  printf "%s@%s [%s]%s" "$user" "$host" "$cwd" "$suffix"
fi
