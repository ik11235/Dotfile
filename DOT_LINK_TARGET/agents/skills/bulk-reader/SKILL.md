---
name: bulk-reader
description: "大きなファイル（350行超）の読解や、3ファイル以上を横断する質問を軽量モデルに委譲し、回答だけを受け取る。Read/cat が hook にブロックされたとき、または大量のコードから要点だけ知りたいときに使う。"
argument-hint: "<ファイルパス or 質問>"
---

```bash
$HOME/.claude/shunt/scripts/bulk-read --question "<質問>" --paths <file1> [<file2> ...]
```

- 各呼び出しは独立。追加で聞きたいときは同じ `--paths` でもう一度呼ぶ（ファイルは作業用モデルに行くだけで自分のコンテキストには入らないので再送は無料）
- 質問は具体的に。「何をしているか」より「X を呼ぶ関数と行番号」「Y の型定義」のように絞ると短く正確な回答になる
- 回答中の行番号や値を編集に使う前に、`Read` の offset/limit か `sed -n 'START,ENDp'` で該当箇所だけ実物を確認する
- 委譲しないもの: デバッグ（要約では足りない）、編集対象の正確な内容、設計判断、セキュリティ観点のレビュー
- 作業用モデルは環境変数 `SHUNT_WORKER=claude|gemini` で切替（既定 claude = Haiku）
