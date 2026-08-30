# GitHub issue の取得

## 参照形式の解決

ユーザーが渡してくる形はまちまち。次のどれでも受け取れるようにする。

| 入力例 | 解釈 |
|--------|------|
| `https://github.com/owner/repo/issues/123` | owner/repo の #123 |
| `#123` / `123` | **カレントリポジトリ**の #123 |
| `owner/repo#123` | 明示されたリポジトリの #123 |
| `https://github.com/owner/repo/pull/123` | issue ではなく PR。実装起点ではないので、何をしたいのか確認する |

カレントリポジトリの確認:

```bash
gh repo view --json nameWithOwner,defaultBranchRef,isFork,parent
```

別リポジトリの issue を指定された場合は、そのリポジトリをローカルに持っているかを先に確認する。
持っていなければ「どこで作業するか」をユーザーに確認する（勝手に clone しない）。

## 取得コマンド

```bash
gh issue view <number> --json number,title,body,state,stateReason,labels,assignees,author,comments,milestone,url,projectItems
```

`--repo owner/repo` を付ければ他リポジトリも読める。人間向けに整形して読みたいときは `--comments` 付きの通常表示も併用する。

```bash
gh issue view <number> --comments
```

## 何を読み取るか

- **body**: 何が困っているか / 再現手順 / 期待挙動。テンプレートが使われていれば見出しごとに拾う。
- **comments**: ここが本命であることが多い。**後半のコメントで仕様が変わっている**ことがよくあるので、
  本文だけ読んで実装に入らない。結論が本文と矛盾するときは、新しいコメントの方を優先しつつ、計画で明示して確認する。
- **labels**: `bug` / `enhancement` / `good first issue` などから種別と規模の当たりを付ける。
  リポジトリ独自のラベル（`needs-discussion`, `blocked`, `wontfix` 等）は着手可否のシグナルなので必ず見る。
- **assignees**: 自分（ユーザー）以外がアサインされているなら、着手前にその事実を申し送る。二重実装は最悪の無駄になる。
- **state / stateReason**: `CLOSED` なら実装せず、なぜ今これを渡されたのかを確認する。
- **milestone / projectItems**: 期限や優先度の文脈。計画のスコープ判断に使う。

## 関連する issue / PR を辿る

issue は相互リンクで文脈が分散する。次を辿ると「既にやられている」を早期に検出できる。

```bash
# この issue に言及している PR（クロスリファレンス）
gh issue view <number> --json title,body,comments --jq '..|strings' | grep -oE '#[0-9]+' | sort -u

# issue 番号で PR を検索（open/merged/closed すべて）
gh pr list --search "<number>" --state all --json number,title,state,url,headRefName

# ブランチ・コミットに痕跡がないか
git branch -a | grep -i <number>
git log --oneline origin/<base> | grep -iE "#<number>|issue.?<number>"
```

`gh issue view` の Web 表示にある "linked pull requests" は JSON で取りづらいので、上の検索で代替する。

## issue 特有の注意

- **受け入れ条件が書かれていないことが多い**。Jira チケットと違い、issue は「困った」だけで終わっていることがある。
  その場合は自分で受け入れ条件を言語化し、フェーズ 1 の計画に明示して承認を取る。勝手に広げも狭めもしない。
- **バグ報告の再現性を先に確かめる**。再現手順があるならローカルで再現してから直す。再現できないバグを「直した」と主張しない。
  再現できない場合は、その事実と調べた範囲を報告して判断を仰ぐ。
- **外部からの issue（OSS でよくある）は要求が曖昧・過大なことがある**。書かれている通りに全部やるのではなく、
  リポジトリの方針と照らして妥当なスコープを提案する。
- **セキュリティに関わる issue**（脆弱性報告など）は公開 PR で修正すると攻撃者に手口を晒すことがある。
  該当しそうなら実装に入る前にユーザーに確認する。
