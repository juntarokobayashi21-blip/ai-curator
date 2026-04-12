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

### ステップ5: HTMLファイル生成

`.md` ファイルと同じ内容を `ideas/daily/YYYYMMDD-trend.html` にも保存する。

以下のPythonコマンドで変換する：
```bash
python3 -c "
import re, pathlib

md_path = 'ideas/daily/YYYYMMDDtrend.md'  # 実際の日付に置換
html_path = md_path.replace('.md', '.html')

md = pathlib.Path(md_path).read_text(encoding='utf-8')

# 変換処理
html = md
# テーブルヘッダー区切り行を除去
html = re.sub(r'\|[-| ]+\|\n', '', html)
# テーブル行をTRに変換
def table_row(m):
    cells = [c.strip() for c in m.group(1).split('|') if c.strip()]
    tds = ''.join(f'<td>{c}</td>' for c in cells)
    return f'<tr>{tds}</tr>\n'
html = re.sub(r'\|(.+)\|\n', table_row, html)
# テーブルをtableタグで囲む
html = re.sub(r'(<tr>.*?</tr>\n)+', lambda m: f'<table border=\"1\">\n{m.group(0)}</table>\n', html, flags=re.DOTALL)
# リンク
html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href=\"\2\">\1</a>', html)
# 見出し
html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
# リスト
html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
html = re.sub(r'(<li>.*?</li>\n)+', lambda m: f'<ul>\n{m.group(0)}</ul>\n', html, flags=re.DOTALL)
# 段落
html = re.sub(r'\n\n+', '\n<br>\n', html)

full = f'''<!DOCTYPE html>
<html lang=\"ja\"><head><meta charset=\"utf-8\">
<style>body{{font-family:sans-serif;max-width:900px;margin:2em auto;line-height:1.6}}
table{{border-collapse:collapse;width:100%}}td{{padding:6px 10px;border:1px solid #ccc;vertical-align:top}}
h1,h2,h3{{color:#333}}a{{color:#0066cc}}</style></head>
<body>{html}</body></html>'''

pathlib.Path(html_path).write_text(full, encoding='utf-8')
print('HTML saved:', html_path)
"
```

### ステップ6: Discord通知

保存完了後、以下のPythonコマンドでDiscordに通知を送る。
HTMLはGitHub PagesのURLとしてメッセージ本文に含め、mdファイルを添付する。

```bash
python3 -c "
import json, subprocess, os, pathlib

# .envから読み込み
try:
    for line in pathlib.Path('.env').read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())
except: pass

webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
if not webhook:
    print('DISCORD_WEBHOOK_URL not set, skipping')
    exit()

date = 'YYYYMMDD'  # 実際の日付に置換
date_fmt = 'YYYY-MM-DD'  # 実際の日付に置換
md_path  = f'ideas/daily/{date}-trend.md'
html_url = f'https://juntarokobayashi21-blip.github.io/ai-curator/ideas/daily/{date}-trend.html'

msg = (
    f'**【AIキュレーター】{date_fmt} トレンドニュース**\n'
    '★★★ 注目記事 N件\n\n'
    '▶ タイトル1\n'
    '▶ タイトル2\n\n'
    f'🌐 {html_url}\n'
    f'📄 {md_path}'
)

result = subprocess.run([
    'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
    '-X', 'POST', webhook,
    '-F', f'payload_json={json.dumps({\"content\": msg})}',
    '-F', f'file1=@{md_path}',
], capture_output=True, text=True)
print('HTTP:', result.stdout)
"
```

注意事項：
- `DISCORD_WEBHOOK_URL` 環境変数が未設定の場合はスキップしてよい
- HTMLはGitHub PagesのURL（`https://juntarokobayashi21-blip.github.io/ai-curator/ideas/daily/YYYYMMDD-trend.html`）としてメッセージ本文に含める
- mdファイルは引き続き添付する
- メッセージが2000文字を超える場合は★★★のタイトルのみに絞る
- GitHub Pagesへの反映はgit push後数分かかる場合がある

### 完了メッセージ

保存完了後、以下を報告する：
- 収集した記事の総数
- ★★★の記事数と簡単なサマリー
- 保存先のファイルパス
- Discord通知の送信結果
