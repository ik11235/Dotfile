dotfile
==================================

[![shellscript-syntax-check](https://github.com/ik11235/Dotfile/workflows/shellscript-syntax-check/badge.svg)](https://github.com/ik11235/Dotfile/actions?query=workflow%3Ashellscript-syntax-check)
[![actionlint](https://github.com/ik11235/Dotfile/workflows/actionlint/badge.svg)](https://github.com/ik11235/Dotfile/actions?query=workflow%3Aactionlint)
[![yamllint](https://github.com/ik11235/Dotfile/workflows/yamllint/badge.svg)](https://github.com/ik11235/Dotfile/actions?query=workflow%3Ayamllint)

個人用 dotfile リポジトリ。macOS をメインターゲットとし、Linux は一部サブセットのみ対応。

# 対応 OS

- **macOS**: 全スクリプト (`.link_dir_and_file.sh` / `.software-install.sh` / `.default-shell-change.sh` / `.mac-init.sh` / `.powerline-fonts-install.sh`) が動作する
- **Linux**: `.mac-init.sh` / `.powerline-fonts-install.sh` は macOS 専用のため実行時に警告表示でスキップ、`.software-install.sh` の Linux 分岐は未実装。シェル / エディタ等の設定ファイル本体 (zsh, fish, mise, direnv, Emacs, Git 等) は利用可能

# 管理対象

- シェル: zsh / fish (起動は zsh、対話 TTY では `exec fish` する。IDE 統合ターミナル / Warp 等は zsh のまま)
- バージョンマネージャ: mise (旧 asdf / `tool-versions` は撤去済み、mise の global config は `DOT_LINK_TARGET/config/mise/config.toml`)
- エディタ: Emacs (パッケージ一覧は `DOT_LINK_TARGET/emacs.d/init.el` の `installing-package-list` を参照)
- ターミナル補助: tmux
- Git / GitHub CLI: `~/.config/git/config`, `~/.config/gh/config.yml`
- Claude Code: `~/.claude/` 以下 (`CLAUDE.md` / `settings.json` / `commands` / `skills`)
- その他: `.editorconfig`, direnv, Brewfile (macOS)

# インストール

推奨: `ghq` 経由で `~/ghq/github.com/ik11235/Dotfile` に配置する。

```shell
ghq get https://github.com/ik11235/Dotfile.git
~/ghq/github.com/ik11235/Dotfile/init.sh
```

`ghq` を使わない場合でも、相対パスの混乱を避けるため `~/ghq/github.com/ik11235/Dotfile` に clone することを推奨する。

```shell
git clone https://github.com/ik11235/Dotfile.git ~/ghq/github.com/ik11235/Dotfile
~/ghq/github.com/ik11235/Dotfile/init.sh
```

# ディレクトリ構成

- `DOT_LINK_TARGET/**` — 先頭 `.` 付きで `$HOME` 直下にシンボリックリンクを張る対象 (例: `DOT_LINK_TARGET/zshrc` → `~/.zshrc`)
- `LINK_TARGET/**` — そのままの名前で `$HOME` 直下にシンボリックリンクを張る対象 (例: `LINK_TARGET/Brewfile` → `~/Brewfile`)
- `init.sh` — 上記のリンクを張り、必要に応じてソフトウェアをインストールするエントリポイント

## リンクの仕様

`DOT_LINK_TARGET` / `LINK_TARGET` の **トップレベル** のファイル・ディレクトリのみをリンク対象とする。サブディレクトリはリンクせず、既に同名ディレクトリが `$HOME` に存在する場合は `... Directory exists.` と表示してスキップする。

## init.sh が呼ぶサブスクリプト

各サブスクリプトは実行開始時に `[*] running <name>` をログ出力する。

| スクリプト | 内容 | OS |
| --- | --- | --- |
| `.link_dir_and_file.sh` | `DOT_LINK_TARGET` / `LINK_TARGET` のシンボリックリンク作成 | 共通 |
| `.software-install.sh` | Brewfile からの一括インストール (macOS のみ) | 共通呼び出し、処理は macOS のみ |
| `.default-shell-change.sh` | zsh をログインシェルに設定 | 共通 |
| `.mac-init.sh` | macOS 固有の `defaults write` 等 | macOS のみ (`init.sh` 側で uname 判定) |
| `.powerline-fonts-install.sh` | Powerline fonts / UDEV Gothic のインストール | macOS のみ (スクリプト冒頭で uname 判定) |

# CI

- `shellscript-syntax-check` — `bash -n` / `zsh -n` / `shellcheck` で dotfile 内のシェルを検証
- `actionlint` — GitHub Actions workflow 自体を lint
- `yamllint` — workflow と `DOT_LINK_TARGET/config/gh/config.yml` を lint (`.yamllint.yml` でルール設定)
