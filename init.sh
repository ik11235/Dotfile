#!/bin/bash -eu

cd "$(dirname "$0")"

/bin/bash .link_dir_and_file.sh

/bin/bash .software-install.sh

#defalut shell change
ZSHPATH=$(which zsh)
sudo sh -c "echo ${ZSHPATH} >> /etc/shells"
chsh -s "${ZSHPATH}"

# textlintのインストール
npm i -g textlint textlint-rule-preset-japanese textlint-rule-prh textlint-rule-ja-no-redundant-expression

# anyenvのinit & installしたい*envのインストール
eval "$(anyenv init -)"
yes | anyenv install --init
ANYENV_INSTALL_TARGET=("rbenv" "pyenv" "nodenv")

for ANYENV_TARGET in "${ANYENV_INSTALL_TARGET[@]}"
do
    anyenv install "${ANYENV_TARGET}"
done

## anyenvのプラグインinstall
mkdir -p "$(anyenv root)/plugins"
git clone https://github.com/znz/anyenv-update.git "$(anyenv root)/plugins/anyenv-update"

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

# private file作成
touch "${HOME}/.zsh.d/zshrc_mac_private"

# powerline-fonts install
(
# clone
git clone https://github.com/powerline/fonts.git --depth=1
# install
cd fonts
./install.sh
# clean-up a bit
cd ..
rm -rf fonts
)