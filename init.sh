#!/bin/bash
cd `dirname $0`
LINKFILE=(".emacs.d" ".zshrc" ".zsh.d" ".aspell.conf")
INSTALL_PAK=("zsh" "aspell" "tmux")

for LINK in ${LINKFILE[@]}
do
    ln -s `pwd`/${LINK} ${HOME}/${LINK}
done

if [ `uname` = "Darwin" ]; then
	#mac用のコード
	for PAK in ${INSTALL_PAK[@]}
	do
		brew install ${PAK}
	done
elif [ `uname` = "Linux" ]; then
	#Linux用のコード
	#TODO ディストリビューションごとにyumとaptを制御する
	sudo apt-get install ${INSTALL_PAK[@]}
fi

#defalut shell change
ZSHPATH=`which zsh`
chsh -s ${ZSHPATH}
