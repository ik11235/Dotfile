#!/bin/bash -eu

echo "Do you want to install a package ? [Y/n]"
read -r ANSWER

ANSWER=$(echo "$ANSWER" | tr y Y)
case $ANSWER in
"" | Y*)
  if [ "$(uname)" = "Darwin" ]; then
    # 実行環境がLinuxの場合のインストール処理

    # brewのインストールの有無をチェック
    # インストールされていない場合インストール
    if ! type brew >/dev/null; then
      echo "not Install brew."
      echo "Start install brew"
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
    fi

    # この処理の前にlink済みであるはずのBrewfileを元にinstall
    brew bundle --global
  elif [ "$(uname)" = "Linux" ]; then
    # 実行環境がLinuxの場合のインストール処理
    # TODO: ディストリビューションごとにyumとaptを制御する

    echo "Linux sh"
    echo "${INSTALL_PAK[@]}"
  fi
  ;;
*)
  echo "Don't install."
  ;;
esac
