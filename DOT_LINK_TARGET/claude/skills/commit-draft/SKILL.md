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

- ユーザーの実行シェルを判定する。SessionStart フックが `/tmp/claude-user-shell` にシェル名を書き出しているので、Read ツールでこのファイルを読む。ファイルが存在しない場合のフォールバックとして `$SHELL` 環境変数を使用する
- 判定したシェルで動く構文でコマンドを出力する（特にfish はHEREDOC非対応のため注意）
- `git status` で未コミットの変更一覧を取得する（`-uall`フラグは使わない）
- `git diff` と `git diff --cached` でstaged/unstaged両方の差分を取得する
- `git log --oneline -5` で直近のコミットメッセージのスタイルを確認する

### 2. 変更の分析

差分の内容から以下を判断する:

- 変更の目的（バグ修正、機能追加、リファクタ、設定変更など）
- 論理的なコミット単位への分割が必要か
- コミットメッセージの行数（後述の判断基準を参照）
- **Claudeが変更に関与したか**（後述のCo-Authored-By判定を参照）

#### コミットメッセージの行数判断

1行目（要約行）は常に必要。本文（3行目以降）を付けるかどうかは変更の性質で判断する。

**1行で十分なケース:**
- 変更の意図が要約行だけで伝わる（リネーム、typo修正、依存更新、単純な追加・削除など）
- 例: `未使用のisTargetJobUrl関数を削除`

**複数行にすべきケース:**
- 「なぜ」この変更をしたかが要約行だけでは伝わらない
- 複数ファイルにまたがる変更で、変更箇所の関係性を説明したい
- 既存の動作を変えるため、変更前後の違いを示したい
- 代替案があった中で特定のアプローチを選んだ理由がある

迷ったら1行でよい。ただし、「要約行を読んだレビュアーが『なぜ？』と思うかどうか」を基準にする。

### Co-Authored-By の判定

このセッション内でClaudeが変更に関与した場合、コミットメッセージの末尾に `Co-Authored-By` トレーラーを追加する。

**関与ありと判断するケース:**
- Claudeがコード変更を提案し、ユーザーがそれを採用した
- ClaudeがEdit/Writeツールで直接ファイルを編集した
- Claudeが生成したコードをユーザーが貼り付けて適用した
- Claudeとユーザーの共同作業で変更が生まれた

**関与なしと判断するケース:**
- ユーザーが自分で書いた変更に対し、コミットコマンドの生成のみを依頼された
- Claudeはコードレビューやアドバイスのみで、変更内容自体はユーザーが独自に作成した

判断に迷う場合は付ける側に倒す。Claudeの提案がわずかでも変更に影響していれば付けてよい。

**フォーマット:**

トレーラーはコミットメッセージ本文の最後に空行を挟んで配置する。モデル名はセッションで使用中のモデルを記載する（例: `Claude Opus 4.6 (1M context)`, `Claude Sonnet 4.6`）。

```
Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
```

### 3. コミット単位の決定

#### 1コミットにまとめる場合
- 変更が単一の目的に収まる場合

#### 複数コミットに分割する場合
- 異なる目的の変更が混在している場合
- 分割する場合は実行順序を明示する

### 4. 出力

#### 出力ルール

- **`git add .` や `git add -A` は使わない** — 必ずファイル名を個別指定する
- **コミットメッセージは直近のコミットのスタイルに合わせる**（日本語/英語、prefixの有無など）
- **複数コミットの場合は番号付きで順序を明示する**
- **コマンド以外の説明は最小限にする** — 何をコミットするかの1行説明のみ
- **.env、credentials等の機密ファイルが含まれている場合は警告する**

#### シェル別のフォーマット

**bash/zsh — 1行メッセージ:**
````
```sh
git add file1 file2
git commit -m "要約行"
```
````

**bash/zsh — 複数行メッセージ:**
````
```sh
git add file1 file2
git commit -m "$(cat <<'EOF'
要約行

本文: なぜこの変更をしたか、補足事項など
EOF
)"
```
````

**bash/zsh — Co-Authored-By付き（1行要約 + トレーラー）:**
````
```sh
git add file1 file2
git commit -m "$(cat <<'EOF'
要約行

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```
````

**bash/zsh — Co-Authored-By付き（複数行メッセージ + トレーラー）:**
````
```sh
git add file1 file2
git commit -m "$(cat <<'EOF'
要約行

本文: なぜこの変更をしたか、補足事項など

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```
````

**fish — 1行メッセージ:**
````
```fish
git add file1 file2
git commit -m "要約行"
```
````

**fish — 複数行メッセージ（HEREDOC非対応）:**
````
```fish
git add file1 file2
git commit -m "要約行

本文: なぜこの変更をしたか、補足事項など"
```
````

**fish — Co-Authored-By付き（1行要約 + トレーラー）:**
````
```fish
git add file1 file2
git commit -m "要約行

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
````

**fish — Co-Authored-By付き（複数行メッセージ + トレーラー）:**
````
```fish
git add file1 file2
git commit -m "要約行

本文: なぜこの変更をしたか、補足事項など

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
````

複数行メッセージでは、要約行と本文の間に必ず空行を1つ入れる（gitの慣習）。

### 5. 変更がない場合

`git status` でコミット対象がなければ「未コミットの変更はありません」とだけ伝える。
