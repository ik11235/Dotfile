# 外部ツール連携（tmux、fuzzy finder等）

## ログイン時にtmux自動アタッチする関数
### zshrc_*_privateで呼び出すことを想定
function tmux_auto_attach () {
  ## https://qiita.com/ssh0/items/a9956a74bff8254a606a
  ### $PERCOL=/usr/local/bin/peco

  # https://qiita.com/abcang/items/e427d9e4ff8d8e5f0c31
  if [[ -n "${REMOTEHOST}${SSH_CONNECTION}" && -z "$TMUX" && -z "$STY" ]]; then
    function confirm {
      MSG=$1
        while :
        do
          echo -n "${MSG} [Y/n]: "
          read ans
          if [ -z "$ans" ]; then
            ans="y"
          fi
          case $ans in
            [yY]) return 0 ;;
            [nN]) return 1 ;;
          esac
        done
    }

    option=""
    if tmux has-session && tmux list-sessions; then
        echo "tmux attached session "
        option="attach"
    else
        echo "tmux created new session"
    fi
    tmux $option && confirm "exit?" && exit
  fi
}

# 有効なfuzzy finderを自動選択
## https://qiita.com/b4b4r07/items/9e1bbffb1be70b6ce033
AVAILABLE_FUZZY_FINDER_LIST="fzf:peco"
available-fuzzy-finder-find () {
    local x candidates
    candidates="$1:"
    while [ -n "$candidates" ]
    do
        x=${candidates%%:*}
        candidates=${candidates#*:}
        if type "$x" >/dev/null 2>&1; then
            echo "$x"
            return 0
        else
            continue
        fi
    done
    return 1
}

export AVAILABLE_FUZZY_FINDER=$(available-fuzzy-finder-find $AVAILABLE_FUZZY_FINDER_LIST)

# tmux使用時にホスト名から色指定
## https://memo.sugyan.com/entry/20120306/1331009647
if [ "$TMUX" != "" ]; then
    tmux set-option status-bg colour$(($(echo -n $(whoami)@$(hostname) | sum | cut -f1 -d' ') % 8 + 8)) | cat > /dev/null
fi

## https://x.com/suna_gaku/status/2035852481872429447
export CLAUDE_CODE_NEW_INIT=1
