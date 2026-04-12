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

`.md` ファイルをスマホ対応のカードレイアウトHTMLに変換して `ideas/daily/YYYYMMDD-trend.html` に保存する。
★★★はカード形式、★★はリスト形式、★はコンパクトなリスト形式で表示する。

以下のPythonスクリプトで変換する（`DATE`と`DATE_FMT`は実際の日付に置換）：

```bash
python3 << 'PYEOF'
import re, pathlib

DATE = 'YYYYMMDD'        # 例: 20260412
DATE_FMT = 'YYYY-MM-DD'  # 例: 2026-04-12
md_path = f'ideas/daily/{DATE}-trend.md'
html_path = f'ideas/daily/{DATE}-trend.html'
md = pathlib.Path(md_path).read_text(encoding='utf-8')

def parse_table_rows(text):
    rows = []
    for line in text.splitlines():
        if line.startswith('|') and not re.match(r'\|[-| ]+\|', line):
            cells = [c.strip() for c in line.strip('|').split('|')]
            rows.append(cells)
    return rows[1:] if rows else []

def md_link(text):
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

def badge(cat):
    colors = {'AI開発':'#4f46e5','セキュリティ':'#dc2626','個人開発':'#16a34a',
              'キャリア':'#d97706','テクノロジー':'#0891b2','ビジネス':'#7c3aed'}
    color = next((c for k,c in colors.items() if k in cat), '#6b7280')
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:99px;font-size:.75em">{cat}</span>'

s3 = re.search(r'## ★★★ 注目記事\n(.*?)(?=\n## )', md, re.DOTALL)
s2 = re.search(r'## ★★ 気になる記事\n(.*?)(?=\n## )', md, re.DOTALL)
s1 = re.search(r'## ★ その他\n(.*?)$', md, re.DOTALL)

s3_html = ''.join(
    f'<div class="card"><div class="card-title">{md_link(r[0])}</div>'
    f'<div class="card-meta">{r[1]} &nbsp;{badge(r[2])}</div>'
    f'<div class="card-comment">{r[3]}</div></div>'
    for r in parse_table_rows(s3.group(1)) if len(r) >= 4
) if s3 else ''

s2_html = ''.join(
    f'<li class="s2-item">{md_link(r[0])}<br>'
    f'<span class="s2-meta">{r[1]} &nbsp;{badge(r[2])}</span></li>'
    for r in parse_table_rows(s2.group(1)) if len(r) >= 3
) if s2 else ''

s1_html = ''.join(
    f'<li>{md_link(line[2:])}</li>'
    for line in (s1.group(1).strip().splitlines() if s1 else [])
    if line.strip().startswith('- ')
)

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>トレンドニュース {DATE_FMT}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f3f4f6;color:#1f2937;padding:1em;line-height:1.6}}
  h1{{font-size:1.2em;color:#111827;margin:.5em 0 1em;padding-bottom:.4em;border-bottom:2px solid #4f46e5}}
  h2{{font-size:1em;margin:1.5em 0 .75em;color:#374151}}
  a{{color:#4f46e5;text-decoration:none}}
  a:hover{{text-decoration:underline}}
  .card{{background:#fff;border-radius:12px;padding:1em;margin-bottom:.75em;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
  .card-title{{font-size:1em;font-weight:bold;margin-bottom:.4em}}
  .card-meta{{font-size:.8em;color:#6b7280;margin-bottom:.5em}}
  .card-comment{{font-size:.875em;color:#374151}}
  .s2-list{{list-style:none;padding:0}}
  .s2-item{{background:#fff;border-radius:8px;padding:.75em 1em;margin-bottom:.5em;font-size:.9em;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
  .s2-meta{{font-size:.75em;color:#9ca3af}}
  .s1-list{{list-style:none;padding:0}}
  .s1-list li{{padding:.4em 0;font-size:.85em;border-bottom:1px solid #e5e7eb;color:#6b7280}}
</style>
</head>
<body>
<h1>📰 トレンドニュース {DATE_FMT}</h1>
<h2>★★★ 注目記事</h2>
{s3_html}
<h2>★★ 気になる記事</h2>
<ul class="s2-list">{s2_html}</ul>
<h2>★ その他</h2>
<ul class="s1-list">{s1_html}</ul>
</body></html>"""

pathlib.Path(html_path).write_text(html, encoding='utf-8')
print('HTML saved:', html_path)
PYEOF
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
