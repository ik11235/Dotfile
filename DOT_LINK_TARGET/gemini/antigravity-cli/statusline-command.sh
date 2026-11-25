#!/bin/sh
# statusLine command for Antigravity CLI (agy)
# Based on ~/.claude/statusline-command.sh (zsh prompt style + session metrics)
input=$(cat)

cwd=""
branch_vcs=""
ctx_pct=""
cost_raw=""
effort=""
rl5=""
rl7=""
rl_other=""

# 必要な値を jq 1 回で取り出す。@sh で各値をシェル用にクォートした代入文を生成して eval する
eval "$(printf '%s' "$input" | jq -r '
  def used_pct:
    ((1 - .) * 100 | floor | if . < 0 then 0 elif . > 100 then 100 else . end);
  def model_family:
    ((.model.id // .model.display_name // "") | ascii_downcase) as $m
    | if ($m | contains("gemini")) then "gemini"
      elif ($m | contains("claude")) then "claude"
      elif ($m | contains("gpt")) then "gpt"
      else "" end;
  def active_quotas:
    (.quota // {} | to_entries
      | map(select((.value | type == "object")
                   and (.value.disabled != true)
                   and (.value.remaining_fraction | type == "number"))));
  def scoped_quotas:
    model_family as $fam
    | active_quotas as $all
    | if $fam == "" then $all
      else ($all | map(select(.key | ascii_downcase | contains($fam)))) as $matched
      | if ($matched | length) > 0 then $matched else $all end
      end;
  scoped_quotas as $q
  | ($q | map(select(.key | test("5h|five.?hour"; "i"))) | first
        | if . then (.value.remaining_fraction | used_pct) else "" end) as $rl5
  | ($q | map(select(.key | test("week|7d|seven.?day"; "i"))) | first
        | if . then (.value.remaining_fraction | used_pct) else "" end) as $rl7
  | ($q | map(select(.key | test("5h|five.?hour|week|7d|seven.?day"; "i") | not)
              | "\(.key):\(.value.remaining_fraction | used_pct)%") | join(",")) as $rl_other
  | @sh "cwd=\(.workspace.current_dir // .cwd // "")
         branch_vcs=\(.vcs.branch // "")
         ctx_pct=\(.context_window.used_percentage // "" | if type == "number" then floor else . end)
         cost_raw=\(.cost.total_usd // "")
         effort=\(.model.effort // "")
         rl5=\($rl5)
         rl7=\($rl7)
         rl_other=\($rl_other)"
' 2>/dev/null)"

cost=""
if [ -n "$cost_raw" ]; then
  cost=$(printf '%s' "$cost_raw" | LC_NUMERIC=C awk '{printf "%.2f", $1}')
fi

branch="$branch_vcs"
wt=""
if [ -n "$cwd" ]; then
  if [ -z "$branch" ]; then
    branch=$(git --no-optional-locks -C "$cwd" branch --show-current 2>/dev/null)
  fi
  git_dir=""
  git_common_dir=""
  {
    read -r git_dir
    read -r git_common_dir
  } <<EOF
$(git --no-optional-locks -C "$cwd" rev-parse --path-format=absolute --git-dir --git-common-dir 2>/dev/null)
EOF
  if [ -n "$git_dir" ] && [ -n "$git_common_dir" ] && [ "$git_dir" != "$git_common_dir" ]; then
    wt=$(basename "$git_dir")
  fi
fi

user=$(whoami)
host=$(hostname -s)
suffix=""
if [ -n "$effort" ]; then
  suffix="${suffix} ${effort}"
fi
if [ -n "$ctx_pct" ]; then
  suffix="${suffix} ctx:${ctx_pct}%"
fi
if [ -n "$cost" ] && [ "$cost" != "0.00" ]; then
  suffix="${suffix} \$${cost}"
fi
if [ -n "$rl5" ] || [ -n "$rl7" ]; then
  suffix="${suffix} rl:${rl5:--}/${rl7:--}%"
elif [ -n "$rl_other" ]; then
  suffix="${suffix} rl:${rl_other}"
fi
if [ -n "$wt" ]; then
  suffix="${suffix} wt:${wt}"
fi

if [ -n "$branch" ]; then
  printf "%s@%s [%s] [%s]%s" "$user" "$host" "$branch" "$cwd" "$suffix"
else
  printf "%s@%s [%s]%s" "$user" "$host" "$cwd" "$suffix"
fi
