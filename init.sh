#!/bin/bash
cd `dirname $0`
LINKFILE=(".emacs.d/" ".zshrc" ".zsh.d/" ".aspell.conf" ".gitignore" ".textlintrc")
INSTALL_PAK=("zsh" "aspell" "tmux" "npm" "coreutils" "rbenv" "ruby-build")

for LINK in ${LINKFILE[@]}
do
    ln -s `pwd`/${LINK} ${HOME}/
done

echo "Do you want to install a package ? [Y/n]"
read ANSWER

ANSWER=`echo $ANSWER | tr y Y | tr -d '[\[\]]'`
case $ANSWER in
    ""|Y* )
	if [ `uname` = "Darwin" ]; then
	    source software-install-mac.sh
	elif [ `uname` = "Linux" ]; then
	    source software-install-linux.sh
	fi
	;;
    *  )
	echo "Don't install."
	;;
esac

#git global config
git config --global core.excludesfile ~/.gitignore

#defalut shell change
ZSHPATH=`which zsh`
sudo sh -c "echo ${ZSHPATH} >> /etc/shells"
chsh -s ${ZSHPATH}

# textlintのインストール
npm i -g textlint textlint-rule-preset-japanese textlint-rule-prh textlint-rule-ja-no-redundant-expression

# command-not-foundのインストール
brew tap homebrew/command-not-found

# rbenvで最新バージョンをインストール
## https://mawatari.jp/archives/install-latest-stable-version-of-ruby-using-rbenv
RUBY_VER=`rbenv install -l | grep -v - | tail -1 | tr -d ' '`
rbenv install $RUBY_VER
rbenv global $RUBY_VER

# gcloud install
brew cask install google-cloud-sdk
