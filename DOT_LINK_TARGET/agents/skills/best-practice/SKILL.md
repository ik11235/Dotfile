---
name: best-practice
description: claude-code-best-practiceリポジトリを最新化し、現在のClaude Code設定（global / project）に対してベストプラクティスに基づく改善提案を行う。引数 global/project でスコープ指定可。
allowed-tools: Read, Glob, Grep, Bash(ls *), Bash(touch *), Bash(stat *), Bash(ghq get https://github.com/shanraisshan/claude-code-best-practice*), Bash(git -C ~/ghq/github.com/shanraisshan/claude-code-best-practice pull --ff-only*), Bash(git -C ~/ghq/github.com/shanraisshan/claude-code-best-practice log *)
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

### Step 1: 前回実行日の取得とリポジトリの最新化

前回実行日を取得してから、実行タイムスタンプを更新する（前回日は Step 2 の差分抽出に、タイムスタンプは放置警告に使う）。ファイルが無ければ前回日は `2026-01-01` とみなす：

```bash
stat -f %Sm -t %F ~/.claude/skills/best-practice/.last-run
touch ~/.claude/skills/best-practice/.last-run
```

続いてリポジトリを最新化する。リポジトリが無ければ `ghq get https://github.com/shanraisshan/claude-code-best-practice` で取得する：

```bash
git -C ~/ghq/github.com/shanraisshan/claude-code-best-practice pull --ff-only
```

git コマンドはこの文字列のまま実行する（`allowed-tools` と一致させるため。`-C` とサブコマンドの間に変数やワイルドカードを挟まない → Gotchas）。pullに失敗した場合はその旨をユーザーに伝え、ローカルの既存内容で続行する。

### Step 2: サブエージェントへの委譲

リポジトリパス: `~/ghq/github.com/shanraisshan/claude-code-best-practice`

まずメイン側で `history.md`（このスキルのディレクトリ）を Read し、過去の提案と「見送り」の理由を把握する。

Step 2〜4 はサブエージェントに委譲し、メインコンテキストには最終提案だけを戻す。スコープが両方なら global 用と project 用の2つを**1メッセージで並列起動**する（1サブエージェント = 1スコープ）。各サブエージェントへの指示には以下を含める：

- 読み取り専用で、ファイルを一切変更しないこと。秘密情報は出力しないこと
- 先に新規知見を抽出する。changelog・バッジの自動更新コミットが大半を占めるため、対象ディレクトリを絞る：
  `git -C ~/ghq/github.com/shanraisshan/claude-code-best-practice log --since=<前回日> --stat -- best-practice tips reports implementation`
  `changelog/` 配下は各ファイル末尾の直近エントリだけを読む
- 現設定を必ず読んでから比較し、**実施済みの提案は出さない**
- `history.md` の「見送り」と同じ提案は、前提が変わっていない限り出さない。出すなら何が変わったかを「現状」に書く（見送り一覧と理由を指示に貼る）
- 本スキルの Gotchas（下記）を指示に貼り、それに反する提案をしない
- 各提案の「理由」にはベストプラクティスリポジトリの根拠ファイルのパスを書き、読んでいないファイルを根拠にしない
- 下記「出力形式」で、ID（global は `G-1`…、project は `P-1`…）付き・重要度順に最大8件程度、末尾に参照したファイル一覧を付ける

サブエージェントから戻った提案のうち、重要度「高」の現状記述はメイン側で設定ファイルやログを1回確認してから提示する（誤検出を防ぐため）。

主要な参照先：
- `best-practice/` — 7つのコア・ベストプラクティス（subagents, commands, skills, settings, memory, mcp, cli flags）
- `implementation/` — 各機能の実装例
- `tips/` — Claude Code開発者からの実践的Tips
- `reports/` — 設定比較やワークフローの詳細分析

### Step 3: 現在の設定の分析

スコープに応じて以下を読み取る：

**globalスコープ（`~/.claude/`）：**
- `~/.claude/CLAUDE.md` と @import 先（RTK.md 等）— グローバル指示
- `~/.claude/settings.json` — permissions / hooks / autoMode / enabledPlugins / skillOverrides / statusLine
- `~/.claude/skills/*/SKILL.md` の frontmatter — グローバルスキル一覧
- `~/.claude/agents/*.md` — グローバルエージェント（存在する場合）
- `~/.claude/rules/`、`~/.claude/commands/` — 存在する場合

`~/.claude` は public の Dotfile リポジトリへのシンボリックリンク。業務情報・個人情報を含む設定値の提案は、public に載ることを前提に要否を書く。

**projectスコープ：**

ルートは `git rev-parse --show-toplevel`（git 管理外なら cwd）。cwd がサブディレクトリなら、ルートから cwd までの各階層の `CLAUDE.md` も読む。

- `CLAUDE.md` — プロジェクト指示
- `.claude/settings.json`、`.claude/settings.local.json` — プロジェクト設定・ローカル設定
- `.claude/skills/`、`.claude/commands/`、`.claude/agents/`、`.claude/rules/` — 存在する場合
- `.claude/hooks/`、`.claude/scripts/` — 存在する場合
- 自動実行（launchd plist・cron・CI から `claude -p` を呼ぶもの）があれば、その定義と実行ログ。警告・失敗の実例は有力な根拠になる

### Step 4: 改善提案の生成

ベストプラクティスと現在の設定を比較し、以下の観点で改善提案を行う：

1. **settings.json** — 推奨設定の追加、権限設定の最適化
2. **CLAUDE.md** — 構造・内容の改善、不足している指示の追加
3. **スキル・コマンド・エージェント** — 新規追加、起動条件の精度、重複
4. **フック** — 開発効率を上げるフック、プロンプト頼みのルールの強制
5. **MCP** — 接続・権限の過不足
6. **自動実行** — ヘッドレス実行のフラグ・権限・失敗時の扱い
7. **ワークフロー** — 開発フロー全体の改善

### Step 5: 履歴への記録

提案を提示したら、`history.md` に今回の実行分を追記する（ID・重要度・タイトル・状態は「未着手」）。ユーザーが対応または見送りを決めたら、その行の状態と理由を更新する。`history.md` も public の Dotfile に載るため、理由は抽象的に書く（業務上の固有名・個人情報・金額を書かない）。

## 提案を反映するとき

ユーザーが ID や番号で対応を指示したら、`references/apply-and-verify.md` を Read して従う。

## 出力形式

提案は以下のフォーマットで出力する：

```
### [重要度: 高/中/低] G-1 提案タイトル

**現状**: 現在の設定や状態の説明
**提案**: 具体的な変更内容
**理由**: ベストプラクティスのどの知見に基づくか

（具体的な変更コード例をコードブロックで）
```

重要度が高いものから順に提示する。

## 制約

- 提案のみ行い、ユーザーの確認なしに設定を変更しない
- ベストプラクティスは参考資料であり、プロジェクトの特性に合わないものは提案しない
- 既存の設定を壊す変更は避け、追加・拡張を中心に提案する
- 出力は日本語で行う

## Gotchas

実際に踏んだ失敗・誤提案を日付付きで1行ずつ追記する。推測で項目を増やさない。

- サブエージェントはさらにサブエージェントを起動できない。このスキルに `context: fork` を付けると Step 2 の並列委譲ができなくなる（2026-10-02 に誤提案）
- `skillOverrides` はプラグイン由来のスキル（例 `code-review:code-review`）や、スキル内に入れ子になったスキル（例 `yomiyasu:yomiyasu`）には効かない。synced スキル（`anthropic-skills:*`）には効く（2026-10-02 実機確認）。前者はプラグインの無効化か、ディレクトリの移動で対応する
- `autoMode` は project / local の設定からは読まれない（v2.1.207 以降）。user 設定・managed 設定・`--settings` の別ファイルだけ。`--settings` の `autoMode.environment` は既存の値に追記される（2026-10-02、`claude auto-mode config` で確認）
- allow 側の `Write(path)` は評価されない。パス限定の書き込み許可は `Edit(path)` で書く（v2.1.210 以降）
- Bash ルールで `-C` とサブコマンドの間に `*` を置くと（例 `git -C * log*`）、`-c` や `--exec-path` を挟んだ任意コマンドまで確認なしで通る。パスを固定して書く（2026-10-02、自動実行ログの警告で判明）
- `~/.claude/settings.json` の編集は、auto mode の判定器に「自己改変」としてブロックされることがある。止まったら回避せず、変更内容を提示してユーザーに任せる（2026-10-02）
