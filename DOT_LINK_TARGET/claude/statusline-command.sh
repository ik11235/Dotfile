#!/bin/sh
# statusLine command for Claude Code
# Based on zsh prompt: PROMPT="%n@%m% " RPROMPT="%1(v|[gitbranch]|)[cwd]"
# shellcheck disable=SC2154  # cwd 等の変数は jq の出力を eval して代入するため、静的には未代入に見える
input=$(cat)
# 必要な値を jq 1 回で取り出す。@sh で各値をシェル用にクォートした代入文を生成して eval する
# (値が無いときは空文字。worktree.name は --worktree セッションのみで、EnterWorktree 等の
#  linked worktree は workspace.git_worktree に入る)
eval "$(printf '%s' "$input" | jq -r '
  @sh "cwd=\(.workspace.current_dir // .cwd // "")
       ctx_pct=\(.context_window.used_percentage // "")
       cost_raw=\(.cost.total_cost_usd // "")
       effort=\(.effort.level // "")
       thinking=\(.thinking.enabled // false)
       wt=\(.worktree.name // .workspace.git_worktree // "")
       rl5=\(.rate_limits.five_hour.used_percentage // "" | if type == "number" then floor else . end)
       rl7=\(.rate_limits.seven_day.used_percentage // "" | if type == "number" then floor else . end)"
')"
cost=""
if [ -n "$cost_raw" ]; then
  cost=$(printf '%s' "$cost_raw" | awk '{printf "%.2f", $1}')
fi
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
