#!/bin/bash -eu

cd "$(dirname "$0")"

/bin/bash .link_dir_and_file.sh

/bin/bash .software-install.sh

/bin/bash .default-shell-change.sh

# private file作成
touch "${HOME}/.zsh.d/zshrc_mac_private"

# powerline-fonts install
/bin/bash .powerline-fonts-install.sh
