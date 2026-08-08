# リポジトリ規約の自動検出

このスキルはリポジトリ非依存なので、ベースブランチも検証コマンドも**そのリポジトリから読み取る**。
決め打ちで `develop` に切ったり `npm test` を叩いたりすると、失敗するだけでなくユーザーの信頼を失う。

初回（フェーズ 0.5）でまとめて調べ、結果を短くメモしてから実装に入る。

## 1. ベースブランチ

```bash
gh repo view --json defaultBranchRef --jq .defaultBranchRef.name
git branch -r | head -30
```

- デフォルトブランチが `main` でも、`develop` が存在して普段の PR がそちらに向いているリポジトリがある。
  実際の PR の向き先を見るのが確実:
  ```bash
  gh pr list --state merged --limit 20 --json baseRefName --jq '[.[].baseRefName]|group_by(.)|map({b:.[0],n:length})'
  ```
- 最頻値をベースにする。割れている場合（`main` と `develop` が混在）は計画で「どちらに向けるか」を確認する。

## 2. ブランチ命名・コミット規約

```bash
git branch -a --sort=-committerdate | head -30
git log --oneline -40
cat CONTRIBUTING.md 2>/dev/null; cat CLAUDE.md 2>/dev/null; cat AGENTS.md 2>/dev/null
ls .github/
```

見るポイント:

- ブランチ名に issue 番号が入っているか（`fix/123-...` / `feature/gh-123` / `username/topic` など）
- コミットが Conventional Commits か（`feat:` / `fix(scope):`）、それとも自由文か
- commitlint 設定（`commitlint.config.*`, `.commitlintrc*`, `package.json` の `commitlint`）があれば**それが正**
- 言語（英語か日本語か）も既存ログに合わせる

規約が読み取れないときは、直近ログの多数派に倣うのが安全。それも割れていれば `<type>/<issue番号>-<short-description>` と
Conventional Commits を提案し、計画で確認する。

## 3. PR テンプレートとタイトル規約

```bash
ls .github/PULL_REQUEST_TEMPLATE* .github/pull_request_template.md 2>/dev/null
ls .github/workflows/ | head -40
grep -rl "pull_request_target\|semantic\|pr-title\|lint-pr" .github/workflows/ 2>/dev/null
```

- テンプレートがあれば**見出しを削らずに**埋める。埋められない項目は空欄で放置せず「該当なし」「ユーザー側で確認が必要」と書く。
- タイトル lint（`semantic-pull-request`, `pr-title-linter` 等）があれば、その設定で許可された type を使う。
- issue 連携は本文に `Closes #<番号>`。分割 PR で自動クローズさせたくないときは `Refs #<番号>` にして理由を書く。

本文はファイルに書いてから渡す:

```bash
gh pr create --draft --base <base> --title "<title>" --body-file /path/to/body.md
```

## 4. Draft で CI が走るか（重要）

Draft 中に CI が走らないなら、ローカル検証が唯一の自動検証になる。走るなら CI の結果もレビュー材料にできる。

```bash
grep -rn "draft" .github/workflows/ | head -30
```

- `if: github.event.pull_request.draft == false` のような条件があれば、そのワークフローは **Draft ではスキップされる**。
- `types: [opened, synchronize, reopened, ready_for_review]` の書き方も見る。
- 走らないと判明したら、フェーズ 3 のローカル検証を省略しない。走ると判明したら、push 後に
  `gh pr checks <number>` で結果を確認し、失敗があればレビューループと同じ扱いで直す。

Draft 解除（ready 化）は CI とレビュアーアサインを動かす行為なので、**ユーザーの判断に委ねる**。

## 5. ローカル検証コマンド

存在するファイルから当たりを付ける。**推測したコマンドをいきなり本番の意図で流さず、まず help や dry-run で存在を確かめる。**

| 手がかり | 典型的なコマンド |
|---------|----------------|
| `package.json` | `npm run lint` / `npm test` / `npm run typecheck`（`scripts` を実際に読んで確認） |
| `Makefile` | `make test` / `make lint` / `make fmt`（`make -n` や `grep '^[a-z].*:' Makefile` でターゲット確認） |
| `build.gradle(.kts)` | `./gradlew test` / `./gradlew ktlintFormat` |
| `pyproject.toml` | `pytest` / `ruff check` / `ruff format` / `mypy` |
| `Cargo.toml` | `cargo test` / `cargo clippy` / `cargo fmt` |
| `go.mod` | `go test ./...` / `gofmt` / `golangci-lint run` |
| `.pre-commit-config.yaml` | `pre-commit run --all-files`（重いので変更ファイル限定も検討） |
| `lefthook.yml` / `.husky/` | commit 時に自動実行される内容の確認（頼り切らない） |

- **モノレポでは、変更したモジュールのコマンドだけ回す**。全体テストは時間がかかりすぎて自走の妨げになる。
- テストが元から壊れている（自分の変更前から red）ことがある。判断が付かないときは変更前のコミットで一度回して切り分け、
  「元から壊れていた」なら直さずその事実を報告する。issue のスコープを勝手に広げない。

## 6. リポジトリ固有の実装ガイド

```bash
ls CLAUDE.md AGENTS.md CONTRIBUTING.md docs/ 2>/dev/null
find . -maxdepth 3 -name "CLAUDE.md" -o -maxdepth 3 -name "AGENTS.md" | head
```

サブディレクトリの `CLAUDE.md` / `AGENTS.md` はそのモジュール固有の規約なので、対象モジュールが決まったら必ず読む。
ここに書かれている規約は、このスキルの一般論より**常に優先**する。
