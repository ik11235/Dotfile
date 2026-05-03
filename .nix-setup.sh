#!/bin/bash -eu
set -o pipefail

# 最小 Nix セットアップ:
# 1. Nix が未インストールなら Determinate Systems インストーラで導入
# 2. flake.nix の default パッケージを nix profile に install
#
# init.sh からは呼ばない（Nix 導入はホスト全体に影響する大きな副作用のため）。
# 利用者が明示的に `bash .nix-setup.sh` を実行する想定。

cd "$(dirname "$0")"

if ! command -v nix >/dev/null 2>&1; then
  echo "[*] Installing Nix via Determinate Systems installer..."
  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install --determinate
  # インストール直後の現シェルでは nix コマンドにパスが通っていないため source する
  if [ -f /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
    # shellcheck disable=SC1091
    . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
  fi
else
  echo "[*] Nix is already installed: $(nix --version)"
fi

echo "[*] Installing CLI tools from flake (.#default)..."
nix --extra-experimental-features 'nix-command flakes' \
  profile install ".#default"

echo "[*] Done. Verify with: nix profile list"
