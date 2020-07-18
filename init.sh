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

/bin/bash .anyenv-init-and-install.sh

# private file作成
touch "${HOME}/.zsh.d/zshrc_mac_private"

# powerline-fonts install
/bin/bash .powerline-fonts-install.sh
