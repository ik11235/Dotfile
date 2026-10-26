#!/bin/bash
set -euo pipefail

echo "[*] running .software-install.sh"

echo "Do you want to install a package ? [Y/n]"
# stdin が閉じていて read が失敗しても set -e で止めない。
# 末尾に改行の無い入力 (printf n | ... や n の直後に Ctrl-D) でも read は 1 を返すが
# 読めた分は ANSWER に入っているので上書きしない。
# stdin の fd 自体が閉じている (<&-) と read は何も代入せず失敗し set -u で落ちるため、先に空で初期化しておく
# (空のまま = 既定の Y)
ANSWER=""
read -r ANSWER || true
ANSWER=$(echo "$ANSWER" | tr y Y)

OS_TYPE=$(uname)
case $ANSWER in
"" | Y*)
  if [ "${OS_TYPE}" = "Darwin" ]; then
    # 実行環境がMacOSの場合のインストール処理

    # brewのインストールの有無をチェック
    # インストールされていない場合インストール
    if ! type brew >/dev/null; then
      echo "not Install brew."
      echo "Start install brew"
      /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install.sh)"
    fi

    # この処理の前にlink済みであるはずのBrewfileを元にinstall
    brew bundle --global
  elif [ "${OS_TYPE}" = "Linux" ]; then
    # Linux のパッケージインストールは未実装のため skip
    # TODO: ディストリビューションごとに apt / dnf / pacman を切り分けて実装する
    echo "Warning: Linux のパッケージインストールは未実装のため skip します。" >&2
  else
    # 上記に当てはまらない環境の場合
    # TODO: 必要に応じて処理を書く
    echo "It's running on an unexpected OS." >&2
    echo "uname result: ${OS_TYPE}" >&2
    exit 1
  fi
  ;;
*)
  echo "Don't install."
  ;;
esac
