#https://qiita.com/naname/items/00d4c81a98c017b0fb43

# ~/.config/fish/config.fishに追加
#fisherパッケージdecors/fish-ghqの設定
set GHQ_SELECTOR $AVAILABLE_FUZZY_FINDER

# jethrokuan/fzf のdefaultキーバインド無効化
## https://github.com/jethrokuan/fzf/tree/8ee7cf502637a9dd7d0cd96ead67c631a25e49d9#quickstart
set -U FZF_LEGACY_KEYBINDINGS 0

# google cloud sdkのPATH
if test -d (brew --prefix)"/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/"
  source (brew --prefix)/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.fish.inc
end

# To enable homebrew-command-not-found
set HB_CNF_HANDLER (brew --repository)"/Library/Taps/homebrew/homebrew-command-not-found/handler.fish"
if test -f $HB_CNF_HANDLER
  source $HB_CNF_HANDLER
end

#source /usr/local/share/fish/vendor_completions.d/*.fish

# history同期
## https://github.com/fish-shell/fish-shell/issues/825#issuecomment-203021964
function save_history --on-event fish_preexec
    history save
    history marge
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

# asdf x fishでrubyバージョン表示をOFFに
set -g theme_display_ruby no

# Warpify SubShell
## https://docs.warp.dev/features/subshells
if set -q WARP_IS_LOCAL_SHELL_SESSION
    printf '\eP$f{"hook": "SourcedRcFileForWarp", "value": { "shell": "fish"}}\x9c'
end

# fzf
fzf --fish | source

## kubernetesのcontextとnamespaceを出す
### https://zenn.dev/tawachan/scraps/2f6884e68fc489
### TODO: 常に出るの邪魔なので管理系のディレクトリに入ったときだけonにしたい
set -g theme_display_k8s_context yes
set -g theme_display_k8s_namespace yes

# mise
set -gx PATH ~/.local/share/mise/shims $PATH

# direnv
eval "$(direnv hook fish)"
