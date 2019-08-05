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
