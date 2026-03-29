#!/bin/bash -eu
set -o pipefail

cd "$(dirname "$0")"

OS_TYPE=$(uname)

# Step 1: Symlink dotfiles
/bin/bash .link_dir_and_file.sh

# Step 2: Install packages via Nix (preferred) or Homebrew (fallback)
if command -v nix >/dev/null 2>&1; then
  echo "Nix detected. Using nix-darwin for package management."

  # Ensure user-config.json exists
  if [ ! -f nix/user-config.json ] || grep -q "CHANGEME" nix/user-config.json; then
    echo "ERROR: nix/user-config.json needs to be configured."
    echo "  cp nix/user-config.json.example nix/user-config.json"
    echo "  Then edit with your username and hostname."
    exit 1
  fi

  if [ "${OS_TYPE}" = "Darwin" ]; then
    # macOS: nix-darwin manages system config, packages, and homebrew casks
    darwin-rebuild switch --flake .
  else
    # Linux: standalone home-manager
    home-manager switch --flake .#linux
  fi
else
  echo "Nix not found. Falling back to legacy installation."
  /bin/bash .software-install.sh

  if [ "${OS_TYPE}" = "Darwin" ]; then
    /bin/bash .mac-init.sh
  fi
fi

# Step 3: Shell and font setup
/bin/bash .default-shell-change.sh
/bin/bash .powerline-fonts-install.sh
