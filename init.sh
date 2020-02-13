#!/bin/bash

cd "`dirname $0`" || exit

## 先頭に.をつけてリンクする対象一覧
DOT_LINK_FILE_DIR="DOT_LINK_TARGET"

cd $DOT_LINK_FILE_DIR || exit
# SC2045
for LINK in *
do
    [[ -e "$LINK" ]] || break
    ## TODO: 既にリンク済みの場合、その階層の下に更にリンクされる　要修正
    ln -sv "`pwd`/${LINK}" ${HOME}/.${LINK}
done
cd .. || exit

## 先頭に.をつけず、そのままの名前でリンクする対象一覧
LINK_FILE_DIR="LINK_TARGET"

cd $LINK_FILE_DIR || exit

for LINK in *
do
    [[ -e "$LINK" ]] || break
    ln -sv "`pwd`/${LINK}" ${HOME}
done
cd .. || exit

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

# rbenvで最新バージョンをインストール
## https://mawatari.jp/archives/install-latest-stable-version-of-ruby-using-rbenv
RUBY_VER=`rbenv install -l | grep -v - | tail -1 | tr -d ' '`
rbenv install $RUBY_VER
rbenv global $RUBY_VER

# private file作成
touch ${HOME}/.zsh.d/zshrc_mac_private
