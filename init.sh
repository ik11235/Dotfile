#!/bin/sh
cd `dirname $0`

for FILE in ".emacs.d" ".zshrc" ".zsh.d" ".aspell.conf"
do
    ln -s `pwd`/${FILE} ${HOME}/${FILE}
done

if [ `uname` = "Darwin" ]; then
   #mac用のコード
   brew install --with-lang-en aspell
elif [ `uname` = "Linux" ]; then
   #Linux用のコード
   #TODO ディストリビューションごとにyumとaptを制御する
   sudo apt-get install aspell
fi

#$ find . -mindepth 1  -maxdepth 1 ! -name .git -a ! -name README.md -print0 |sed -e s/\.// |xargs -0 -I % echo "ln -s `pwd`/% ${HOME}/%"
