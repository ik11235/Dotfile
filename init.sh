#!/bin/bash -eu

cd "$(dirname "$0")"

OS_TYPE=$(uname)

# Step 1: Symlink dotfiles
/bin/bash .link_dir_and_file.sh

# Step 2: Install Nix if not present
if ! command -v nix >/dev/null 2>&1; then
  echo "Nix not found. Installing via Determinate Systems installer..."
  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm
  # Load nix into current shell
  # shellcheck source=/dev/null
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
fi

# Step 3: Configure user-config.json
if [ ! -f nix/user-config.json ] || grep -q "CHANGEME" nix/user-config.json; then
  echo "Setting up nix/user-config.json..."
  CURRENT_USER=$(whoami)
  CURRENT_HOST=$(hostname -s)
  CURRENT_SYSTEM="$(uname -m)-$(uname -s | tr '[:upper:]' '[:lower:]')"
  # Map to Nix system names
  case "${CURRENT_SYSTEM}" in
    arm64-darwin) CURRENT_SYSTEM="aarch64-darwin" ;;
    x86_64-darwin) CURRENT_SYSTEM="x86_64-darwin" ;;
    x86_64-linux) CURRENT_SYSTEM="x86_64-linux" ;;
    aarch64-linux) CURRENT_SYSTEM="aarch64-linux" ;;
  esac

  cat > nix/user-config.json <<JSONEOF
{
  "username": "${CURRENT_USER}",
  "hostname": "${CURRENT_HOST}",
  "system": "${CURRENT_SYSTEM}",
  "linuxUsername": "${CURRENT_USER}",
  "linuxHomeDirectory": "/home/${CURRENT_USER}"
}
JSONEOF
  echo "Generated nix/user-config.json:"
  cat nix/user-config.json
fi

# Step 4: Apply Nix configuration
if [ "${OS_TYPE}" = "Darwin" ]; then
  # macOS: nix-darwin manages system config, packages, and homebrew casks
  darwin-rebuild switch --flake .
else
  # Linux: standalone home-manager
  home-manager switch --flake .#linux
fi

# Step 3: Shell and font setup
/bin/bash .default-shell-change.sh
/bin/bash .powerline-fonts-install.sh
