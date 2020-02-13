#!/bin/bash

cd "`dirname $0`" || exit
LINKFILE=(".emacs.d/" ".zshrc" ".zsh.d/" ".aspell.conf" ".config" ".textlintrc" "Brewfile" ".gitconfig")

for LINK in "${LINKFILE[@]}"
do
    ln -s "`pwd`/${LINK}" ${HOME}
done

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
