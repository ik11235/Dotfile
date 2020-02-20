#!/bin/bash

## https://qiita.com/TanukiTam/items/6572ea18c2de80ebf458

# 日付大小比較
# arg1:'yyyy/mm/dd hh:mm:ss'
# arg2:'yyyy/mm/dd hh:mm:ss'
# 1が2より大きい場合、 +の数値を $ret に入れる
# 1が2より小さい場合、 -の数値を $ret に入れる
# 1が2と同じ大きさの場合、0 を $retに入れる
function dateComp()
{
    # 1970/01/01 00:00:00 からの経過秒に変換
    ARG1_SECOND=`${DATE_CMD} -d "$1" '+%s'`
    ARG2_SECOND=`${DATE_CMD} -d "$2" '+%s'`

    # 差を返却
    expr $ARG1_SECOND - $ARG2_SECOND
}
