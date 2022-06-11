#!/bin/bash -eu

cd "$(dirname "$0")"

/bin/bash .link_dir_and_file.sh

/bin/bash .software-install.sh

/bin/bash .default-shell-change.sh

/bin/bash .mac-init.sh

# powerline-fonts install
/bin/bash .powerline-fonts-install.sh
