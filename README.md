dotfile
==================================

# 導入予定
* emacs
* tmux
* zsh
* (ssh)


# インストール方法
    git clone https://github.com/ik11235/Dotfile.git ./dotfile
    ./dotfile/init.sh

# 各設定ファイルについて
## emacs
- 要 emacs 24以上

 emacsの各設定を拡張ごとにファイルを分割して記述

 基本的には、package.elで追加する

 以下のパッケージを自動インストール
- init-loader
- helm
- markdown-mode

## tmux

## zsh

## init.sh
 dotfileルート以下のファイルをチェックして全てをUSER_HOME以下にシンボリックリンクをはるスクリプト
 
 現在は対象ファイルは直打ち(そのうち自動検査型に変更)
