# エルメス監視システム LINE通知切り替え 設計書

**日付:** 2026-03-25
**対象ファイル:** `monitor_hermes.py`

## 概要

エルメス公式サイトでベアンのキーケースを10分ごとに監視し、新商品が掲載されたら LINE Messaging API の Push Message で通知する。既存の Gmail 通知を廃止し LINE に一本化する。

## アーキテクチャ

```
Windowsタスクスケジューラ (10分ごと)
    ↓
monitor_hermes.py
    ↓ Playwright でベアン検索ページをスクレイピング
    ↓ キーケース候補を抽出
    ↓ 既通知URLと照合 (hermes_monitor_state.json)
    ↓ 新商品あり
    ↓
LINE Messaging API (Push Message)
    → 自分のLINEに通知
```

## 変更内容

### 削除
- `send_notification()` の Gmail (smtplib) 実装
- `.env` の `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`

### 追加
- `send_line_notification()` — LINE Messaging API の Push Message を送信
- `.env` に `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_ID`

### 通知メッセージ形式
```
【エルメス】ベアンのキーケースが入荷しました！

・Béarn キーケース
  ¥XX,XXX
  https://www.hermes.com/...

今すぐチェック：
https://www.hermes.com/jp/ja/search/?s=ベアン
```

## LINE Messaging API セットアップ手順

1. LINE Developers (developers.line.biz) にログイン／登録
2. プロバイダーを作成
3. Messaging API チャネルを作成
4. チャネルアクセストークン（長期）を発行 → `LINE_CHANNEL_ACCESS_TOKEN`
5. BotをLINEで友だち追加
6. `https://api.line.me/v2/profile` にGETリクエストしてUser IDを取得 → `LINE_USER_ID`

## 環境変数 (.env)

```
LINE_CHANNEL_ACCESS_TOKEN=xxxxxxxxxxxx
LINE_USER_ID=Uxxxxxxxxxxxx
```

## エラー処理

- トークン未設定の場合: ログ出力してスキップ（クラッシュしない）
- API呼び出し失敗: ステータスコードとエラー内容をログ出力してスキップ

## テスト方法

```bash
# .envにトークンをセット後、スクリプトを直接実行
python monitor_hermes.py

# LINE通知のみテストしたい場合
python -c "
from monitor_hermes import send_line_notification
send_line_notification([{'name': 'テスト商品', 'price': '¥10,000', 'url': 'https://example.com'}])
"
```
