# General principle

Think in English, interact with the user in Japanese.

## ワークフロー方針[^workflow-ref]

- 3ステップ以上 or アーキ判断を伴うタスクは Planモードで開始。詰まったら止まって再計画
- リサーチ・並列分析・重い調査はサブエージェントへ委譲し、メインコンテキストを保護（1サブエージェント = 1タスク）
- 10分以上かかる作業はバックグラウンドタスク化し、完了は通知待ち（sleep ポーリング禁止）
- 修正を受けたら学びをパターン化して残す。プロジェクトに `tasks/lessons.md` があればそこへ追記し、セッション開始時にレビュー
- 動作を証明できるまで完了マークしない。「スタッフエンジニアは承認するか？」と自問し、テスト実行・ログ確認を行う
- 重要変更前に「もっとエレガントな方法は？」と一度立ち止まる。ただしシンプルな修正は過剰設計しない
- バグレポート・CI 失敗は手取り足取りなしで自走修正（ユーザーのコンテキスト切替をゼロに）

## タスク管理

- **Todoist の専用プロジェクト「claude code」（id は環境変数 `TODOIST_CLAUDE_PROJECT_ID`）を計画と進捗の単一ソースとする**
- タスクの登録書式・セッション復元情報の併設・操作ツールの使い分けは todoist-task-with-resume skill に従う
- ローカル `tasks/todo.md` を使うのは、明示依頼時 or Todoist が使えない環境のみ

## コア原則

- **シンプル第一**：変更を最小限に
- **手を抜かない**：根本原因を直す。一時しのぎ禁止
- **影響を最小化**：必要な箇所のみ
- **Permission 拒否時**：止まってユーザーに依頼。必要なコマンドは `!` 付きで表示

## Git / PR

- PR マージ依頼時のデフォルトは **merge コミット** (`gh pr merge <PR> --merge`)。`--squash` / `--rebase` はユーザーの明示指示があった場合のみ。`--delete-branch` は併用してよい

## MCP 共通ルール

### Todoist MCP

- **書き込み許可は専用プロジェクト「claude code」（`TODOIST_CLAUDE_PROJECT_ID`）配下のみ**。それ以外は Read-Only とし、他プロジェクトへの書き込みが必要な場合は必ず明示確認を取ってから実行
- ID の実値は `echo $TODOIST_CLAUDE_PROJECT_ID` で取得。未設定なら使用前にユーザーに確認
- 期日変更・並べ替えは `reschedule-tasks` / `reorder-objects` を使う（`update-tasks` で due を書き換えると recurrence が壊れる）
- 参照系（find-* / fetch / get-* / search / analyze-* など）はプロジェクト横断で自由に利用可

[^workflow-ref]: ワークフロー設計は https://qiita.com/uno_ha07/items/5820d195510861b5be71 を参考にしている。
