#!/bin/bash -eu

if [ "$(uname)" = "Darwin" ]; then
  # ネットワークドライブで.DS_Store 等の作成を抑制する
  ## https://support.apple.com/ja-jp/HT208209
  defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool TRUE
fi

