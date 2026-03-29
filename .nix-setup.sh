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

  # Prevent git from showing diff for user-specific values
  git update-index --skip-worktree nix/user-config.json
fi

# Apply Nix configuration
# On first run, darwin-rebuild/home-manager are not yet installed.
# Use `nix run` to bootstrap, then subsequent runs can use the direct commands.
# Use absolute path for --flake because sudo changes $HOME to /var/root
FLAKE_DIR="$(pwd)"

if [ "${OS_TYPE}" = "Darwin" ]; then
  if command -v darwin-rebuild >/dev/null 2>&1; then
    darwin-rebuild switch --flake "${FLAKE_DIR}"
  else
    echo "Bootstrapping nix-darwin (first run)..."
    sudo nix run nix-darwin#darwin-rebuild -- switch --flake "${FLAKE_DIR}"
  fi
else
  if command -v home-manager >/dev/null 2>&1; then
    home-manager switch --flake "${FLAKE_DIR}#linux"
  else
    echo "Bootstrapping home-manager (first run)..."
    nix run home-manager#home-manager -- switch --flake "${FLAKE_DIR}#linux"
  fi
fi
