---
name: commit-draft
description: 未コミットのdiffを分析し、コピペで実行できるgit commitコマンドを生成する
user-invocable: true
disable-model-invocation: true
---

# commit-draft — diffからコミットコマンドを生成

未コミットの変更を分析し、そのままターミナルに貼り付けて実行できるコミットコマンドを出力する。

## 手順

### 1. 環境確認

- ユーザーの実行シェルを判定する。Claude CodeのBashツール内では `$$` が正しく展開されないため使用しない。代わりに `$PPID` を起点にプロセスツリーを上方向に辿り、既知のシェル名（fish, zsh, bash, nu, elvish等）に一致する最初のプロセスを探す。具体的には以下のワンライナーを実行する:
  ```bash
  pid=$PPID; found=""; while [ "$pid" != "1" ] && [ -n "$pid" ] && [ "$pid" != "0" ]; do comm=$(ps -o comm= -p "$pid" 2>/dev/null | xargs); case "$comm" in fish|zsh|bash|nu|elvish|nushell) found="$comm"; break ;; esac; pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); done; if [ -n "$found" ]; then echo "$found"; else echo "$SHELL"; fi
  ```
  見つからない場合のみ `$SHELL` にフォールバックする（`$SHELL` はログインシェルを返すため、`exec fish` のようにシェルを切り替えている場合は不正確になる）
- 判定したシェルで動く構文でコマンドを出力する（特にfish はHEREDOC非対応のため注意）
- `git status` で未コミットの変更一覧を取得する（`-uall`フラグは使わない）
- `git diff` と `git diff --cached` でstaged/unstaged両方の差分を取得する
- `git log --oneline -5` で直近のコミットメッセージのスタイルを確認する

### 2. 変更の分析

差分の内容から以下を判断する:

- 変更の目的（バグ修正、機能追加、リファクタ、設定変更など）
- 論理的なコミット単位への分割が必要か
- コミットメッセージに含めるべき要点

### 3. コミット単位の決定

#### 1コミットにまとめる場合
- 変更が単一の目的に収まる場合

#### 複数コミットに分割する場合
- 異なる目的の変更が混在している場合
- 分割する場合は実行順序を明示する

### 4. 出力

以下の形式でコマンドブロックを出力する:

````
```sh
git add <具体的なファイルパス>
git commit -m "<コミットメッセージ>"
```
````

#### 出力ルール

- **`git add .` や `git add -A` は使わない** — 必ずファイル名を個別指定する
- **コミットメッセージは直近のコミットのスタイルに合わせる**（日本語/英語、prefixの有無など）
- **複数コミットの場合は番号付きで順序を明示する**
- **メッセージが複数行の場合はシェルに応じた構文を使う**:

**bash/zsh の場合:**
````
```sh
git add file1 file2
git commit -m "$(cat <<'EOF'
1行目: 要約

詳細（必要な場合）
EOF
)"
```
````

**fish の場合（HEREDOC非対応）:**
````
```fish
git add file1 file2
git commit -m "1行目: 要約

詳細（必要な場合）"
```
````

- **コマンド以外の説明は最小限にする** — 何をコミットするかの1行説明のみ
- **.env、credentials等の機密ファイルが含まれている場合は警告する**

### 5. 変更がない場合

`git status` でコミット対象がなければ「未コミットの変更はありません」とだけ伝える。
