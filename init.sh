#!/bin/bash

cd "`dirname $0`" || exit

function link_dir_file() {
    TARGET_DIR=$1
    LINK_TARGET_PREFIX=$2

    cd $TARGET_DIR || exit

    # SC2045
    for LINK in *
    do
      [[ -e "$LINK" ]] || break
      # 既にリンク済みの場合、そのディレクトリの階層の下に更にリンクされるので事前にディレクトリの存在有無をチェックする
      # ファイルの場合、ln側で自動的に重複で止まるのでチェックは不要
      if [ -d "${LINK_TARGET_PREFIX}${LINK}" ]; then
        echo "${LINK_TARGET_PREFIX}${LINK}: Directory exists."
        continue;
      fi
      ln -sv "`pwd`/${LINK}" ${LINK_TARGET_PREFIX}${LINK}
    done

    cd .. || exit
}

## 先頭に.をつけてリンクする対象一覧
DOT_LINK_FILE_DIR="DOT_LINK_TARGET"
link_dir_file "${DOT_LINK_FILE_DIR}" "${HOME}/."

## 先頭に.をつけず、そのままの名前でリンクする対象一覧
LINK_FILE_DIR="LINK_TARGET"
link_dir_file "${LINK_FILE_DIR}" "${HOME}/"

echo "Do you want to install a package ? [Y/n]"
read ANSWER

ANSWER=`echo $ANSWER | tr y Y | tr -d '[\[\]]'`
case $ANSWER in
    ""|Y* )
	if [ "`uname`" = "Darwin" ]; then
	    source software-install-mac.sh
	elif [ "`uname`" = "Linux" ]; then
	    source software-install-linux.sh
	fi
	;;
    *  )
	echo "Don't install."
	;;
esac

#defalut shell change
ZSHPATH=`which zsh`
sudo sh -c "echo ${ZSHPATH} >> /etc/shells"
chsh -s ${ZSHPATH}

# textlintのインストール
npm i -g textlint textlint-rule-preset-japanese textlint-rule-prh textlint-rule-ja-no-redundant-expression

# anyenvのinit & installしたい*envのインストール
eval "$(anyenv init -)"
yes | anyenv install --init
ANYENV_INSTALL_TARGET=("rbenv" "pyenv" "nodenv")

for ANYENV_TARGET in "${ANYENV_INSTALL_TARGET[@]}"
do
    anyenv install ${ANYENV_TARGET}
done

# rbenvで最新バージョンをインストール
## https://mawatari.jp/archives/install-latest-stable-version-of-ruby-using-rbenv
RUBY_VER=`rbenv install -l | grep -v - | tail -1 | tr -d ' '`
rbenv install $RUBY_VER
rbenv global $RUBY_VER

# private file作成
touch ${HOME}/.zsh.d/zshrc_mac_private

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