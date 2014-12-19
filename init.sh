#!/bin/bash
cd `dirname $0`
LINKFILE=(".emacs.d" ".zshrc" ".zsh.d" ".aspell.conf")
INSTALL_PAK=("texlive-extra-utils" "texlive-lang-japanese" "zsh" "aspell" "tmux" "make" "g++" "ruby-all-dev" "bundler")

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
exit

#defalut shell change
ZSHPATH=`which zsh`
chsh -s ${ZSHPATH}
