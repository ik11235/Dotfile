---
name: commit-draft
description: 未コミットのdiffを分析し、Claude Code内で「!」付きで即実行できるgit commitコマンドを生成する
user-invocable: true
disable-model-invocation: true
---

# commit-draft — diffからコミットコマンドを生成

未コミットの変更を分析し、Claude Codeのプロンプトに `!` 付きで貼り付けて即実行できるコミットコマンドを出力する。

## 手順

### 1. 状態の取得

まず `git rev-parse --show-toplevel` でリポジトリルートのパスを取得する。以降のgitコマンドはすべて `git -C <repo-root>` を使い、`cd` は使わない（Bashツールの不要な権限プロンプトを避けるため）。

- `git -C <repo-root> status` で未コミットの変更一覧を取得する（`-uall`フラグは使わない）
- `git -C <repo-root> diff` と `git -C <repo-root> diff --cached` でstaged/unstaged両方の差分を取得する
- `git -C <repo-root> log --oneline -5` で直近のコミットメッセージのスタイルを確認する
- `lefthook.yml` や `.husky/prepare-commit-msg` 等を確認し、`prepare-commit-msg` hookがプレフィックスを自動付与するか調べる

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
- このセッション内でClaudeがEdit/Writeツールを使った形跡がなく、ユーザーからも「Claudeが書いた」という明示がない場合

デフォルトはCo-Authored-By **なし**。確実にClaudeが変更に関与したと判断できる場合のみ付ける。「このセッションで自分がコードを書いた/編集した記憶があるか？」を基準にする。コミットコマンドの生成だけを頼まれた場合は関与なし。

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

#### 出力方式

Claude Codeの `!` プレフィックスは内部で `(eval)` を使うため、heredocや複数行の入力は動作しない。また、長い1行コマンドを直接表示すると、ターミナル幅で折り返し＋インデントが入りコピペが壊れる。

この問題を回避するため、**コマンドをシェルスクリプトに書き出し、短い実行コマンドを提示する**方式を取る。

**手順:**

1. まずReadツールで `/tmp/commit-draft.sh` を読み込む（存在しなくてもエラーが返るだけでよい。Writeツールは事前にReadが必要なため）。その後Writeツールでシェルスクリプトを書き出す
2. スクリプトの中身をコードブロックでユーザーに表示する（何が実行されるか確認できるようにするため）
3. 実行用の短いコマンドを提示する:
```
! bash /tmp/commit-draft.sh
```

#### スクリプトの書き方

- **先頭で必ずgitリポジトリのルートに移動する** — ユーザーがサブディレクトリにいても動作するようにするため
- **`git add .` や `git add -A` は使わない** — 必ずファイル名を個別指定する
- **`set -e` を付ける** — エラー時に即停止するため

**1行メッセージの例:**
```bash
#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
git add file1 file2
git commit -m "要約行"
```

**複数行メッセージの例（heredoc）:**
```bash
#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
git add file1 file2
git commit -F - <<'EOF'
要約行

本文: なぜこの変更をしたか、補足事項など
EOF
```

**Co-Authored-By付きの例:**
```bash
#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
git add file1 file2
git commit -F - <<'EOF'
要約行

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

**複数行 + Co-Authored-By付きの例:**
```bash
#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"
git add file1 file2
git commit -F - <<'EOF'
要約行

本文: なぜこの変更をしたか、補足事項など

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
```

シェルスクリプト内ではheredoc（`<<'EOF'`）が使えるため、`git commit -F -` でstdinからメッセージを読み取る形式にする。`-m` 連結より見やすく、改行や空行の制御も自然にできる。1行メッセージの場合のみ `-m` を使う。

#### prepare-commit-msg hookへの対応

`lefthook.yml` や `.husky/prepare-commit-msg` 等の設定を確認し、`prepare-commit-msg` hookがコミットメッセージにプレフィックス（例: `feat(TICKET-123): `）を自動付与するか調べる。自動付与される場合、スクリプト内のコミットメッセージにはプレフィックスを含めず、本文のみを記述する。

例えば、ブランチ名 `feat/TICKET-456_add_feature` から hookが `feat(TICKET-456): ` を自動付与する場合:
- **正しい**: `git commit -m "ユーザー一覧にフィルタ機能を追加"`
- **誤り**: `git commit -m "fix(TICKET-456): ユーザー一覧にフィルタ機能を追加"` → `feat(TICKET-456): fix(TICKET-456): ...` と重複する

#### その他のルール

- **コミットメッセージは直近のコミットのスタイルに合わせる**（日本語/英語、prefixの有無など）
- **複数コミットの場合は番号付きで順序を明示する**
- **コマンド以外の説明は最小限にする** — 何をコミットするかの1行説明のみ
- **.env、credentials等の機密ファイルが含まれている場合は警告する**

#### 複数コミットの場合

複数コミットに分割する場合は、各コミットを別々のスクリプトファイルとして書き出す（`/tmp/commit-draft-1.sh`, `/tmp/commit-draft-2.sh`, ...）。実行コマンドもそれぞれ提示し、1つずつ順番に実行できるようにする。

### 5. 変更がない場合

`git status` でコミット対象がなければ「未コミットの変更はありません」とだけ伝える。
