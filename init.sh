#!/bin/bash
# 各サブスクリプトは `/bin/bash script` 形式で呼ぶため shebang のフラグは無視される。
# そのため各スクリプト側で set -euo pipefail を明示している
set -euo pipefail

cd "$(dirname "$0")"

/bin/bash .link_dir_and_file.sh

/bin/bash .software-install.sh

/bin/bash .default-shell-change.sh

if [ "$(uname)" = "Darwin" ]; then
  /bin/bash .mac-init.sh
fi

# powerline-fonts install
/bin/bash .powerline-fonts-install.sh
