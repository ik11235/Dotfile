# === PATH・環境変数 ===

# mise
set -gx PATH ~/.local/share/mise/shims $PATH

# === 外部ツール連携 ===

# google cloud sdkのPATH
if test -d (brew --prefix)"/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/"
  source (brew --prefix)/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.fish.inc
end

# To enable homebrew-command-not-found
set HOMEBREW_COMMAND_NOT_FOUND_HANDLER (brew --repository)/Library/Homebrew/command-not-found/handler.fish
if test -f $HOMEBREW_COMMAND_NOT_FOUND_HANDLER
  source $HOMEBREW_COMMAND_NOT_FOUND_HANDLER
end

# fzf
fzf --fish | source

# direnv
eval "$(direnv hook fish)"

# === キーバインド ===

# fish_key_bindings
set --global fish_key_bindings fish_default_key_bindings

# jethrokuan/fzf のdefaultキーバインド無効化
## https://github.com/jethrokuan/fzf/tree/8ee7cf502637a9dd7d0cd96ead67c631a25e49d9#quickstart
set -g FZF_LEGACY_KEYBINDINGS 0

#fisherパッケージdecors/fish-ghqの設定
## https://qiita.com/naname/items/00d4c81a98c017b0fb43
set GHQ_SELECTOR $AVAILABLE_FUZZY_FINDER

# === プロンプト・テーマ ===

# asdf x fishでrubyバージョン表示をOFFに
set -g theme_display_ruby no

## kubernetesのcontextとnamespaceを出す
### https://zenn.dev/tawachan/scraps/2f6884e68fc489
### TODO: 常に出るの邪魔なので管理系のディレクトリに入ったときだけonにしたい
set -g theme_display_k8s_context yes
set -g theme_display_k8s_namespace yes

# === ユーティリティ関数 ===

# history同期
## https://github.com/fish-shell/fish-shell/issues/825#issuecomment-203021964
function save_history --on-event fish_preexec
    history save
    history merge
end

## M1関係の設定
if test (uname -s) = "Darwin" && type arch > /dev/null
    alias x64='exec arch -arch x86_64 "$SHELL"'
    alias a64='exec arch -arch arm64e "$SHELL"'
    function switch-arch
        switch (uname -m)
          case arm64
            set arch x86_64
          case x86_64
            set arch arm64e
          case '*'
            echo "undefined architecture."
            return 1
        end

        exec arch -arch $arch "$SHELL"
    end
end

# === アプリ固有 ===

# Warpify SubShell
## https://docs.warp.dev/features/subshells
if set -q WARP_IS_LOCAL_SHELL_SESSION
    printf '\eP$f{"hook": "SourcedRcFileForWarp", "value": { "shell": "fish"}}\x9c'
end
