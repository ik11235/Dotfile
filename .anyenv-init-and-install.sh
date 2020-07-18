#!/bin/bash -eu

# anyenvのinit & installしたい*envのインストール
eval "$(anyenv init -)"
yes | anyenv install --init
ANYENV_INSTALL_TARGET=("rbenv" "pyenv" "nodenv")

for ANYENV_TARGET in "${ANYENV_INSTALL_TARGET[@]}"; do
  anyenv install "${ANYENV_TARGET}"
done

## anyenvのプラグインinstall
mkdir -p "$(anyenv root)/plugins"
git clone https://github.com/znz/anyenv-update.git "$(anyenv root)/plugins/anyenv-update"

# 各種install後に再度initしておく
eval "$(anyenv init -)"

# rbenvで最新バージョンをインストール
## https://mawatari.jp/archives/install-latest-stable-version-of-ruby-using-rbenv
RUBY_VER=$(rbenv install -l | grep -v - | tail -1 | tr -d ' ')
rbenv install "$RUBY_VER"
rbenv global "$RUBY_VER"

# nodenvで最新バージョンをインストール
NODE_VER=$(nodenv install -l | grep -v "[a-z]" | tail -1 | tr -d ' ')
nodenv install "$NODE_VER"
nodenv global "$NODE_VER"

## yarnを誤ってhomebrew等で入れないように先にyarnを入れておく
nodenv exec npm install -g yarn

# pyenvで3.7.7をインストール
## 3.7.7決め打ちなのは→対策　https://twitter.com/ik11235/status/1283723978985488385
## TODO: ↑の問題が解消したら最新バージョンを入れるように変更
PYTHON_VER="3.7.7"
pyenv install "$PYTHON_VER"
pyenv global "$PYTHON_VER"
