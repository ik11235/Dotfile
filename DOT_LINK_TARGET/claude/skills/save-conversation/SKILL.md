---
name: save-conversation
description: Save conversation logs with summary and hard links to raw session logs. Use when the user invokes /save-conversation or asks to save, archive, or persist the current conversation/session log (「会話を保存」「ログを保存」「このセッションを記録して」など). Hard-links the raw jsonl and generates a summary markdown via a bundled script — do not hand-write the conversation log.
allowed-tools: Bash(*), Write(*), Read(*)
---

# Save Conversation

現在の会話を保存する。機械的な処理（セッション特定・ハードリンク・会話ログ抽出・MD組み立て）はすべて同梱スクリプトが行う。**あなたが書くのはタイトルと Summary だけ**。会話ログ全文を自分で再生成しないこと — それがこのスキルの高速さの理由であり、生ログ jsonl も完全な形でハードリンク保全される。

## 保存先の決定（引数の解釈）

`/save-conversation` に渡された引数で保存先が決まる。Step 2 のスクリプト呼び出しにそのまま反映する。

| 引数 | 保存先 | スクリプト引数 |
| --- | --- | --- |
| なし | `${cwd}/${session_uuid}/`（従来挙動） | `--dest` 不要 |
| `vault`（typo の `valut` も可） | 環境変数 `CLAUDE_SAVE_CONV_VAULT_DIR` が指す保存先（未設定ならスクリプトがエラー終了） | `--dest vault` |
| 上記以外の文字列 | その文字列を PATH とみなして保存（従来の PATH 指定挙動） | `--dest "<引数>"` |

`vault` の実パスはスクリプトには埋め込まず、環境変数 `CLAUDE_SAVE_CONV_VAULT_DIR`（zshrc 等のシェル設定で定義）で与える。キーワード解決はスクリプト側で行うので、引数の値をそのまま `--dest` に渡せばよい。生ログ jsonl の探索元は保存先と独立して常に実 cwd から導出されるため、別ディレクトリで起動したセッションを vault に集約しても正しくハードリンクされる。

## Step 1: タイトルを決め、Summary を書く

1. この会話の短く説明的なタイトルを決める（会話で使われた言語、最大50文字。`/ \ : * ? " < > |` は使わない — スクリプト側でも除去されるが、最初から安全な形にする）。
2. Summary を一時ファイルに書く。会話全体の要点 — 議論したトピック、下した決定、実行したアクション — を簡潔に。会話の逐語再現は不要（スクリプトが jsonl から抽出する）。
   一時ファイル名はセッション固有にすること（固定名だと並行セッションで内容が混線する）: `/tmp/save-conv-summary-$CLAUDE_CODE_SESSION_ID.md`、env が無ければ `mktemp` を使う。

```bash
# 例: Write ツールで /tmp/save-conv-summary-<session-id>.md に Summary 本文だけを書く
```

## Step 2: スクリプトを実行する

```bash
python3 ~/.claude/skills/save-conversation/scripts/save_conversation.py \
  --title "<タイトル>" \
  --summary-file "/tmp/save-conv-summary-$CLAUDE_CODE_SESSION_ID.md"
  # 保存先を指定する場合は上記に --dest を足す（上表参照）:
  #   vault 保存: --dest vault
  #   PATH 指定:  --dest "/path/to/save"
```

スクリプトが自動で行うこと:

- セッション特定: `$CLAUDE_CODE_SESSION_ID` → なければ `~/.claude/projects/<encoded-cwd>/` の最新 jsonl
- 保存先 `${dest}/${session_uuid}/`（`--dest` 省略時は `${cwd}`）の作成と jsonl のハードリンク。既存リンクは inode を比較し、atomic rename（tmpfile → rename）でソースが置き換わった stale link は貼り直す
- jsonl から user/assistant のテキストを抽出（tool call・thinking・system-reminder は除外）し、frontmatter + Summary + Conversation Log の MD を `${dest}/${session_uuid}/<タイトル>.md` に書き出す

オプション（通常は不要）: `--session <uuid>` `--cwd <dir>` `--project-dir <dir>`

## Step 3: 結果を報告する

スクリプトの出力（保存先パス・メッセージ数）をユーザーに伝える。`/rename` はビルトインコマンドでツールから呼べないため、ユーザーが実行できる形で提示する:

```
セッション名を変更するには以下を実行してください:
/rename <タイトル>
```

## トラブルシューティング

- `error: project dir not found` — cwd が想定と違う。`--cwd` で保存先ディレクトリを明示する
- スクリプトが失敗した場合のみ、旧来の手動手順（mkdir → ln → MD 手書き）にフォールバックしてよい。その際も会話ログは要点のみに留め、全文再生成はしない
