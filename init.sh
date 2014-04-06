#!/bin/sh
cd `dirname $0`
#pwd
for FILE in ".emacs.d" ".zshrc"
do
    ln -s `pwd`/${FILE} ${HOME}/${FILE}
done

#$ find . -mindepth 1  -maxdepth 1 ! -name .git -a ! -name README.md -print0 |sed -e s/\.// |xargs -0 -I % echo "ln -s `pwd`/% ${HOME}/%"
