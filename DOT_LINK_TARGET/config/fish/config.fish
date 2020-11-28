#https://qiita.com/naname/items/00d4c81a98c017b0fb43

# ~/.config/fish/config.fishに追加
#fisherパッケージdecors/fish-ghqの設定
set GHQ_SELECTOR $AVAILABLE_FUZZY_FINDER


# google cloud sdkのPATH
source /usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.fish.inc

eval (direnv hook fish)

## homebrew-command-not-found
set HB_CNF_HANDLER (brew --prefix)"/Homebrew/Library/Taps/homebrew/homebrew-command-not-found/handler.fish"
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

# anyenvのPATHをbrewの実行時の対象から除外する
## https://www.null-engineer.com/2019/02/08/anyenv%E3%82%A4%E3%83%B3%E3%82%B9%E3%83%88%E3%83%BC%E3%83%AB%E6%B8%88%E3%81%BF%E3%81%AEmac%E3%81%A7brew-doctor%E3%82%92%E5%AE%9F%E8%A1%8C%E3%81%97%E3%81%9F%E3%82%89warning%E3%81%8C%E5%87%BA%E3%82%8B/
## phpenv等でも出るらしいので、anyenv管理のものは一律除外
## https://qiita.com/takc923/items/45386905f70fde9af0e7

set NOT_ANYENV_PATH ""

for tmp_path in (string split : $PATH)
    if ! string match '*/.anyenv/*' $tmp_path >> /dev/null
        set NOT_ANYENV_PATH $NOT_ANYENV_PATH $tmp_path
    end
end

alias brew="env PATH=$NOT_ANYENV_PATH brew"
