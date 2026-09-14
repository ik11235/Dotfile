# shunt — 大ファイル読みの軽量モデル委譲

Spotify の shunt プラグイン（https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt, Apache-2.0）の
hook 部分を移植し、作業用モデル呼び出しを Portal CLI から `claude -p`（Haiku）/ `gemini` に差し替えたもの。
起点: https://engineering.atspotify.com/2026/9/portal-by-spotify-cut-my-claude-code-token-usage-by-90

## 構成

```
shunt/
├── hooks/check-file-size    PreToolUse(Read): 350行超の全文読みを deny → /bulk-reader へ誘導
├── hooks/check-bash-read    PreToolUse(Bash): cat/head/tail/less/more/rtk read の大ファイル読みを deny
├── scripts/bulk-read        ファイル群＋質問を作業用モデルへ渡し、回答だけ返す
├── scripts/lib/worker.sh    作業用モデル呼び出し（stdin 渡し）・ログ
├── evals/run.sh             hook 判定テスト（36件）
└── usage.log                委譲ログ（日時 / mode / worker / 入力概算tk / 出力概算tk）※git管理外
```

skill 本体: `~/.claude/skills/bulk-reader/SKILL.md`。hook 登録と `SHUNT_MIN_LINES` は `~/.claude/settings.json`。

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `SHUNT_MIN_LINES` | `350` | この行数を超える全文読みをブロック |
| `SHUNT_EXCLUDE_GLOBS` | なし | ブロック対象から外すパス glob（`:` 区切り） |
| `SHUNT_WORKER` | `claude` | `claude`（Haiku）/ `gemini`（Flash） |
| `SHUNT_CLAUDE_MODEL` | `claude-haiku-4-5-20251001` | |
| `SHUNT_GEMINI_MODEL` | `gemini-2.5-flash` | |
| `SHUNT_TIMEOUT_SECONDS` | `180` | 1回の委譲のタイムアウト |
| `SHUNT_MAX_PAYLOAD_BYTES` | `2000000` | 1回に送る本文の上限 |

## 使い方・確認

```bash
bash ~/.claude/shunt/evals/run.sh                       # hook テスト
~/.claude/shunt/scripts/bulk-read --question "..." --paths a.kt b.kt
awk -F'\t' '{i+=$4;o+=$5;n++} END{print n" calls, "i" in → "o" out tokens"}' ~/.claude/shunt/usage.log
```

## 既知の制約（元実装と同じ）

- `offset:0` / `limit:0` は狙い読み扱いで通る
- `head -n 5 file` は `5` をパスと誤認して通る（`head -5 file` は検知）
- `sed -n '1,9999p' file` のような読み方は対象外
- 作業用モデルは表面的なパターンは拾うが、スレッド安全性などの深い問題は見落とす。デバッグ・設計判断・編集対象の正確な内容は委譲しない
