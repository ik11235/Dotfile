---
name: permission-allowlist
description: >-
  Antigravity CLI の過去トランスクリプトをスキャンし、頻繁に手動承認している安全な
  読み取り専用コマンド・MCP ツール・URL 読み取りを洗い出して
  ~/.gemini/antigravity-cli/settings.json の permissions.allow へ提案・追加する
  （Claude Code の /fewer-permission-prompts に相当する Antigravity 向けスキル）。
  「Antigravity の許可プロンプトを減らしたい」「permission-allowlist」
  「Antigravity の allowlist を更新して」などで使う。
---

# permission-allowlist — Antigravity の許可プロンプト削減

Antigravity CLI の直近セッションのトランスクリプトを分析し、安全で繰り返し使われている読み取り専用操作を `~/.gemini/antigravity-cli/settings.json` の `permissions.allow` に追加提案する。機械的なログ集計・既存ルール照合・RTK リライト判定・JSON 更新は同梱スクリプト [`scripts/analyze_permissions.py`](./scripts/analyze_permissions.py) に任せ、モデル側は安全性の最終判断とユーザーへのわかりやすい提示に集中する。

> **Claude Code との使い分け**: このスキルは Antigravity CLI（`~/.gemini/antigravity-cli/settings.json`）専用。Claude Code の許可リスト調整にはビルトインの `/fewer-permission-prompts` をそのまま使う。

## Antigravity 権限モデルの前提

- 設定ファイル: `~/.gemini/antigravity-cli/settings.json`（Global スコープ。Project / Shared スコープの調整が必要な場合は `/permissions` TUI を案内する）
- 優先順位: **`deny` > `ask` > `allow`**（`deny` や `ask` にあるルールは `allow` に追加しても上書きできない）
- 書式（カッコの前に空白を入れない）:
  - コマンド: `command(<prefix>)` または `command(regex:<pattern>)`（単語単位の前方一致。Claude Code の `Bash(<prefix> *)` と違い末尾 `*` は付けない）
  - MCP: `mcp(<server>/<tool>)` または `mcp(<server>/*)`
  - URL 読み取り: `read_url(<domain>)`（Terminal Sandbox の外部通信 allowlist にも反映される）
- Terminal Sandbox: Default / Auto モードではサンドボックス内コマンドは自動許可されるため、承認プロンプトの主な発生源は **`BypassSandbox: true` のコマンド**、**MCP ツール**、**`read_url`** になる
- RTK フック: `~/.gemini/config/hooks.json` で `rtk hook antigravity` が有効な場合、PreToolUse でコマンドが `rtk ...` に書き換えられてから許可ルールと照合されるため、書き換え対象コマンドには `command(rtk <prefix>)` も併せて必要になる

## 手順

### Step 1: トランスクリプトをスキャンする

同梱スクリプトを実行して直近 50 セッション（既定）を集計する。他会話のログ（`~/.gemini/antigravity-cli/brain/` 配下）と `~/.gemini/antigravity-cli/settings.json` を読むため、Antigravity の Terminal Sandbox で `Operation not permitted` または `sessions_scanned: 0` になった場合は **`BypassSandbox: true`** で再実行する。

```bash
python3 ~/.agents/skills/permission-allowlist/scripts/analyze_permissions.py scan --limit 50 --min-count 2
```

- より広く見たい場合は `--min-count 1` や `--limit 100` を指定できる
- 機械処理で詳細サンプルまで見たい場合は `--format json` を使う

### Step 2: 候補の安全性を最終精査する

スクリプトは任意コード実行（`python3` / `node` / `bash` / `xargs` / `find` / `sed` / `awk` 等）や書き込み系（`rm` / `git commit` / `git push` / `gh pr merge` / `gh api` / `git -C` 等）を自動除外するが、**`Safety` 列が `review` の候補や `npm run <script>` などは必ず中身を精査**し、以下を守ること:

- **読み取り専用・副作用なし**（またはテスト/lint/型チェック等の検証用途で安全に再実行できるもの）だけを推奨する
- **広すぎるプレフィックスを提案しない**:
  - 悪い例: `command(gh pr)`（`gh pr merge` まで許可してしまう）、`command(git -C)`（任意リポジトリや `-c` の抜け道になり得る）、`command(gh api)`（POST/DELETE まで許可してしまう）
  - 良い例: `command(gh pr view)`、`command(gh pr list)`、`command(gh issue view)`
- **RTK 書き換えの考慮**: スクリプトが `command(rtk ...)` を併記している場合、通常の `command(...)` とペアで提案する（`rtk` 経由でも直接実行でも止まらないようにするため）
- **サンドボックス専用（`Bypass/Ask = 0` かつ `sandbox-only`）**: Default / Auto モードでは既に自動許可されているため、優先度「低（任意）」として分ける
- **`exact-match-only` が多いコマンド**: `$(...)` や `{a,b}` 等を含む呼び出しでは Antigravity がプレフィックス一致を無効化するため、ルール追加だけでは消えない場合がある旨を補足する
- **機密情報の配慮**: `~/.gemini/antigravity-cli/settings.json` はマシンローカルだが、提案出力にトークンや社内機密パスをそのまま転記しない

### Step 3: ユーザーへ優先度付きで提案し、承認を取る

**ユーザーの明示的な承認なしに `settings.json` を書き換えない。**

以下の観点で整理して提示する:

1. **推奨（高優先）**: `BypassSandbox: true` の回数やセッション数が多い安全な読み取りコマンド・MCP・`read_url`
2. **検討（中優先）**: 出現頻度は中程度、またはリポジトリの `package.json` 等に依存する検証コマンド（例: `npm run ...`）
3. **任意（低優先）**: `sandbox-only` のコマンド（`request-review` モードでない限り追加不要）
4. **補足（該当がある場合のみ）**: `deny`/`ask` との競合、自動除外された高頻度コマンドの理由（例: `gh api` や `git -C` を外した理由）

番号付きで一覧を出し、追加する番号（または「高優先をすべて」など）をユーザーに選んでもらう。

### Step 4: 承認されたルールを `settings.json` へ反映する

ユーザーが承認したら、同梱スクリプトの `apply` サブコマンドで `~/.gemini/antigravity-cli/settings.json` を更新する（`settings.json` はワークスペース外のため `BypassSandbox: true` で実行する）。

まず `--dry-run` で確認し、問題なければ反映する:

```bash
python3 ~/.agents/skills/permission-allowlist/scripts/analyze_permissions.py apply \
  --add "command(gh pr view)" \
  --add "command(rtk gh pr view)" \
  --dry-run
```

```bash
python3 ~/.agents/skills/permission-allowlist/scripts/analyze_permissions.py apply \
  --add "command(gh pr view)" \
  --add "command(rtk gh pr view)"
```

`apply` スクリプトが行うこと:
- `action(target)` 書式と安全ガードレール（グローバルワイルドカード `*`・危険コマンド・機密パス・既存 `deny` との競合）を検証
- 重複追加を防止し、`statusLine` / `trustedWorkspaces` / `$schema` など他キーを保持
- 一時ファイル + `chmod 0600` + atomic rename で安全に書き込み

### Step 5: 結果を報告する

追加したルール一覧・スキップされた既存ルール・現在の `permissions.allow` 総数を報告する。Project / Shared スコープでの管理やルール削除をしたい場合は `/permissions` コマンドが使えることも一言添える。
