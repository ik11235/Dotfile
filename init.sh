<<<<<<< HEAD
#!/bin/bash -eu
=======
#!/bin/bash
cd `dirname $0`
LINKFILE=(".emacs.d" ".zshrc" ".zsh.d" ".aspell.conf")
INSTALL_PAK=("zsh" "aspell" "tmux" "npm")
>>>>>>> ead9c68 (livedownを追加)

cd "$(dirname "$0")"

/bin/bash .link_dir_and_file.sh

/bin/bash .software-install.sh

#npmによるインストール
NPM_INSTALL_PAK=("livedown")
for PAK in ${INSTALL_PAK[@]}
do
    npm install -g ${PAK}
done

#livedownが起動しない問題への対応
##http://stackoverflow.com/questions/26320901/cannot-install-nodejs-usr-bin-env-node-no-such-file-or-directory
sudo ln -s /usr/bin/nodejs /usr/bin/node


#defalut shell change
ZSHPATH=$(which zsh)
sudo sh -c "echo ${ZSHPATH} >> /etc/shells"
chsh -s "${ZSHPATH}"

/bin/bash .anyenv-init-and-install.sh

# private file作成
touch "${HOME}/.zsh.d/zshrc_mac_private"

# powerline-fonts install
/bin/bash .powerline-fonts-install.sh
