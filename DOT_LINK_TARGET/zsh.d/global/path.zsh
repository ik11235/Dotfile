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
)
