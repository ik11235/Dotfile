## ワークフロー設計[^workflow-ref]

### Planモード
- 3ステップ以上 or アーキ判断は Planモードで開始
- 詰まったら止まって再計画。検証ステップにも使う
- 実装前に詳細な仕様で曖昧さを排す

### サブエージェント
- リサーチ・並列分析・重い調査は委譲してメインコンテキストを保護
- 1サブエージェント = 1タスク。複雑問題ほど計算量を投入

### 自己改善ループ
- 修正を受けたら `tasks/lessons.md` にパターンを記録
- セッション開始時にプロジェクト関連 lessons をレビュー
- ミス率が下がるまでルールを改善

### 完了前検証
- 動作を証明できるまで完了マークしない
- 必要に応じて main との差分を確認
- 「スタッフエンジニアは承認するか？」と自問
- テスト実行・ログ確認

### エレガントさ
- 重要変更前に「もっとエレガントな方法は？」と一度立ち止まる
- ハック的に感じたら今ある情報で再設計
- シンプルな修正は過剰設計しない

### 自律的バグ修正
- バグレポートは手取り足取りなしで自走修正
- ログ・エラー・失敗テストから自力で解く
- ユーザーのコンテキスト切替をゼロに（CI 失敗は言われずとも直す）

### コンテキスト管理
- 300k tokens 超の手応えで `/compact <方向性>` を手動実行（bad compact 予防）
- 試行失敗で学びが出たら `/rewind` で試行前に戻す（修正より rewind 優先）
- Auto-compact 閾値 70%（`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=70`）

### 長時間タスク並列化
- 10分以上かかる作業（Zenn digest・Vault 整理・横断検索）は `/tasks` でバックグラウンド化
- 完了は通知待ち。sleep ポーリング禁止

---

## タスク管理

**Todoist の専用プロジェクト「claude code」（id は環境変数 `TODOIST_CLAUDE_PROJECT_ID`）を計画と進捗の単一ソースとする**（MCP 共通ルール参照）。

1. 計画はタスクとして登録（粒度はチェック可能な単位。サブタスクで階層化）
2. 着手・完了は随時 update / complete で反映。重要な経過は task の comment に残す
3. 期限が決まっているものは `dueString`、固定締切は `deadlineDate`、所要時間は `duration` を使い分ける
4. 優先度は `p1`〜`p4`（`p1` が最高、`p4` がデフォルト/最低）
5. 並べ替え・期日変更は専用ツール（`reschedule-tasks` / `reorder-objects`）。`update-tasks` で due を書き換えると recurrence が壊れる
6. リポジトリ内のローカル `tasks/todo.md` を使うのは、ユーザーが明示的に依頼した場合や Todoist が使えない環境のみ

### セッション復元情報の併設

タスクを Todoist に登録するときは、後で続きを再開できるよう、当該セッションの復元情報を **task description（または最初のコメント）** に併設する。

- 取得元: `$CLAUDE_CODE_SESSION_ID`（環境変数）と `pwd`
- 推奨フォーマット（コピペで再開できる一行コマンドを必ず含める）:
  ```
  cwd: <pwd の値>
  session: <CLAUDE_CODE_SESSION_ID の値>
  resume: cd '<pwd の値>' && claude --resume <session-id>
  ```
- 1セッション内で複数タスクを切る場合、同一の cwd / session を全タスクの description に記載してよい（重複OK、後から検索性を上げるため）
- セッションログ実体は `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` に保存される。`claude --resume` が機能しない場合のフォールバック確認先として把握しておく

---

## コア原則

- **シンプル第一**：変更を最小限に
- **手を抜かない**：根本原因を直す。一時しのぎ禁止
- **影響を最小化**：必要な箇所のみ
- **Permission 拒否時**：止まってユーザーに依頼。必要なコマンドは `!` 付きで表示

---

## MCP 共通ルール

### Todoist MCP
- **書き込み許可は専用プロジェクト「claude code」（id は環境変数 `TODOIST_CLAUDE_PROJECT_ID`）のみ**。それ以外のプロジェクト・タスク・セクション・コメント・ラベル・フィルタは Read-Only として扱う
- ID の実値が必要なときは `echo $TODOIST_CLAUDE_PROJECT_ID` で取得する。未設定なら Todoist MCP を使う前にユーザーに確認
- 対象書き込み操作（add / update / complete / uncomplete / reschedule / delete / move / reorder / manage-assignments など）は、対象が専用プロジェクト配下に閉じることを事前確認してから実行
- 他プロジェクトへの書き込みが必要だとユーザーが意図している場合は、必ず明示確認を取ってから実行（暗黙に進めない）
- 参照系（find-* / fetch / get-* / search / analyze-* など）はプロジェクト横断で自由に利用可

---

[^workflow-ref]: ワークフロー設計は https://qiita.com/uno_ha07/items/5820d195510861b5be71 を参考にしている。
