---
trigger: always_on
---

# RTK - Rust Token Killer

`PreToolUse` フック（`rtk hook antigravity`）により、シェルコマンドは自動的に `rtk` 経由へ書き換えられ、出力がトークン節約のために圧縮される。

## 扱い方

- 圧縮された出力は必要なシグナルを保った完全な結果として扱い、通常どおりコマンドを実行する
- 出力が空・終了コードと矛盾・文字化けして利用できない場合に限り、`rtk bypass <cmd>` で生出力を再取得する

## メタコマンド（直接実行可）

```bash
rtk gain              # トークン節約サマリ
rtk gain --history    # コマンド別の節約履歴
rtk bypass <cmd>      # フィルタを通さず生コマンドを実行（デバッグ用）
```
