# x-research

SocialData API を使って X (Twitter) の記事を収集・分析する CLI ツール。

## セットアップ

```bash
cd x-research
npm install
cp .env.example .env
# .env に SOCIALDATA_API_KEY を記入
```

## 使い方

```bash
npm run research -- --minFaves 1000 --since 2026-02-24 --until 2026-03-24 --lang ja
```

### オプション

| オプション | デフォルト | 説明 |
|---|---|---|
| `--minFaves` | `1000` | 最低いいね数 |
| `--since` | (必須) | 検索開始日 `YYYY-MM-DD` |
| `--until` | (必須) | 検索終了日 `YYYY-MM-DD` |
| `--lang` | `ja` | `ja` で日本語アカウントのみ対象 |

### 環境変数

`.env` に設定：

```
SOCIALDATA_API_KEY=your_key_here
CONCURRENCY=3   # 並列取得数（デフォルト3）
```

## 出力

- `output/report-YYYY-MM-DDTHH-MM-SS.json` — 全記事データ（JSON）
- `output/report-YYYY-MM-DDTHH-MM-SS.md`  — Markdown レポート

## キャッシュ

- `cache/` に検索結果・記事詳細をキャッシュ
- 同じクエリを再実行するとキャッシュから読み込み（差分取得）
- キャッシュをクリアしたい場合は `cache/` を削除

## 処理フロー

1. SocialData 検索 API でページネーション全件取得
2. 著者プロフィールの日本語文字でフィルタ（`--lang ja` 時）
3. ツイートのエンティティから `x.com/i/article/{id}` を抽出
4. 記事詳細 API を並列取得（失敗時はツイートテキストで代替）
5. タイトル＋著者で重複除去
6. エンゲージメントスコア順にソート（いいね + RT×2 + 引用 + リプ）
7. JSON・Markdown を `output/` に保存
