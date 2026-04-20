# === 外部ツール連携 ===

# ~/.zprofile の `brew shellenv` で HOMEBREW_PREFIX / HOMEBREW_REPOSITORY が
# export されていればそれを使う。未定義なら brew が存在する場合のみフォールバック。
# Nix 環境など brew が無いケースでは未定義のまま、以降の brew 依存処理は個別に
# 分岐する。
if not set -q HOMEBREW_PREFIX; and type -q brew
  set -gx HOMEBREW_PREFIX (brew --prefix)
  set -gx HOMEBREW_REPOSITORY (brew --repository)
end

# google cloud sdkのPATH
## brew cask `gcloud-cli` が share 配下に配置する。
## 古い cask 名 `google-cloud-sdk` / `gcloud-cli` でも動くようフォールバックする。
if set -q HOMEBREW_PREFIX
  for _gcloud_dir in $HOMEBREW_PREFIX/share/google-cloud-sdk \
                      $HOMEBREW_PREFIX/Caskroom/gcloud-cli/latest/google-cloud-sdk \
                      $HOMEBREW_PREFIX/Caskroom/google-cloud-sdk/latest/google-cloud-sdk
    if test -f $_gcloud_dir/path.fish.inc
      source $_gcloud_dir/path.fish.inc
      break
    end
  end
  set -e _gcloud_dir
end

# To enable homebrew-command-not-found
if set -q HOMEBREW_REPOSITORY
  set HOMEBREW_COMMAND_NOT_FOUND_HANDLER $HOMEBREW_REPOSITORY/Library/Homebrew/command-not-found/handler.fish
  if test -f $HOMEBREW_COMMAND_NOT_FOUND_HANDLER
    source $HOMEBREW_COMMAND_NOT_FOUND_HANDLER
  end
end

# interactive shell 以外では不要なフック類をスキップして起動を高速化する
if status is-interactive
  # fzf
  fzf --fish | source

  # direnv
  eval "$(direnv hook fish)"
end

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
