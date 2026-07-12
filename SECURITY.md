# Security Policy

このプロジェクトは、セッションの transcript を外部の advisor provider に送信する
実験的な個人用ツールです。脆弱性の報告に実際の API キー、認証情報、個人情報、実際の
transcript を含めないでください。

## 公開報告の禁止

脆弱性を public issue、Pull Request、Discussion に投稿しないでください。再現には
合成データを使ってください。

## 報告経路

現在、このリポジトリには専用のセキュリティ連絡先が設定されていません。公開前に、
リポジトリ管理者は GitHub の Private Vulnerability Reporting を有効化するか、専用の
非公開連絡先をここに追加してください。経路が設定されるまでは、公開面に詳細を書かず、
管理者の GitHub プロフィール等から非公開に連絡してください。

報告には、影響を受ける commit/version、影響範囲、再現手順、緩和策（分かる場合）を
含めてください。現時点で対応時間の SLA は設けていません。

## 対象となる問題

- API キーや Codex 認証情報の漏洩
- transcript や設定値の意図しない外部送信
- 子 Codex プロセスの隔離・credential 除去の破綻
- install script や設定処理による意図しない書き込み・実行
- 依存関係や配布物に起因する脆弱性
