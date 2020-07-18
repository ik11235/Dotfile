#!/bin/bash -eu

function link_dir_file() {
  (
    TARGET_DIR=$1
    LINK_TARGET_PREFIX=$2

    cd "$TARGET_DIR"

    # SC2045
    for LINK in *; do
      [[ -e "$LINK" ]] || break
      # 既にリンク済みの場合、そのディレクトリの階層の下に更にリンクされるので事前にディレクトリの存在有無をチェックする
      # ファイルの場合、ln側で自動的に重複で止まるのでチェックは不要
      if [ -d "${LINK_TARGET_PREFIX}${LINK}" ]; then
        echo "${LINK_TARGET_PREFIX}${LINK}: Directory exists."
        continue
      fi
      ln -sv "$(pwd)/${LINK}" "${LINK_TARGET_PREFIX}${LINK}"
    done
  )
}

## 先頭に.をつけてリンクする対象一覧
DOT_LINK_FILE_DIR="DOT_LINK_TARGET"
link_dir_file "${DOT_LINK_FILE_DIR}" "${HOME}/."

## 先頭に.をつけず、そのままの名前でリンクする対象一覧
LINK_FILE_DIR="LINK_TARGET"
link_dir_file "${LINK_FILE_DIR}" "${HOME}/"
