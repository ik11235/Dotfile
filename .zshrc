bindkey -e
HISTFILE=$HOME/.zsh-history           # 履歴をファイルに保存する
HISTSIZE=100000                       # メモリ内の履歴の数
SAVEHIST=100000                       # 保存される履歴の数
setopt extended_history               # 履歴ファイルに時刻を記録
function history-all { history -E 1 } # 全履歴の一覧を出力する
setopt share_history                  # 履歴の共有

setopt PROMPT_SUBST #色つけ設定
RPROMPT="[%d]"   #右プロンプト設定
PROMPT="%n@%m%% "   #プロンプト設定

case "${OSTYPE}" in
# Mac(Unix)
darwin*)
    # ここに設定
    ;;  
# Linux
linux*)
	alias ls='ls --color=auto'
	alias rits='sudo pon dsl-provider'
	source "/etc/zsh_command_not_found"
	#Start tmux on every shell login
	#https://wiki.archlinux.org/index.php/Tmux#Start_tmux_on_every_shell_login
	if which tmux 2>&1 >/dev/null; then
	    #if not inside a tmux session, and if no session is started, start a new session
	    test -z "$TMUX" && (tmux attach || tmux new-session)
	fi
	#tmux設定
	DISPLAY=`tmux show-environment |grep DISPLAY=|cut -d "=" -f 2`
	if [ -n "$DISPLAY" ]; then
	    export DISPLAY=${DISPLAY}
	else
	    echo "non DISPLAY number">>/dev/null
	fi
    ;;  
esac


##go言語設定
export GOROOT=$HOME/go
export PATH=$PATH:$GOROOT/bin
# The next line updates PATH for the Google Cloud SDK.
export PATH=/home/yuichi/google-cloud-sdk/bin:$PATH


###ここからhttp://qiita.com/uasi/items/c4288dd835a65eb9d709より引用
# 自動補完を有効にする
# コマンドの引数やパス名を途中まで入力して <Tab> を押すといい感じに補完してくれる
# 例： `cd path/to/<Tab>`, `ls -<Tab>`
autoload -U compinit; compinit
# 入力したコマンドが存在せず、かつディレクトリ名と一致するなら、ディレクトリに cd する
# 例： /usr/bin と入力すると /usr/bin ディレクトリに移動
setopt auto_cd

# cd した先のディレクトリをディレクトリスタックに追加する
# ディレクトリスタックとは今までに行ったディレクトリの履歴のこと
# `cd +<Tab>` でディレクトリの履歴が表示され、そこに移動できる
setopt auto_pushd

# pushd したとき、ディレクトリがすでにスタックに含まれていればスタックに追加しない
setopt pushd_ignore_dups

# 拡張 glob を有効にする
# glob とはパス名にマッチするワイルドカードパターンのこと
# （たとえば `mv hoge.* ~/dir` における "*"）
# 拡張 glob を有効にすると # ~ ^ もパターンとして扱われる
# どういう意味を持つかは `man zshexpn` の FILENAME GENERATION を参照
setopt extended_glob

# 入力したコマンドがすでにコマンド履歴に含まれる場合、履歴から古いほうのコマンドを削除する
# コマンド履歴とは今まで入力したコマンドの一覧のことで、上下キーでたどれる
setopt hist_ignore_all_dups

# コマンドがスペースで始まる場合、コマンド履歴に追加しない
# 例： <Space>echo hello と入力
setopt hist_ignore_space

# <Tab> でパス名の補完候補を表示したあと、
# 続けて <Tab> を押すと候補からパス名を選択できるようになる
# 候補を選ぶには <Tab> か Ctrl-N,B,F,P
zstyle ':completion:*:default' menu select=1

# 単語の一部として扱われる文字のセットを指定する
# ここではデフォルトのセットから / を抜いたものとする
# こうすると、 Ctrl-W でカーソル前の1単語を削除したとき、 / までで削除が止まる
WORDCHARS='*?_-.[]~=&;!#$%^(){}<>'

# The next line updates PATH for the Google Cloud SDK.
###source /Users/yuichi/google-cloud-sdk/path.bash.inc
sdk_dir="${HOME}/google-cloud-sdk"
bin_path="$sdk_dir/bin"
export PATH=$bin_path:$PATH

# The next line enables bash completion for gcloud.
source ${HOME}/google-cloud-sdk/completion.zsh.inc

##brew 補完
#source /usr/local/Library/Contributions/brew_zsh_completion.zsh
