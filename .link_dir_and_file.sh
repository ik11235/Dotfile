#!/bin/bash -eu
set -o pipefail

echo "[*] running .link_dir_and_file.sh"

link_dir_file() {
  local target_dir=$1
  local link_target_prefix=$2
  local abs_target_dir
  abs_target_dir=$(cd "$target_dir" && pwd)

  shopt -s nullglob
  for path in "$abs_target_dir"/*; do
    local name=${path##*/}
    # 既にリンク済みの場合、そのディレクトリの階層の下に更にリンクされるので事前にディレクトリの存在有無をチェックする
    # ファイルの場合、ln側で自動的に重複で止まるのでチェックは不要
    if [ -d "${link_target_prefix}${name}" ]; then
      echo "${link_target_prefix}${name}: Directory exists."
      continue
    fi
    ln -sv "$path" "${link_target_prefix}${name}"
  done
  shopt -u nullglob
}

## 先頭に.をつけてリンクする対象一覧
DOT_LINK_FILE_DIR="DOT_LINK_TARGET"
link_dir_file "${DOT_LINK_FILE_DIR}" "${HOME}/."

## 先頭に.をつけず、そのままの名前でリンクする対象一覧
LINK_FILE_DIR="LINK_TARGET"
link_dir_file "${LINK_FILE_DIR}" "${HOME}/"
