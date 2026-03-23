# プロンプト表示設定（PROMPT、RPROMPT、gitブランチ情報）

setopt PROMPT_SUBST
PROMPT="%n@%m%% "

#gitブランチ情報の表示設定
##http://yoshiko.hatenablog.jp/entry/2014/04/02/zsh%E3%81%AE%E3%83%97%E3%83%AD%E3%83%B3%E3%83%97%E3%83%88%E3%81%ABgit%E3%81%AE%E3%82%B9%E3%83%86%E3%83%BC%E3%82%BF%E3%82%B9%E3%82%92%E3%82%B7%E3%83%B3%E3%83%97%E3%83%AB%E5%8F%AF%E6%84%9B%E3%81%8F
##http://kitak.hatenablog.jp/entry/2013/05/25/103059

# VCSの情報を取得するzshの便利関数 vcs_infoを使う
autoload -Uz vcs_info

# 表示フォーマットの指定
# %b ブランチ情報
# %a アクション名(mergeなど)
zstyle ':vcs_info:*' formats '[%b]'
zstyle ':vcs_info:*' actionformats '[%b|%a]'
precmd () {
    psvar=()
    LANG=en_US.UTF-8 vcs_info
    [[ -n "$vcs_info_msg_0_" ]] && psvar[1]="$vcs_info_msg_0_"
}

# バージョン管理されているディレクトリにいれば表示，そうでなければ非表示
RPROMPT="%1(v|%F{green}%1v%f|)[%d]"
