#!/bin/bash
set -euo pipefail

if [ "$(uname)" != "Darwin" ]; then
  echo "Warning: .powerline-fonts-install.sh は現状macOSのみ対応。Linux対応は今後実装予定のためskipします。" >&2
  exit 0
fi

echo "[*] running .powerline-fonts-install.sh"

# powerline
# 既存 fonts ディレクトリが残っていれば削除（前回の実行中断に備える）
rm -rf fonts
# clone
git clone https://github.com/powerline/fonts.git --depth=1
# install
cd fonts
./install.sh
# clean-up a bit
cd ..
rm -rf fonts

# UDEV Gothic (NF) は Homebrew cask "font-udev-gothic-nf" で入れる (Brewfile 参照)。
# 以前はここで GitHub API から zip を取得して ~/Library/Fonts に展開していた
