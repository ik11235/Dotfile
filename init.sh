#!/bin/bash -eu
set -o pipefail

cd "$(dirname "$0")"

# Step 1: Symlink dotfiles
/bin/bash .link_dir_and_file.sh

# Step 2: Install Nix and apply configuration
/bin/bash .nix-setup.sh

# Step 3: Shell and font setup
/bin/bash .default-shell-change.sh
/bin/bash .powerline-fonts-install.sh
