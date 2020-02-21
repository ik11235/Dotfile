#!/bin/bash

function coloer_echo_red() {
  echo -e "\033[0;31m${1}\033[0;39m"
}

function coloer_echo_white_bg_red() {
  echo -e "\033[41;37m${1}\033[0;39m"
}
