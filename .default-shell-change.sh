#!/bin/bash -eu

ZSH_PATH=$(command -v zsh)
result=0
grep "${ZSH_PATH}" /etc/shells >/dev/null || result=$?
if [ ! "${result}" = "0" ]; then
  sudo sh -c "echo ${ZSH_PATH} >> /etc/shells"
fi

chsh -s "${ZSH_PATH}"
