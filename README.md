dotfile
==================================

[![shellscript-syntax-check](https://github.com/ik11235/Dotfile/workflows/shellscript-syntax-check/badge.svg)](https://github.com/ik11235/Dotfile/actions?query=workflow%3Ashellscript-syntax-check)

# 導入予定

* emacs
* tmux
* zsh
* fish
* (ssh)


# インストール方法

```shell script
 git clone https://github.com/ik11235/Dotfile.git ./dotfile
 ./dotfile/init.sh
```

## use ghq

```shell script
 ghq get https://github.com/ik11235/Dotfile.git
 cd "$( ghq list --full-path | grep ik11235/Dotfile)"
 ./init.sh
 cd -
```

OR

```shell script
git clone https://github.com/ik11235/Dotfile.git ~/ghq/github.com/ik11235/Dotfile
~/ghq/github.com/ik11235/Dotfile/init.sh
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
<<<<<<< HEAD
- yasnippet
=======
- livedown

## tmux
>>>>>>> ead9c68 (livedownを追加)

## zsh

 .zshrcでは以下のOSごとのファイル読み込みのみを行う
- zshrc_global すべてのOS対象のファイル
- zshrc_linux Linux用のファイル
- zshrc_mac mac用のファイル

## fish

- 起動シェルはzshにしつつ、zshから呼び出すことを想定している

## init.sh
<<<<<<< HEAD

 以下を行うスクリプト
 
 - DOT_LINK_TARGETディレクトリにあるファイルは.付きでUSER_HOME以下にシンボリックリンクを貼る(.configや.zsh.d等)
 - LINK_TARGETディレクトリにあるファイルはそのままの名前でUSER_HOME以下にシンボリックリンクを貼る(Brewfile等)
 
 - その後、必要な設定やソフトウェアのインストールを行う
     - (現在、ソフトウェアのインストールはmacのみ対応 / LinuxにもLinuxBrew等で対応を検討中)
=======
 dotfileルート以下のファイルをチェックして全てをUSER_HOME以下にシンボリックリンクをはるスクリプト

 現在は対象ファイルは直打ち(そのうち自動検査型に変更)
>>>>>>> ead9c68 (livedownを追加)
