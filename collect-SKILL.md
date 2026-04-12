# news-collect スキル

今日のトレンドニュースを収集し、CLAUDE.mdの興味領域に基づいて評価・整理して保存する。

## 手順

### ステップ1: プロフィール読み込み
CLAUDE.mdを読み込み、興味領域と評価基準を把握する。

### ステップ2: ニュース収集

以下のソースから情報を収集する：

**はてなブックマーク**
- https://b.hatena.ne.jp/hotentry/it をWebFetchで取得
- タイトル・URL・ブクマ数を抽出

**Hacker News**
- https://news.ycombinator.com をWebFetchで取得
- タイトルと以下の形式でコメントページURLを記録：
  `https://news.ycombinator.com/item?id=ITEM_ID`
  （元記事URLではなくコメントページURLを必ず使うこと）

**Zenn トレンド**
- https://zenn.dev/trending をWebFetchで取得

**Qiita トレンド**
- https://qiita.com/trend をWebFetchで取得

**Reddit**
- WebFetchツールはreddit.comをブロックするため、以下のBashコマンドを使用：
  ```bash
  curl -s -H "User-Agent: news-collector/1.0" https://www.reddit.com/r/artificial+MachineLearning+netsec+selfhosted+SideProject+ExperiencedDevs+cscareerquestions+webdev+technology/.json | head -c 50000
  ```

### ステップ3: 評価・整理

収集した記事をCLAUDE.mdの興味領域と照らし合わせて：
- 各記事に ★★★ / ★★ / ★ を付ける
- カテゴリ（AI開発・セキュリティ・個人開発など）を分類
- ★★★の記事は特に詳しくコメントを添える

### ステップ4: 保存

以下の形式で `ideas/daily/YYYYMMDD-trend.md` に保存する（YYYYMMDDは今日の日付）：

```markdown
# トレンドニュース YYYY-MM-DD

## ★★★ 注目記事

| タイトル | ソース | カテゴリ | コメント |
|---|---|---|---|
| [タイトル](URL) | HN | AI開発 | 一言コメント |

## ★★ 気になる記事

| タイトル | ソース | カテゴリ |
|---|---|---|
| [タイトル](URL) | はてブ | セキュリティ |

## ★ その他

- [タイトル](URL) — ソース
```

### ステップ5: Discord通知

保存完了後、以下のBashコマンドでDiscordに通知を送る：

```bash
curl -s -X POST "$DISCORD_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{\"content\": \"MESSAGE\"}"
```

通知メッセージの内容（JSON文字列として組み立てる）：
```
**【AIキュレーター】YYYY-MM-DD トレンドニュース**
★★★ 注目記事 N件

▶ タイトル1
▶ タイトル2
...（★★★の記事をすべてリスト）

📄 ideas/daily/YYYYMMDD-trend.md
```

注意事項：
- `DISCORD_WEBHOOK_URL` 環境変数が未設定の場合はスキップしてよい
- メッセージ内の `"` はエスケープ（`\"`）する
- 改行は `\n` で表現する
- メッセージが2000文字を超える場合は★★★のタイトルのみに絞る

### 完了メッセージ

保存完了後、以下を報告する：
- 収集した記事の総数
- ★★★の記事数と簡単なサマリー
- 保存先のファイルパス
- Discord通知の送信結果
