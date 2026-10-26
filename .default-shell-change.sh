#!/bin/bash
set -euo pipefail

echo "[*] running .default-shell-change.sh"

ZSH_PATH=$(command -v zsh) || { echo "Error: zsh not found in PATH" >&2; exit 1; }

if ! grep -qx "$ZSH_PATH" /etc/shells; then
  printf '%s\n' "$ZSH_PATH" | sudo tee -a /etc/shells >/dev/null
fi

chsh -s "$ZSH_PATH"
