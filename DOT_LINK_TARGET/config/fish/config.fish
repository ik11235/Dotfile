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

# direnv
## https://github.com/direnv/direnv/blob/master/docs/hook.md#fish
direnv hook fish | source

## homebrew-command-not-found
set HB_CNF_HANDLER (brew --prefix)"/Library/Taps/homebrew/homebrew-command-not-found/handler.fish"
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


# asdf
# ASDF configuration code
if test -z $ASDF_DATA_DIR
    set _asdf_shims "$HOME/.asdf/shims"
else
    set _asdf_shims "$ASDF_DATA_DIR/shims"
end

# Do not use fish_add_path (added in Fish 3.2) because it
# potentially changes the order of items in PATH
if not contains $_asdf_shims $PATH
    set -gx --prepend PATH $_asdf_shims
end
set --erase _asdf_shims

. ~/.asdf/plugins/golang/set-env.fish

# anyenvのPATHをbrewの実行時の対象から除外する
## https://www.null-engineer.com/2019/02/08/anyenv%E3%82%A4%E3%83%B3%E3%82%B9%E3%83%88%E3%83%BC%E3%83%AB%E6%B8%88%E3%81%BF%E3%81%AEmac%E3%81%A7brew-doctor%E3%82%92%E5%AE%9F%E8%A1%8C%E3%81%97%E3%81%9F%E3%82%89warning%E3%81%8C%E5%87%BA%E3%82%8B/
## phpenv等でも出るらしいので、anyenv管理のものは一律除外
## https://qiita.com/takc923/items/45386905f70fde9af0e7

set NOT_ANYENV_PATH ""

for tmp_path in (string split : $PATH)
    if ! string match '*/.asdf/*' $tmp_path >> /dev/null
        set NOT_ANYENV_PATH $NOT_ANYENV_PATH $tmp_path
    end
end

alias brew="env PATH=$NOT_ANYENV_PATH (which brew)"

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
