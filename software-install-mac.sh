#!/bin/bash

# mac用のアプリケーションインストール確認コード

# brewのインストールの有無をチェック
# インストールされていない場合インストール
if ! type brew >/dev/null; then
  echo "not Install brew."
  echo "Start install brew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
fi

brew bundle --global
