#!/bin/bash -eu

if [ "$(uname)" = "Darwin" ]; then
  # ネットワークドライブで.DS_Store 等の作成を抑制する
  ## https://support.apple.com/ja-jp/HT208209
  defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool TRUE
  # USBストレージで.DS_Store 等の作成を抑制する
  defaults write com.apple.desktopservices DSDontWriteUSBStores -bool TRUE

  # Bluetoothの音質周りの設定
  ## https://minatokobe.com/wp/os-x/mac/post-75289.html
  ## aptXを有効化
  sudo defaults write bluetoothaudiod "Enable AptX codec" -bool true
  ## AACを有効化
  sudo defaults write bluetoothaudiod "Enable AAC codec" -bool true
  ## bitpoolの最低値を上げて、Bluetoothヘッドフォン/ヘッドセットの音質を向上させる
  ### https://news.mynavi.jp/article/osxhack-63/
  defaults write com.apple.BluetoothAudioAgent "Apple Bitpool Min (editable)" -int 40

  # Mission Control
  ## 左下 → 画面ロック
  defaults write com.apple.dock wvous-bl-corner -int 13
  defaults write com.apple.dock wvous-bl-modifier -int 0

  # 不可視ファイルを表示
  defaults write com.apple.finder AppleShowAllFiles YES

  # 全ての拡張子のファイルを表示する
  defaults write NSGlobalDomain AppleShowAllExtensions -bool true

  # 自動大文字の無効化
  defaults write NSGlobalDomain NSAutomaticCapitalizationEnabled -bool false

  # フルキーボードアクセスを有効
  defaults write NSGlobalDomain AppleKeyboardUIMode -int 3

  # 起動音を小さく
  sudo nvram SystemAudioVolume=%01

  # キーのリピート
  defaults write NSGlobalDomain KeyRepeat -int 2

  # リピート入力認識までの時間
  defaults write NSGlobalDomain InitialKeyRepeat -int 15

  # デフォルトをplainTextに
  defaults write com.apple.TextEdit RichText -int 0
fi
