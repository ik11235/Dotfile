dotfile
==================================

# 導入予定

* emacs
* tmux
* zsh
* (ssh)


# インストール方法

```shell script
 git clone git@github.com:ik11235/Dotfile.git ./dotfile
 ./dotfile/init.sh
```

## use ghq

```shell script
 ghq get git@github.com:ik11235/Dotfile.git
 cd "$( ghq list --full-path | grep ik11235/Dotfile)"
 ./init.sh
 cd -
```

# 各設定ファイルについて

## emacs

- 要 emacs 24以上

 emacsの各設定を拡張ごとにファイルを分割して記述

 基本的には、package.elで追加する

 以下のパッケージを自動インストール
- init-loader
- helm
- markdown-mode
- magit
- yasnippet

## tmux

## zsh

 .zshrcでは以下のOSごとのファイル読み込みのみを行う
- zshrc_global すべてのOS対象のファイル
- zshrc_linux Linux用のファイル
- zshrc_mac mac用のファイル

## init.sh

 以下を行うスクリプト
 
 - DOT_LINK_TARGETディレクトリにあるファイルは.付きでUSER_HOME以下にシンボリックリンクを貼る(.configや.zsh.d等)
 - LINK_TARGETディレクトリにあるファイルはそのままの名前でUSER_HOME以下にシンボリックリンクを貼る(Brewfile等)
 
 - その後、必要な設定やソフトウェアのインストールを行う
     - (現在、ソフトウェアのインストールはmacのみ対応 / LinuxにもLinuxBrew等で対応を検討中)
