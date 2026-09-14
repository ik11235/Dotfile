# PATH設定
## (以降のPATH通ってる前提のスクリプト等を通すため)
typeset -gU path PATH
path=(
  ## M1 brew
  /opt/homebrew/bin(N-/)
  /opt/homebrew/sbin(N-/)
  ## x64 brew
  /usr/local/bin(N-/)
  /usr/local/sbin(N-/)
  ## .bin(DOT_LINK_TARGET/bin)をPATHに追加
  $HOME/.bin(N-/)
  ## Android platform-tools
  ### Android Studioのパスがあればそれを使用する
  $HOME/Library/Android/sdk/platform-tools(N-/)

  $path

  ## Docker Desktop の CLI（docker 本体と cli-plugins）
  ### Docker Desktop が ~/.zprofile 等へ直接追記してくるのを避け、ここで一元管理する
  $HOME/.docker/bin(N-/)
)
