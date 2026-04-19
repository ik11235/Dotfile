#!/bin/bash -eu
set -o pipefail

echo "[*] running .default-shell-change.sh"

ZSH_PATH=$(command -v zsh)

if ! grep -qx "$ZSH_PATH" /etc/shells; then
  printf '%s\n' "$ZSH_PATH" | sudo tee -a /etc/shells >/dev/null
fi

chsh -s "$ZSH_PATH"
