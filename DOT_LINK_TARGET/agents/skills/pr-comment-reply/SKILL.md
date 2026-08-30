---
name: pr-comment-reply
description: PRのレビューコメントを確認し、対応要否を判断して修正・コミット・pushし、返信コメントにコミットハッシュURLを明記するまでを一連で行う。「PRのコメント対応して」「レビューコメント見て対応して」「指摘に返信して」と頼まれたとき、またはPRのレビュー指摘への修正とその返信を求められたときに使用する。
---

# pr-comment-reply — PRコメント対応から返信まで

レビューコメントの確認 → 対応要否の判断 → 修正 → commit/push → コミットハッシュURL付き返信、を一連で行う。

## 手順

### 1. コメントの収集

対象PRを特定し（指定がなければ現在のブランチから `gh pr view` で判定）、未対応のレビューコメントを取得する:

```bash
gh pr view <PR> --json url,headRefName,reviews,comments
gh api repos/<owner>/<repo>/pulls/<PR>/comments --jq '.[] | {id, path, line, body, user: .user.login, in_reply_to_id}'
```

- inline コメント（pulls/comments）と会話コメント（issues/comments）の両方を確認する
- 既に返信済み・resolved のスレッドは除外する

### 2. 対応要否の判断

各コメントを分類して**先にユーザーへ一覧提示**する:

- **修正する**: 指摘が妥当で修正方針が明確
- **修正しない（回答のみ）**: 意図的な実装・誤解・スコープ外 — 理由を返信で説明
- **要相談**: 設計判断が割れる・スコープが大きい — ユーザーの判断を仰ぐ

「要相談」が1件でもあれば、修正着手前にユーザーに確認する。

### 3. 修正とコミット

- 指摘単位で論理的にコミットを分割する（無関係な指摘を1コミットに混ぜない）
- コミットメッセージは通常のリポジトリ規約に従う（prepare-commit-msg hook の自動プレフィックスに注意）
- push まで実行し、**各修正に対応するコミットハッシュを控える**

### 4. 返信コメント

対応した各コメントスレッドに返信する。**必ずコミットハッシュのURLを明記する**:

```bash
gh api repos/<owner>/<repo>/pulls/<PR>/comments/<comment-id>/replies -f body='ご指摘の通り修正しました。
https://github.com/<owner>/<repo>/commit/<full-hash>'
```

- 修正しない場合も放置せず、理由を添えて返信する
- 会話コメント（inline でないもの）への返信は `gh pr comment <PR> --body '...'` を使う

### 5. 完了報告

「コメントN件: 修正M件（各コミットURL）、回答のみK件、要相談J件」の形でユーザーに報告する。resolved 化はレビュアーに委ねる（勝手に resolve しない）。
