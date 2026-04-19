#!/bin/bash -eu
set -o pipefail

cd "$(dirname "$0")"

/bin/bash .link_dir_and_file.sh

/bin/bash .software-install.sh

/bin/bash .default-shell-change.sh

if [ "$(uname)" = "Darwin" ]; then
  /bin/bash .mac-init.sh
fi

# powerline-fonts install
/bin/bash .powerline-fonts-install.sh
