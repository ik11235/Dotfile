#!/bin/sh
cd `dirname $0`
LINKFILE=(".emacs.d" ".zshrc" ".zsh.d" ".aspell.conf")
INSTALL_PAK=("aspell")

for LINK in ${LINKFILE[@]}
do
    ln -s `pwd`/${LINK} ${HOME}/${LINK}
done

for PAK in ${INSTALL_PAK[@]}
do
    if [ `uname` = "Darwin" ]; then
	#mac用のコード
	brew install ${PAK}
    elif [ `uname` = "Linux" ]; then
	#Linux用のコード
	#TODO ディストリビューションごとにyumとaptを制御する
	sudo apt-get install ${PAK}
    fi
done
