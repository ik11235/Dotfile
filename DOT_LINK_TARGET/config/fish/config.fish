#https://qiita.com/naname/items/00d4c81a98c017b0fb43

# ~/.config/fish/config.fishに追加
#fisherパッケージoh-my-fish/plugin-pecoの設定
function fish_user_key_bindings
  bind \cr peco_select_history # Bind for prco history to Ctrl+r
end


# ~/.config/fish/config.fishに追加
#fisherパッケージdecors/fish-ghqの設定
set GHQ_SELECTOR peco


# google cloud sdkのPATH
source /usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.fish.inc

eval (direnv hook fish)

## homebrew-command-not-found
brew command command-not-found-init > /dev/null 2>&1; and . (brew command-not-found-init)

#source /usr/local/share/fish/vendor_completions.d/*.fish

# history同期
## https://github.com/fish-shell/fish-shell/issues/825#issuecomment-203021964
function save_history --on-event fish_preexec
    history --save
    history --marge
end

