---
name: zenn-ai-digest
description: Zennの生成AI関連の新着記事を収集・要約してMarkdown/PDFレポートを生成する。
when_to_use: |
  以下のいずれかに該当する場合に使用：
  - 「Zennの最新記事」「Zennダイジェスト」「Zennの記事まとめ」を求められた
  - 「今週のAI記事」「AI記事まとめ」「生成AIのトレンド」「AI関連ニュースのまとめ」を求められた
  - 直近N日間の生成AI/LLM/Claude/ChatGPT/Gemini関連の技術記事サーベイを求められた
user-invocable: true
paths:
  - "**/AI-Chat/**"
  - "**/my-Obsidian-valut/**"
  - "**/Obsidian-valut/**"
---

# zenn-ai-digest — Zenn生成AI記事の収集・要約

Zennに投稿された生成AI関連の新着記事を収集し、一行要約リスト＋詳細要約＋総合分析レポートを生成してファイルに保存する。

## 手順

### 1. 期間の確認

ユーザーが期間を指定していない場合は「直近何日間の記事を対象にしますか？（デフォルト：7日間）」と確認する。指定があればその期間を使う。

### 2. 記事の収集

以下のトピックでZenn APIから最新記事を取得する。WebFetchツールを使い、**並列で**リクエストする。

**検索トピック一覧:**
- `ai`
- `chatgpt`
- `openai`
- `llm`
- `gpt`
- `claude`
- `gemini`
- `langchain`
- `rag`
- `生成ai`
- `stablediffusion`
- `copilot`

**APIエンドポイント:**
```
https://zenn.dev/api/articles?topicname={topic}&order=latest
```

**レスポンス構造:**
```json
{
  "articles": [
    {
      "id": 12345,
      "title": "記事タイトル",
      "path": "/username/articles/slug",
      "published_at": "2026-03-15T10:00:00.000+09:00",
      "liked_count": 10,
      "article_type": "tech",
      "emoji": "🤖",
      "user": {
        "username": "username",
        "name": "表示名"
      }
    }
  ],
  "next_page": 2
}
```

**フィルタリング:**
- `published_at` を使って指定期間内の記事のみを抽出する
- 複数トピックで重複する記事は `id` で重複排除する
- `liked_count` の降順でソートして、注目度の高い記事を優先する

### 3. 記事の要約

収集した各記事について、WebFetchで記事本文を取得し要約する。

**記事URL:** `https://zenn.dev{path}`（pathはAPIレスポンスのpath フィールド）

WebFetchのpromptには以下を指定する:
```
この記事を以下の形式で要約してください:
- 一行要約（30文字以内）
- 詳細要約（3-5文のパラグラフ）
- 主要なキーワード・技術（カンマ区切り）
```

記事数が多い場合（15件超）は、`liked_count` 上位15件に絞って詳細要約を行い、残りは一行要約のみにする。

効率のため、WebFetchリクエストは可能な限り並列で実行する。

### 4. レポートの生成

以下の構成でMarkdownレポートを作成する:

```markdown
# Zenn 生成AI記事ダイジェスト

> 対象期間: YYYY/MM/DD 〜 YYYY/MM/DD
> 収集日: YYYY/MM/DD
> 対象記事数: N件

## サマリーリスト

| # | タイトル | 著者 | いいね | 一行要約 |
|---|---------|------|-------|---------|
| 1 | [タイトル](URL) | @username | 10 | 一行要約 |

## 詳細要約

### 1. 記事タイトル
- **URL:** https://zenn.dev/...
- **著者:** @username
- **公開日:** YYYY/MM/DD
- **いいね:** N
- **キーワード:** keyword1, keyword2

詳細要約テキスト（3-5文）

---

（各記事について繰り返し）

## 総合分析

### トレンド概要
この期間の生成AI記事全体から読み取れるトレンドや傾向を3-5文で分析する。

### 注目トピック
- **トピック1:** 説明
- **トピック2:** 説明

### 技術・ツール別の動向
記事で多く取り上げられている技術やツールの傾向をまとめる。
```

### 5. ファイルの保存

レポートを以下のパスに保存する:
```
{カレントディレクトリ}/zenn-ai-digest-YYYYMMDD.md
```

ファイル名の日付は収集日（実行日）を使う。

### 6. PDF版の生成

保存したMarkdownファイルをPDFに変換する。`npx md-to-pdf` を使用する。

```bash
npx md-to-pdf {カレントディレクトリ}/zenn-ai-digest-YYYYMMDD.md
```

これにより同じディレクトリに `zenn-ai-digest-YYYYMMDD.pdf` が生成される。

変換に失敗した場合は、Markdownファイルは保存済みであることをユーザーに伝え、`npm install -g md-to-pdf` の実行を案内する。

### 7. 完了報告

保存後、以下をユーザーに報告する:
- Markdownファイルパス
- PDFファイルパス
- 収集した記事数
