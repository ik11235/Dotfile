#!/bin/bash -eu

# Nix installation and configuration setup

cd "$(dirname "$0")"

OS_TYPE=$(uname)

# Install Nix if not present
if ! command -v nix >/dev/null 2>&1; then
  echo "Nix not found. Installing via Determinate Systems installer..."
  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --no-confirm
  # Load nix into current shell
  # shellcheck source=/dev/null
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
fi

# Generate user-config.json if not configured
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

  # configName: short alias for darwinConfigurations key (hide full hostname from git)
  # Must be set via NIX_CONFIG_NAME env var to match an existing nix/hosts/<configName>.nix
  CURRENT_CONFIG_NAME="${NIX_CONFIG_NAME:-}"
  if [ -z "${CURRENT_CONFIG_NAME}" ]; then
    echo "Error: NIX_CONFIG_NAME is not set. Set it to match a nix/hosts/<configName>.nix file."
    echo "Example: NIX_CONFIG_NAME=YD-macbookair bash .nix-setup.sh"
    exit 1
  fi

  cat > nix/user-config.json <<JSONEOF
{
  "username": "${CURRENT_USER}",
  "hostname": "${CURRENT_HOST}",
  "configName": "${CURRENT_CONFIG_NAME}",
  "system": "${CURRENT_SYSTEM}",
  "linuxUsername": "${CURRENT_USER}",
  "linuxHomeDirectory": "/home/${CURRENT_USER}"
}
JSONEOF
  echo "Generated nix/user-config.json:"
  cat nix/user-config.json

  # Prevent git from showing diff for user-specific values
  git update-index --skip-worktree nix/user-config.json
fi

# Apply Nix configuration
# On first run, darwin-rebuild/home-manager are not yet installed.
# Use `nix run` to bootstrap, then subsequent runs can use the direct commands.
# Use absolute path for --flake because sudo changes $HOME to /var/root
FLAKE_DIR="$(pwd)"
CONFIG_NAME="$(jq -r '.configName' nix/user-config.json)"

if [ "${OS_TYPE}" = "Darwin" ]; then
  if command -v darwin-rebuild >/dev/null 2>&1; then
    darwin-rebuild switch --flake "${FLAKE_DIR}#${CONFIG_NAME}"
  else
    echo "Bootstrapping nix-darwin (first run)..."
    sudo nix run nix-darwin#darwin-rebuild -- switch --flake "${FLAKE_DIR}#${CONFIG_NAME}"
  fi
else
  if command -v home-manager >/dev/null 2>&1; then
    home-manager switch --flake "${FLAKE_DIR}#linux"
  else
    echo "Bootstrapping home-manager (first run)..."
    nix run home-manager#home-manager -- switch --flake "${FLAKE_DIR}#linux"
  fi
fi
