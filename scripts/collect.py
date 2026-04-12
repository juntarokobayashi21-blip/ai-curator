#!/usr/bin/env python3
"""
AI Curator - Daily News Collector
GitHub Models (gpt-4o-mini) で無料AI評価
"""

import json
import os
import re
import subprocess
import pathlib
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')
DATE  = datetime.now(JST).strftime('%Y%m%d')

GITHUB_TOKEN       = os.environ.get('GITHUB_TOKEN', '')
DISCORD_WEBHOOK    = os.environ.get('DISCORD_WEBHOOK_URL', '')
GITHUB_PAGES_BASE  = 'https://juntarokobayashi21-blip.github.io/ai-curator'
MD_PATH   = f'ideas/daily/{DATE}-trend.md'
HTML_PATH = f'ideas/daily/{DATE}-trend.html'

# ─── Fetch helpers ────────────────────────────────────────────────────────────

def get(url, headers=None):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 news-collector/1.0',
        **(headers or {})
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  [WARN] {url}: {e}')
        return ''

def parse_rss(xml, source):
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    out = []
    for item in items[:20]:
        title = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', item)
        link  = re.search(r'<link>(.*?)</link>|<link[^>]+href="([^"]+)"', item)
        if title and link:
            t = (title.group(1) or '').strip()
            l = (link.group(1) or link.group(2) or '').strip()
            if t and l and not l.startswith('#'):
                out.append({'title': t, 'url': l, 'source': source})
    return out

# ─── Sources ──────────────────────────────────────────────────────────────────

def fetch_hatena():
    print('  Hatena...')
    xml = get('https://b.hatena.ne.jp/hotentry/it.rss')
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    out = []
    for item in items[:30]:
        title = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', item)
        link  = re.search(r'<link>(.*?)</link>', item)
        bm    = re.search(r'<hatena:bookmarkcount>(\d+)</hatena:bookmarkcount>', item)
        if title and link:
            out.append({
                'title': (title.group(1) or '').strip(),
                'url':   (link.group(1) or '').strip(),
                'source': f'はてブ({bm.group(1) if bm else "?"})',
            })
    return out

def fetch_hn():
    print('  Hacker News...')
    return parse_rss(get('https://hnrss.org/frontpage'), 'HN')

def fetch_zenn():
    print('  Zenn...')
    return parse_rss(get('https://zenn.dev/feed'), 'Zenn')

def fetch_qiita():
    print('  Qiita...')
    return parse_rss(get('https://qiita.com/popular-items/feed'), 'Qiita')

def fetch_google_news():
    print('  Google News...')
    it = parse_rss(get('https://news.google.com/rss/search?q=technology&hl=ja&gl=JP&ceid=JP:ja'), 'GoogleNews(IT)')
    biz = parse_rss(get('https://news.google.com/rss/search?q=business&hl=ja&gl=JP&ceid=JP:ja'), 'GoogleNews(Business)')
    return it + biz

def fetch_reddit():
    print('  Reddit...')
    out = []
    for sub in ['artificial', 'MachineLearning', 'netsec', 'SideProject', 'ExperiencedDevs', 'cscareerquestions']:
        try:
            data = json.loads(get(f'https://www.reddit.com/r/{sub}/.json?limit=5'))
            for p in data['data']['children'][:5]:
                d = p['data']
                out.append({
                    'title': d['title'],
                    'url': f"https://reddit.com{d['permalink']}",
                    'source': f"Reddit/r/{sub}({d['score']})",
                })
        except Exception as e:
            print(f'  [WARN] Reddit/{sub}: {e}')
    return out

# ─── AI Evaluation ────────────────────────────────────────────────────────────

def evaluate(articles):
    if not GITHUB_TOKEN:
        print('[WARN] GITHUB_TOKEN not set, skipping AI evaluation')
        return []

    numbered = '\n'.join(f'{i+1}. [{a["source"]}] {a["title"]}' for i, a in enumerate(articles))

    prompt = f"""以下は今日収集したニュース記事の一覧です。
以下の興味領域に基づいて各記事を評価してください。

## 興味領域
- AI開発 — LLM、エージェント、プロンプトエンジニアリング、AIツール・サービス
- サイバーセキュリティ — 脆弱性、インシデント、セキュリティツール、ゼロデイ
- 個人開発（収益化） — SaaS、インディーハッカー、収益化事例、ノーコード
- 自動運転 — EV、Tesla、Waymo、自動運転技術の最新動向
- キャリア/転職 — エンジニアの働き方、給与、転職市場、リモートワーク
- テクノロジー企業の動向 — GAFAM、日本大手IT、スタートアップの資金調達・M&A
- ビジネス動向 — DX、新規事業、市場トレンド

## 評価基準
- ★★★: 興味領域に直接関係し、実用的・具体的な情報
- ★★: 興味領域に関係するが間接的
- ★: 参考程度
- なし: 関係なし（リストに含めない）

## 記事一覧
{numbered}

## 出力形式（JSONのみ、説明不要）
[
  {{"index": 1, "rating": "★★★", "category": "AI開発", "comment": "一言コメント"}},
  {{"index": 3, "rating": "★★", "category": "セキュリティ"}},
  {{"index": 5, "rating": "★", "category": "ビジネス動向"}}
]"""

    payload = json.dumps({
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://models.inference.ai.azure.com/chat/completions',
        data=payload,
        headers={
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Content-Type': 'application/json',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            content = result['choices'][0]['message']['content']
            m = re.search(r'\[.*\]', content, re.DOTALL)
            if m:
                return json.loads(m.group())
    except Exception as e:
        print(f'[WARN] AI evaluation: {e}')
    return []

# ─── HTML ─────────────────────────────────────────────────────────────────────

def badge(cat):
    colors = {'AI開発':'#4f46e5','セキュリティ':'#dc2626','個人開発':'#16a34a',
              'キャリア':'#d97706','テクノロジー':'#0891b2','ビジネス':'#7c3aed'}
    color = next((c for k, c in colors.items() if k in cat), '#6b7280')
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:99px;font-size:.75em">{cat}</span>'

def build_html(s3, s2, s1):
    cards = ''.join(
        f'<div class="card"><div class="card-title"><a href="{a["url"]}">{a["title"]}</a></div>'
        f'<div class="card-meta">{a["source"]} &nbsp;{badge(a.get("category",""))}</div>'
        f'<div class="card-comment">{a.get("comment","")}</div></div>'
        for a in s3
    )
    s2items = ''.join(
        f'<li class="s2-item"><a href="{a["url"]}">{a["title"]}</a><br>'
        f'<span class="s2-meta">{a["source"]} &nbsp;{badge(a.get("category",""))}</span></li>'
        for a in s2
    )
    s1items = ''.join(
        f'<li><a href="{a["url"]}">{a["title"]}</a> — {a["source"]}</li>'
        for a in s1
    )
    return f"""<!DOCTYPE html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>トレンドニュース {TODAY}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f3f4f6;color:#1f2937;padding:1em;line-height:1.6}}
h1{{font-size:1.2em;color:#111827;margin:.5em 0 1em;padding-bottom:.4em;border-bottom:2px solid #4f46e5}}
h2{{font-size:1em;margin:1.5em 0 .75em;color:#374151}}
a{{color:#4f46e5;text-decoration:none}}a:hover{{text-decoration:underline}}
.card{{background:#fff;border-radius:12px;padding:1em;margin-bottom:.75em;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.card-title{{font-size:1em;font-weight:bold;margin-bottom:.4em}}
.card-meta{{font-size:.8em;color:#6b7280;margin-bottom:.5em}}
.card-comment{{font-size:.875em;color:#374151}}
.s2-list{{list-style:none;padding:0}}
.s2-item{{background:#fff;border-radius:8px;padding:.75em 1em;margin-bottom:.5em;font-size:.9em;box-shadow:0 1px 2px rgba(0,0,0,.06)}}
.s2-meta{{font-size:.75em;color:#9ca3af}}
.s1-list{{list-style:none;padding:0}}
.s1-list li{{padding:.4em 0;font-size:.85em;border-bottom:1px solid #e5e7eb;color:#6b7280}}
</style></head>
<body>
<h1>📰 トレンドニュース {TODAY}</h1>
<h2>★★★ 注目記事</h2>{cards}
<h2>★★ 気になる記事</h2><ul class="s2-list">{s2items}</ul>
<h2>★ その他</h2><ul class="s1-list">{s1items}</ul>
</body></html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f'=== AI Curator collect {TODAY} ===')

    articles = []
    articles += fetch_hatena()
    articles += fetch_hn()
    articles += fetch_zenn()
    articles += fetch_qiita()
    articles += fetch_google_news()
    articles += fetch_reddit()
    print(f'Total: {len(articles)} articles')

    print('Evaluating...')
    evals = evaluate(articles)

    rated = {}
    for ev in evals:
        idx = ev['index'] - 1
        if 0 <= idx < len(articles):
            a = {**articles[idx], 'category': ev.get('category',''), 'comment': ev.get('comment','')}
            rated.setdefault(ev['rating'], []).append(a)

    s3 = rated.get('★★★', [])
    s2 = rated.get('★★', [])
    s1 = rated.get('★', [])
    print(f'★★★:{len(s3)}  ★★:{len(s2)}  ★:{len(s1)}')

    # Markdown
    pathlib.Path(MD_PATH).parent.mkdir(parents=True, exist_ok=True)
    lines = [f'# トレンドニュース {TODAY}\n',
             '## ★★★ 注目記事\n',
             '| タイトル | ソース | カテゴリ | コメント |', '|---|---|---|---|']
    for a in s3:
        lines.append(f'| [{a["title"]}]({a["url"]}) | {a["source"]} | {a["category"]} | {a["comment"]} |')
    lines += ['\n## ★★ 気になる記事\n', '| タイトル | ソース | カテゴリ |', '|---|---|---|']
    for a in s2:
        lines.append(f'| [{a["title"]}]({a["url"]}) | {a["source"]} | {a["category"]} |')
    lines.append('\n## ★ その他\n')
    for a in s1:
        lines.append(f'- [{a["title"]}]({a["url"]}) — {a["source"]}')
    pathlib.Path(MD_PATH).write_text('\n'.join(lines), encoding='utf-8')
    print(f'Saved: {MD_PATH}')

    # HTML
    pathlib.Path(HTML_PATH).write_text(build_html(s3, s2, s1), encoding='utf-8')
    print(f'Saved: {HTML_PATH}')

    # Discord
    if DISCORD_WEBHOOK:
        html_url = f'{GITHUB_PAGES_BASE}/ideas/daily/{DATE}-trend.html'
        msg = (f'**【AIキュレーター】{TODAY} トレンドニュース**\n'
               f'★★★ 注目記事 {len(s3)}件\n\n'
               + ''.join(f'▶ {a["title"]}\n' for a in s3)
               + f'\n🌐 {html_url}\n📄 {MD_PATH}')
        r = subprocess.run([
            'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
            '-X', 'POST', DISCORD_WEBHOOK,
            '-F', f'payload_json={json.dumps({"content": msg})}',
            '-F', f'file1=@{MD_PATH}',
        ], capture_output=True, text=True)
        print(f'Discord: HTTP {r.stdout}')
    else:
        print('Discord: skipped (no webhook)')

    print('=== Done ===')

if __name__ == '__main__':
    main()
