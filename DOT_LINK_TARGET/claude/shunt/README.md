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

skill 本体: `~/.claude/skills/bulk-reader/SKILL.md`。hook は 2026-09-26 に登録を外した（末尾の節を参照）。

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

## 2026-09-26: hook の登録を外した

導入後12日間の実績を集計し、hook は `~/.claude/settings.json` から外した（`SHUNT_MIN_LINES` も削除）。
hooks/ と evals/ は再導入に備えて残している。bulk-read と bulk-reader skill は手動で使える。

- テキストのブロック47件で、全文を読まずに済んだ分は入力トークン換算で約209万、分割読みで増えた往復は約132万
- 差し引きは同期間の全消費の0.5%。しきい値や除外を調整しても1%に届かない
- bulk-read への委譲はほぼ起きず、効いていたのは「全文読みの禁止」だけだった
- 編集中の記事は分割してほぼ全文を読み直すため、往復が増えるだけで損をしていた

詳細は Vault の `メモ/雑多メモ/2026-09-14 Spotify shunt方式のトークン削減を取り込む検討.md`。
再導入するときは README 冒頭の構成どおり、Read と Bash の PreToolUse に hooks/ の2本を登録する。
