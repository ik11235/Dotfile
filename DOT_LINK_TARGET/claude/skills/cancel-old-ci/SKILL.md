---
name: cancel-old-ci
description: GitHub PR上で最新コミット以外の実行中CI workflowランをキャンセルする。PR番号の指定がなければ現在のブランチから自動判定する。
when_to_use: |
  以下のいずれかに該当する場合に使用：
  - 「古いCI止めて」「最新以外のCIキャンセル」「CIを止めて」「最新のCI以外止めて」
  - 同一ブランチで複数コミットpush後、古いコミットのCIランがリソースを浪費しているとき
  - PR上で実行中の古い workflow run を一括キャンセルしたいとき
---

# cancel-old-ci — 古いCIランのキャンセル

GitHub PR上で、最新コミット以外の実行中（in_progress / queued）のCI workflowランをキャンセルする。

## 手順

### 1. 対象PRの特定

- ユーザーがPR番号やURLを指定した場合はそれを使う
- 指定がない場合は `git branch --show-current` で現在のブランチ名を取得する

### 2. 実行中のランを取得

```bash
gh api "repos/{owner}/{repo}/actions/runs?per_page=50&branch={branch}" \
  --jq '.workflow_runs[] | select(.status != "completed") | "\(.id) \(.status) \(.head_sha[:10]) \(.name)"'
```

### 3. 最新コミットの特定と古いランの抽出

- 取得したランの中で最も多く出現する `head_sha`、またはブランチの HEAD コミットを最新とする
- 最新コミット以外の `head_sha` を持つランを「古いラン」として抽出する

### 4. キャンセル実行

古いランが存在する場合、それぞれに対して：

```bash
gh api repos/{owner}/{repo}/actions/runs/{run_id}/cancel -X POST
```

### 5. 結果報告

- キャンセルした件数とラン名を報告する
- 古いランがなかった場合は「最新コミットのCIのみ実行中です」と伝える
