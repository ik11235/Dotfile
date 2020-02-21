#!/bin/bash

## args1 target git dir
function git-diff-check() {
  (
    cd "$(dirname "$1")" || exit
    git fetch
    local_time=$(git log master -n 1 --pretty=format:"%cd" --date=iso)
    remote_time=$(git log origin/master -n 1 --pretty=format:"%cd" --date=iso)

    echo $(dateComp "$remote_time" "$local_time")
    #echo "${diff_time}s ずれている。"
  )
}

## args1 target git dir
function git_update_check() {
  (
    cd "$(dirname "$1")" || exit
    GIT_ROOT=$(git rev-parse --show-superproject-working-tree --show-toplevel | head -1)
    cd $GIT_ROOT || exit

    TIME_CHECK_FILE="${GIT_ROOT}/.last_check_time"

    if [[ -e ${TIME_CHECK_FILE} ]]; then
      LAST_CHECK_TIME=$(cat ${TIME_CHECK_FILE})
      NOW_TIME=$(${DATE_CMD} '+%s')

      DIFF_TIME=$(dateComp "${NOW_TIME}" "${LAST_CHECK_TIME}")

      ## 毎回git-diff-checkを走れせるとfetchでそこそこ時間がかかる
      ## 60*60*24=86400秒以上たっていればチェックを走らせる
      ## 立っていなければここでstop
      if [ "${DIFF_TIME}" -lt "86400" ]; then
        return
      fi
    fi

    DIFF=$(git-diff-check "$1")
    if [ "${DIFF}" -ne "0" ]; then
      coloer_echo_white_bg_red "${GIT_ROOT}は${DIFF}秒、originと差分が存在します。x"
    fi

    ${DATE_CMD} '+%s' >${TIME_CHECK_FILE}
  )
}
