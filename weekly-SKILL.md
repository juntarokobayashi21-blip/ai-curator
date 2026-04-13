# weekly-summary スキル

直近7日分のデイリーレポートを集計し、週間ベスト記事・カテゴリ統計・急上昇トピックをまとめて保存する。

## 手順

### ステップ1: 対象ファイルの特定

今日の日付から過去7日間の `ideas/daily/YYYYMMDD-trend.md` を列挙する。

```bash
python3 -c "
from datetime import date, timedelta
today = date.today()
for i in range(7):
    d = today - timedelta(days=i)
    print(d.strftime('%Y%m%d'))
"
```

存在するファイルだけを対象にする（7日分揃っていなくても動作する）。

### ステップ2: ★★★ 記事の収集

各デイリーファイルを読み込み、`## ★★★ 注目記事` セクションのテーブル行を全件抽出する。

各行から以下を取得：
- タイトル（markdownリンクのまま）
- URL
- ソース（複数ソースバッジも含む）
- カテゴリ
- コメント
- 掲載日（ファイル名から取得）

### ステップ3: ランキング生成

収集した ★★★ 記事を以下の優先度でスコアリングし、**週間トップ10** を選出する：

| 条件 | スコア加算 |
|------|-----------|
| 複数ソース (2ソース🔥) | +2 |
| 複数ソース (3ソース以上🔥🔥) | +4 |
| AI開発・セキュリティカテゴリ | +1 |
| 複数日連続で関連記事が出ているトピック | +2 |

同スコアの場合は掲載日が新しい方を優先する。

### ステップ4: カテゴリ統計

週間の ★★★ 記事をカテゴリ別に集計する：

```
AI開発: N件
セキュリティ: N件
個人開発: N件
...
```

最多カテゴリを「今週のホットトピック」として記録する。

### ステップ5: 急上昇トピック検出

★★★ と ★★ 記事のタイトルから頻出キーワードを集計する。
3件以上出現した単語・フレーズを「急上昇ワード」として抽出する（固有名詞・技術用語を優先）。

### ステップ6: 保存

以下の形式で `ideas/weekly/YYYYMMDD-weekly.md` に保存する（YYYYMMDDは**今日の**日付）：

```markdown
# 週間トレンドまとめ YYYY-MM-DD（週）

> 対象期間: YYYY-MM-DD 〜 YYYY-MM-DD｜収集記事数: N件（★★★: N件）

## 🏆 週間ベスト10

| # | タイトル | ソース | カテゴリ | 掲載日 |
|---|---|---|---|---|
| 1 | [タイトル](URL) | HN / はてブ (2ソース🔥) | AI開発 | 04/10 |
| 2 | [タイトル](URL) | Reddit | セキュリティ | 04/11 |

## 📊 カテゴリ別集計

| カテゴリ | 件数 | 割合 |
|---|---|---|
| AI開発 | N | XX% |
| セキュリティ | N | XX% |

**今週のホットトピック: AI開発**

## 🔥 急上昇ワード

`Claude` `エージェント` `セキュリティ` `バイブコーディング` ...

## 📅 日別ハイライト

| 日付 | ★★★ 件数 | 注目記事 |
|---|---|---|
| 04/06 (月) | N | [タイトル](URL) |
| 04/07 (火) | N | [タイトル](URL) |
```

`ideas/weekly/` ディレクトリが存在しない場合は作成する。

### ステップ7: HTMLファイル生成

`.md` ファイルをスマホ対応HTMLに変換して `ideas/weekly/YYYYMMDD-weekly.html` に保存する。

```bash
python3 << 'PYEOF'
import re, pathlib

DATE = 'YYYYMMDD'        # 例: 20260413
DATE_FMT = 'YYYY-MM-DD'  # 例: 2026-04-13
md_path = f'ideas/weekly/{DATE}-weekly.md'
html_path = f'ideas/weekly/{DATE}-weekly.html'
md = pathlib.Path(md_path).read_text(encoding='utf-8')

def md_link(text):
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

def source_html(src):
    multi = re.search(r'\((\d+)ソース(🔥+)\)', src)
    if multi:
        count = multi.group(1)
        flames = multi.group(2)
        sources_part = re.sub(r'\s*\(\d+ソース🔥+\)', '', src).strip()
        badge = (f'<span style="background:#f59e0b;color:#fff;padding:1px 7px;'
                 f'border-radius:99px;font-size:.7em;margin-left:4px">'
                 f'{count}ソース{flames}</span>')
        return f'{sources_part}{badge}'
    return src

def badge(cat):
    colors = {'AI開発':'#4f46e5','セキュリティ':'#dc2626','個人開発':'#16a34a',
              'キャリア':'#d97706','テクノロジー':'#0891b2','ビジネス':'#7c3aed'}
    color = next((c for k,c in colors.items() if k in cat), '#6b7280')
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:99px;font-size:.75em">{cat}</span>'

def parse_table_rows(text):
    rows = []
    for line in text.splitlines():
        if line.startswith('|') and not re.match(r'\|[-| ]+\|', line):
            cells = [c.strip() for c in line.strip('|').split('|')]
            rows.append(cells)
    return rows[1:] if rows else []

# ベスト10テーブル
s_best = re.search(r'## 🏆 週間ベスト10\n(.*?)(?=\n## )', md, re.DOTALL)
best_html = ''
for r in (parse_table_rows(s_best.group(1)) if s_best else []):
    if len(r) >= 5:
        best_html += (
            f'<div class="card">'
            f'<div class="rank">#{r[0]}</div>'
            f'<div class="card-title">{md_link(r[1])}</div>'
            f'<div class="card-meta">{source_html(r[2])} &nbsp;{badge(r[3])}'
            f'<span class="date">{r[4]}</span></div>'
            f'</div>'
        )

# カテゴリ統計
s_cat = re.search(r'## 📊 カテゴリ別集計\n(.*?)(?=\n## )', md, re.DOTALL)
cat_rows = parse_table_rows(s_cat.group(1)) if s_cat else []
cat_html = ''.join(
    f'<div class="cat-row"><span class="cat-name">{badge(r[0])}</span>'
    f'<span class="cat-count">{r[1]}件</span>'
    f'<span class="cat-bar"><span style="width:{r[2]};background:#4f46e5;display:inline-block;height:8px;border-radius:4px"></span></span>'
    f'</div>'
    for r in cat_rows if len(r) >= 3
)
hot_match = re.search(r'\*\*今週のホットトピック: (.+?)\*\*', md)
hot_topic = hot_match.group(1) if hot_match else ''

# 急上昇ワード
s_words = re.search(r'## 🔥 急上昇ワード\n\n(.+)', md)
words_html = ''
if s_words:
    words = re.findall(r'`([^`]+)`', s_words.group(1))
    words_html = ''.join(
        f'<span style="background:#fef3c7;color:#92400e;padding:4px 10px;border-radius:99px;font-size:.85em;margin:3px">{w}</span>'
        for w in words
    )

# 日別ハイライト
s_daily = re.search(r'## 📅 日別ハイライト\n(.*?)$', md, re.DOTALL)
daily_rows = parse_table_rows(s_daily.group(1)) if s_daily else []
daily_html = ''.join(
    f'<tr><td>{r[0]}</td><td style="text-align:center">{r[1]}</td><td>{md_link(r[2])}</td></tr>'
    for r in daily_rows if len(r) >= 3
)

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>週間トレンド {DATE_FMT}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f3f4f6;color:#1f2937;padding:1em;line-height:1.6}}
  h1{{font-size:1.2em;color:#111827;margin:.5em 0 1em;padding-bottom:.4em;border-bottom:2px solid #4f46e5}}
  h2{{font-size:1em;margin:1.5em 0 .75em;color:#374151}}
  a{{color:#4f46e5;text-decoration:none}} a:hover{{text-decoration:underline}}
  .summary{{background:#e0e7ff;border-radius:8px;padding:.6em 1em;font-size:.85em;color:#3730a3;margin-bottom:1em}}
  .card{{background:#fff;border-radius:12px;padding:1em;margin-bottom:.75em;box-shadow:0 1px 3px rgba(0,0,0,.1);display:flex;gap:.75em;align-items:flex-start}}
  .rank{{font-size:1.4em;font-weight:bold;color:#d1d5db;min-width:2em;text-align:center}}
  .card-title{{font-size:.95em;font-weight:bold;margin-bottom:.3em}}
  .card-meta{{font-size:.78em;color:#6b7280;display:flex;align-items:center;gap:.4em;flex-wrap:wrap}}
  .date{{color:#9ca3af;margin-left:auto}}
  .card > div:last-child{{flex:1}}
  .cat-row{{display:flex;align-items:center;gap:.75em;padding:.4em 0;border-bottom:1px solid #f3f4f6;font-size:.9em}}
  .cat-name{{min-width:8em}} .cat-count{{min-width:3em;text-align:right;color:#6b7280}}
  .cat-bar{{flex:1}}
  .words{{display:flex;flex-wrap:wrap;gap:.3em;margin:.5em 0}}
  table{{width:100%;border-collapse:collapse;font-size:.85em;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
  td,th{{padding:.5em .75em;border-bottom:1px solid #f3f4f6;text-align:left}}
  th{{background:#f9fafb;color:#6b7280;font-weight:600}}
</style>
</head>
<body>
<h1>📊 週間トレンドまとめ {DATE_FMT}</h1>
<div class="summary">{re.search(r'> (.+)', md).group(1) if re.search(r'> (.+)', md) else ''}</div>

<h2>🏆 週間ベスト10</h2>
{best_html}

<h2>📊 カテゴリ別集計</h2>
{f'<p style="margin-bottom:.75em;font-size:.9em">🔥 今週のホットトピック: <strong>{hot_topic}</strong></p>' if hot_topic else ''}
{cat_html}

<h2>🔥 急上昇ワード</h2>
<div class="words">{words_html}</div>

<h2>📅 日別ハイライト</h2>
<table>
<thead><tr><th>日付</th><th>★★★</th><th>注目記事</th></tr></thead>
<tbody>{daily_html}</tbody>
</table>
</body></html>"""

pathlib.Path(html_path).parent.mkdir(parents=True, exist_ok=True)
pathlib.Path(html_path).write_text(html, encoding='utf-8')
print('HTML saved:', html_path)
PYEOF
```

### ステップ8: Discord通知

```bash
python3 -c "
import json, subprocess, os, pathlib, re

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

date = 'YYYYMMDD'
date_fmt = 'YYYY-MM-DD'
md_path  = f'ideas/weekly/{date}-weekly.md'
html_url = f'https://juntarokobayashi21-blip.github.io/ai-curator/ideas/weekly/{date}-weekly.html'

md = pathlib.Path(md_path).read_text(encoding='utf-8')
summary = re.search(r'> (.+)', md)
summary_text = summary.group(1) if summary else ''

msg = (
    f'**【AIキュレーター】{date_fmt} 週間まとめ**\n'
    f'{summary_text}\n\n'
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

### 完了メッセージ

保存完了後、以下を報告する：
- 集計期間と対象ファイル数
- 収集した ★★★ 記事の総数
- 週間ベスト10の上位3件
- 今週のホットトピック
- 保存先ファイルパス
