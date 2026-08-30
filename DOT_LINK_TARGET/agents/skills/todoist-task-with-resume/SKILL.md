---
name: todoist-task-with-resume
description: Todoist「claude code」プロジェクトへのタスク登録・更新の手順と、セッション復元情報（cwd / session / resume コマンド）を task description に併設する書式を提供する。計画を Todoist にタスク登録するとき、進捗を反映するとき、後で作業を再開できるようセッション情報を残すときに使用する。
---

# Todoist タスク登録＋セッション復元情報

本 skill は Todoist MCP の操作ルールと、登録・更新の手順・書式を定める。

## Todoist MCP 操作ルール

- **書き込みは専用プロジェクト「claude code」（`TODOIST_CLAUDE_PROJECT_ID`）配下のみ**。それ以外は Read-Only とし、他プロジェクトへの書き込みが必要な場合は必ず明示確認を取ってから実行
- ID の実値は `echo $TODOIST_CLAUDE_PROJECT_ID` で取得。未設定なら使用前にユーザーに確認
- 期日変更・並べ替えは `reschedule-tasks` / `reorder-objects` を使う（`update-tasks` で due を書き換えると recurrence が壊れる）
- 参照系（find-* / fetch / get-* / search / analyze-* など）はプロジェクト横断で自由に利用可

## タスク登録・更新の手順

1. 計画はチェック可能な粒度でタスク登録する。階層はサブタスク（`parentId`）で表現し、まとめ役の親タスクは `isUncompletable: true` にする
2. 着手・完了は随時 update / complete で反映。重要な経過は task の comment に残す
3. 期限が決まっているものは `dueString`、固定締切は `deadlineDate`、所要時間は `duration` を使い分ける
4. 優先度は `p1`〜`p4`（`p1` が最高、`p4` がデフォルト/最低）

## セッション復元情報の併設

タスク登録時、後で続きを再開できるよう、当該セッションの復元情報を **task description（または最初のコメント）** に併設する。

- 取得元: `$CLAUDE_CODE_SESSION_ID`（環境変数）と `pwd`
- 推奨フォーマット（コピペで再開できる一行コマンドを必ず含める）:

  ```
  cwd: <pwd の値>
  session: <CLAUDE_CODE_SESSION_ID の値>
  resume: cd '<pwd の値>' && claude --resume <session-id>
  ```

- 1セッション内で複数タスクを切る場合、同一の cwd / session を全タスクの description に記載してよい（重複OK、後から検索性を上げるため）
- セッションログ実体は `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` に保存される。`claude --resume` が機能しない場合のフォールバック確認先として把握しておく
