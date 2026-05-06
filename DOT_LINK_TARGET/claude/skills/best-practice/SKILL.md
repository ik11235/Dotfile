---
name: best-practice
description: claude-code-best-practiceリポジトリを最新化し、現在のClaude Code設定（global / project）に対してベストプラクティスに基づく改善提案を行う。引数 global/project でスコープ指定可。
when_to_use: |
  以下のいずれかに該当する場合に使用：
  - 「ベストプラクティス」「best practice」「設定見直し」「設定改善」を求められた
  - 「スキル改善」「Claude Code最適化」「ハック改善」を求められた
  - settings.json/CLAUDE.md/skills/agents/hooks の見直しや陳腐化チェックを依頼された
allowed-tools: Read, Bash(git pull*), Bash(git -C * pull*), Bash(ghq get*), Bash(ls *), Bash(touch *), Glob, Grep
---

claude-code-best-practiceリポジトリ（https://github.com/shanraisshan/claude-code-best-practice）を参照し、現在の設定に対する改善提案を行う。

## 引数の解釈

`$ARGUMENTS` で適用先スコープを決定する：

| 引数 | 対象 |
|------|------|
| `global` | グローバル設定のみ（`~/.claude/`） |
| `project` | 現在のプロジェクト設定のみ（`.claude/`、`CLAUDE.md`） |
| 空 or 未指定 | 両方 |

## 実行手順

### Step 1: リポジトリの最新化と実行記録

まず実行タイムスタンプを更新する（放置警告用）：

```bash
touch ~/.claude/skills/best-practice/.last-run
```

続いてリポジトリを最新化する：

```bash
REPO=~/ghq/github.com/shanraisshan/claude-code-best-practice
if [ -d "$REPO" ]; then
  git -C "$REPO" pull --ff-only 2>&1
else
  ghq get https://github.com/shanraisshan/claude-code-best-practice 2>&1
fi
```

pullに失敗した場合はその旨をユーザーに伝え、ローカルの既存内容で続行する。

### Step 2: ベストプラクティスの読み込み

リポジトリパス: `~/ghq/github.com/shanraisshan/claude-code-best-practice`

サブエージェントを使い、以下のファイル群から現在のプロジェクトに関連する内容を読み取る。メインコンテキストを汚さないよう、読み込みと分析はサブエージェントに委譲する。

主要な参照先：
- `best-practice/` — 7つのコア・ベストプラクティス（subagents, commands, skills, settings, memory, mcp, cli flags）
- `implementation/` — 各機能の実装例
- `tips/` — Claude Code開発者からの実践的Tips
- `reports/` — 設定比較やワークフローの詳細分析

### Step 3: 現在の設定の分析

スコープに応じて以下を読み取る：

**globalスコープ（`~/.claude/`）：**
- `~/.claude/CLAUDE.md` — グローバル指示
- `~/.claude/settings.json` — グローバル設定
- `~/.claude/skills/` — グローバルスキル一覧
- `~/.claude/commands/` — グローバルコマンド（存在する場合）

**projectスコープ（カレントディレクトリ）：**
- `CLAUDE.md` — プロジェクト指示
- `.claude/settings.json` — プロジェクト設定
- `.claude/settings.local.json` — ローカル設定
- `.claude/skills/` — プロジェクトスキル
- `.claude/commands/` — プロジェクトコマンド（存在する場合）
- `.claude/agents/` — プロジェクトエージェント（存在する場合）
- `.claude/hooks/` — プロジェクトフック（存在する場合）

### Step 4: 改善提案の生成

ベストプラクティスと現在の設定を比較し、以下の観点で改善提案を行う：

1. **settings.json** — 推奨設定の追加、権限設定の最適化
2. **CLAUDE.md** — 構造・内容の改善、不足している指示の追加
3. **スキル・コマンド** — プロジェクトに有用な新しいスキルやコマンド
4. **フック** — 開発効率を上げるフックの提案
5. **ワークフロー** — 開発フロー全体の改善

## 出力形式

提案は以下のフォーマットで出力する：

```
### [重要度: 高/中/低] 提案タイトル

**現状**: 現在の設定や状態の説明
**提案**: 具体的な変更内容
**理由**: ベストプラクティスのどの知見に基づくか

\`\`\`json or markdown
具体的な変更コード例
\`\`\`
```

重要度が高いものから順に提示する。

## 制約

- 提案のみ行い、ユーザーの確認なしに設定を変更しない
- ベストプラクティスは参考資料であり、プロジェクトの特性に合わないものは提案しない
- 既存の設定を壊す変更は避け、追加・拡張を中心に提案する
- 出力は日本語で行う
