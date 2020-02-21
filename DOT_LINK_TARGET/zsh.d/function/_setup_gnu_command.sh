#!/bin/bash

## GNUコマンド補完用
case "${OSTYPE}" in
# Mac(Unix)
darwin*)
  ### GNU系コマンドを前提にこのスクリプトは組んでいるので、BSD系が基準のMacのコマンドが使われないように明記する
  DATE_CMD=$(which gdate)
  ;;
# Linux
linux*)
  DATE_CMD=$(which date)
  ;;
esac
