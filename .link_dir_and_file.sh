#!/bin/bash
set -euo pipefail

echo "[*] running .link_dir_and_file.sh"

link_dir_file() {
  local target_dir=$1
  local link_target_prefix=$2
  local abs_target_dir
  abs_target_dir=$(cd "$target_dir" && pwd)

  shopt -s nullglob
  for path in "$abs_target_dir"/*; do
    local name=${path##*/}
    local dest="${link_target_prefix}${name}"
    # 既にリンク済み（またはユーザーが別途置いたファイル/ディレクトリ）ならスキップする。
    # ディレクトリの場合、そのまま ln すると既存ディレクトリの下に更にリンクが作られてしまう。
    # ファイルの場合、ln が失敗して set -e で以降のリンクが作られなくなる（再実行時に困る）
    if [ -L "$dest" ] || [ -e "$dest" ]; then
      echo "${dest}: already exists, skip."
      continue
    fi
    ln -sv "$path" "$dest"
  done
  shopt -u nullglob
}

## 先頭に.をつけてリンクする対象一覧
DOT_LINK_FILE_DIR="DOT_LINK_TARGET"
link_dir_file "${DOT_LINK_FILE_DIR}" "${HOME}/."

## 先頭に.をつけず、そのままの名前でリンクする対象一覧
LINK_FILE_DIR="LINK_TARGET"
link_dir_file "${LINK_FILE_DIR}" "${HOME}/"
