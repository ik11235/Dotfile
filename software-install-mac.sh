#!/bin/bash

#mac用のコード

#brewのインストールの有無をチェック
#インストールされていない場合インストール
type brew > /dev/null
if [ $? -ne 0 ]; then
  echo "not Install brew."
  echo "Start install brew"
  ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
fi

brew bundle
