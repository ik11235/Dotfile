#!/bin/bash
set -euo pipefail

echo "[*] running .default-shell-change.sh"

ZSH_PATH=$(command -v zsh) || { echo "Error: zsh not found in PATH" >&2; exit 1; }

if ! grep -qx "$ZSH_PATH" /etc/shells; then
  printf '%s\n' "$ZSH_PATH" | sudo tee -a /etc/shells >/dev/null
fi

# 現在のログインシェルを取得する ($SHELL は再ログインまで更新されないため使わない)
current_shell() {
  if [ "$(uname)" = "Darwin" ]; then
    dscl . -read "/Users/$(id -un)" UserShell 2>/dev/null | awk '{print $2}'
  else
    getent passwd "$(id -un)" | cut -d: -f7
  fi
}

# 既に zsh なら chsh (パスワード入力を求められる) を省略する
if [ "$(current_shell)" = "$ZSH_PATH" ]; then
  echo "login shell is already ${ZSH_PATH}, skip."
else
  chsh -s "$ZSH_PATH"
fi
