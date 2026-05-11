# SSH 異常切断などで残った xterm 拡張モードをリセットする
#   \e[?1004l : focus reporting OFF
#   \e[>4;0m  : modifyOtherKeys OFF (Ctrl+R 等で `;5;114~` が出るのを防ぐ)
# tmux 内では tmux 自身が状態を管理しているのでスキップ
if status is-interactive; and not set -q TMUX
    printf '\e[?1004l\e[>4;0m'
end
