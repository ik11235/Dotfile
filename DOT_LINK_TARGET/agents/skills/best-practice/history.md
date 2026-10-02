# best-practice 提案履歴

`/best-practice` の提案と、その後の判断を記録する追記専用ログ。次回の実行で、サブエージェントが見送り済みの提案を繰り返さないために使う。

- 状態は `実施` / `見送り` / `未着手` のいずれか
- 見送りは、前提が変わらない限り再提案しない。再提案するときは、何が変わったかを書く
- このファイルは public の Dotfile に載る。理由は抽象的に書き、業務上の固有名・個人情報・金額は書かない
- 2026-10-02 以前の ID は振り直し（当時は ID 制度がなかった）

## 2026-10-02

| ID | 重要度 | 提案 | 状態 | 理由・メモ |
|---|---|---|---|---|
| P-1 | 高 | ヘッドレス実行ラッパーの無効な `Write(path)` allow を削除し、`--fallback-model` と `--max-turns` を追加 | 実施 | |
| P-2 | 高 | 読み取り専用エージェントの書き込み先をエージェントスコープの PreToolUse フックで memory に限定 | 実施 | |
| G-1 | 高 | 自動 compact の発火点を `autoCompactWindow` で 400K に下げる | 実施 | PCT の env は外して一本化 |
| G-2 | 高 | `autoMode.environment` に業務リポジトリ・個人ノート・タスク管理・SaaS の信頼範囲を追記 | 見送り | `~/.claude` は public の Dotfile に載るため。private 化の手段（`--settings` で private リポジトリの別ファイルを読む alias、または managed-settings.d）と同時でなければ再提案しない |
| P-3 | 中 | 既存のデイリーノート・週次ノートへの Write を PreToolUse フックで拒否 | 実施 | |
| G-3 | 中 | ドット始まりの `.credentials.json` を Read/Edit deny に追加 | 実施 | Bash の `cat` は防げない |
| G-4 | 中 | squash / rebase マージを `permissions.ask` で確認制にする | 実施 | |
| G-5 | 中 | 重複スキルの整理（プラグイン版 code-review の無効化、synced skill-creator の非表示、入れ子スキルの退避、description の書き直し） | 実施 | |
| P-4 | 中 | Vault で使わないコード系スキルを `skillOverrides` で一覧から外す | 実施 | |
| P-5 | 中 | ペルソナ系スキルの起動条件を名前指定に絞り、counseling と振り分ける | 実施 | |
| G-6 | 低 | `/best-practice` に `context: fork` を付ける | 見送り | fork したサブエージェントはさらにサブエージェントを起動できず、スコープ別の並列委譲と両立しない。代わりに委譲手順を明文化した |
| P-6 | 低 | 自動実行系スキルに Gotchas 節を設ける | 実施 | |
| P-7 | 低 | 長いスキルの参照用部分を `references/` に切り出す | 実施 | kuon のみ。release-judgment は毎回使う手順なので見送り（切り出しても Read が1回増えるだけ） |
| P-8 | 低 | `.obsidian/` を Edit deny に入れる | 未着手 | |
| G-7 | 低 | status line に rate limit と worktree 名を表示 | 未着手 | |
| G-8 | 低 | research-only エージェントに memory の読み書きタイミングを明記 | 未着手 | |
| G-9 | 低 | `Bash(git -C * remote -v*)` の、サブコマンド前ワイルドカードの警告を解消 | 未着手 | 任意コマンドが確認なしで通りうる |
| G-10 | 低 | commit-draft スキルの出力先 `/tmp/commit-draft.sh` がセッション間で衝突する | 未着手 | このスキルの提案ではなく、セッション中に見つけた問題 |

### スキル自体の見直し（同日）

| ID | 重要度 | 提案 | 状態 | 理由・メモ |
|---|---|---|---|---|
| S-1 | 高 | `allowed-tools` の `git -C * …` をパス固定にする | 実施 | |
| S-2 | 高 | 提案履歴（このファイル）を持ち、見送り済みの提案を繰り返さない | 実施 | |
| S-3 | 中 | Gotchas 節を設ける | 実施 | |
| S-4 | 中 | 差分抽出を対象ディレクトリに絞る | 実施 | 自動更新コミットが約7割を占めていた |
| S-5 | 中 | project スコープの基準を git ルートにし、scripts・自動実行ログを調査対象に加える | 実施 | |
| S-6 | 中 | 提案に ID を振り、反映と検証の手順を `references/apply-and-verify.md` に切り出す | 実施 | |
| S-7 | 低 | 起動制御を `skillOverrides` から frontmatter の `disable-model-invocation` に移す | 未着手 | |
| S-8 | 低 | 出力形式の見本で入れ子のコードフェンスがエスケープ表示される | 実施 | S-6 の書き直しのついでに解消 |
| S-9 | 低 | `.last-run` の `touch` を実行の最後に移す | 未着手 | |
