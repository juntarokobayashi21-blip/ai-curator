#!/usr/bin/env python3
"""
AI Curator - Weekly Summary Generator
直近7日分のデイリーレポートから週間ベスト10を生成する
"""

import json
import os
import re
import subprocess
import pathlib
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST)
DATE  = TODAY.strftime('%Y%m%d')
TODAY_FMT = TODAY.strftime('%Y-%m-%d')

GITHUB_TOKEN      = os.environ.get('GITHUB_TOKEN', '')
DISCORD_WEBHOOK   = os.environ.get('DISCORD_WEBHOOK_URL', '')
GITHUB_PAGES_BASE = 'https://juntarokobayashi21-blip.github.io/ai-curator'
MD_PATH   = f'ideas/weekly/{DATE}-weekly.md'
HTML_PATH = f'ideas/weekly/{DATE}-weekly.html'

# ─── Parse daily files ────────────────────────────────────────────────────────

def load_weekly_articles():
    """直近7日分の daily md から ★★★ 記事を全件収集する"""
    all_articles = []
    for i in range(7):
        d = TODAY - timedelta(days=i)
        path = pathlib.Path(f'ideas/daily/{d.strftime("%Y%m%d")}-trend.md')
        if not path.exists():
            continue
        md = path.read_text(encoding='utf-8')
        date_label = d.strftime('%m/%d')
        # ★★★ テーブルを抽出
        m = re.search(r'## ★★★ 注目記事\n(.*?)(?=\n## |\Z)', md, re.DOTALL)
        if not m:
            continue
        for line in m.group(1).splitlines():
            if not line.startswith('|') or re.match(r'\|[-| ]+\|', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) < 3:
                continue
            title_m = re.match(r'\[(.+?)\]\((.+?)\)', cells[0])
            if not title_m:
                continue
            all_articles.append({
                'title':    title_m.group(1),
                'url':      title_m.group(2),
                'source':   cells[1] if len(cells) > 1 else '',
                'category': cells[2] if len(cells) > 2 else '',
                'comment':  cells[3] if len(cells) > 3 else '',
                'date':     date_label,
                'score':    0,
            })
    return all_articles

def score_articles(articles):
    """スコアリングして上位10件を返す"""
    for a in articles:
        src = a['source']
        # 複数ソースボーナス
        multi = re.search(r'\((\d+)ソース', src)
        if multi:
            a['score'] += int(multi.group(1)) * 2
        # カテゴリボーナス
        if 'AI開発' in a['category'] or 'セキュリティ' in a['category']:
            a['score'] += 1
    return sorted(articles, key=lambda x: x['score'], reverse=True)[:10]

def category_stats(articles):
    """全 ★★★ 記事のカテゴリ集計"""
    counts = {}
    for a in articles:
        for cat in a['category'].split('/'):
            cat = cat.strip()
            if cat:
                counts[cat] = counts.get(cat, 0) + 1
    total = sum(counts.values()) or 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True), total

def trending_words(articles):
    """頻出キーワード抽出（3文字以上の英数字 or カタカナ語）"""
    text = ' '.join(a['title'] for a in articles)
    words = re.findall(r'[A-Za-z]{4,}|[ァ-ヶー]{3,}', text)
    counts = {}
    ignore = {'that','this','with','from','have','will','your','they','also',
              'more','been','when','were','what','into','than','some','just'}
    for w in words:
        if w.lower() not in ignore:
            counts[w] = counts.get(w, 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [w for w, c in top if c >= 2][:15]

# ─── AI Summary ───────────────────────────────────────────────────────────────

def _summary_fallback(top10, all_articles):
    cats = {}
    for a in all_articles:
        for c in a.get('category', '').split('/'):
            c = c.strip()
            if c:
                cats[c] = cats.get(c, 0) + 1
    top_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    main_cat = top_cats[0][0] if top_cats else 'テクノロジー'
    titles_sample = '、'.join(f'「{a["title"][:20]}…」' for a in top10[:2])
    return (f'今週は{len(all_articles)}件の注目記事を収集しました。'
            f'{main_cat}関連が最多で、{titles_sample}などが特に話題になりました。'
            f'来週も引き続きトレンドをウォッチしていきましょう。')

def generate_summary(top10):
    if not top10:
        return ''
    titles = '\n'.join(f'- [{a["category"]}] {a["title"]}' for a in top10[:10])
    prompt = f"""以下は今週の注目ニュースTOP10です。今週のトレンドを3〜4文の日本語でまとめてください。

観点：
1. 今週もっとも多かったカテゴリとその傾向
2. 特に印象的だったトピック
3. 来週への注目ポイント

記事：
{titles}

まとめ文のみ出力（箇条書き不要、3〜4文の連続した文章で）："""
    payload = json.dumps({
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.7,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://models.inference.ai.azure.com/chat/completions',
        data=payload,
        headers={'Authorization': f'Bearer {GITHUB_TOKEN}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            text = result['choices'][0]['message']['content'].strip()
            if text:
                return text
    except Exception as e:
        print(f'[WARN] Summary API failed: {e}')
    print('[INFO] Using fallback summary')
    return _summary_fallback(top10, top10)

# ─── HTML ─────────────────────────────────────────────────────────────────────

def badge(cat):
    colors = {'AI開発':'#4f46e5','セキュリティ':'#dc2626','個人開発':'#16a34a',
              'キャリア':'#d97706','テクノロジー':'#0891b2','ビジネス':'#7c3aed'}
    color = next((c for k, c in colors.items() if k in cat), '#6b7280')
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:99px;font-size:.75em">{cat}</span>'

def source_badge(src):
    multi = re.search(r'\((\d+)ソース(🔥+)\)', src)
    if multi:
        plain = re.sub(r'\s*\(\d+ソース🔥+\)', '', src).strip()
        b = (f'<span style="background:#f59e0b;color:#fff;padding:1px 6px;'
             f'border-radius:99px;font-size:.7em;margin-left:3px">'
             f'{multi.group(1)}ソース{multi.group(2)}</span>')
        return plain + b
    return src

def build_html(top10, cat_stats, total_cats, words, summary, period):
    summary_html = f'<div class="summary-box">{summary}</div>' if summary else ''

    cards = ''
    for i, a in enumerate(top10, 1):
        cards += (
            f'<div class="card">'
            f'<div class="rank">#{i}</div>'
            f'<div><div class="card-title"><a href="{a["url"]}">{a["title"]}</a></div>'
            f'<div class="card-meta">{source_badge(a["source"])} &nbsp;{badge(a["category"])}'
            f'<span class="date">{a["date"]}</span></div></div></div>'
        )

    cat_html = ''
    for cat, cnt in cat_stats[:7]:
        pct = round(cnt / total_cats * 100)
        cat_html += (
            f'<div class="cat-row"><span class="cat-name">{badge(cat)}</span>'
            f'<span class="cat-cnt">{cnt}件</span>'
            f'<span class="cat-bar"><span style="width:{pct}%;background:#4f46e5;'
            f'display:inline-block;height:8px;border-radius:4px"></span></span></div>'
        )

    words_html = ''.join(
        f'<span style="background:#fef3c7;color:#92400e;padding:4px 10px;'
        f'border-radius:99px;font-size:.85em;margin:3px">{w}</span>'
        for w in words
    )

    return f"""<!DOCTYPE html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>週間トレンド {TODAY_FMT}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f3f4f6;color:#1f2937;padding:1em;line-height:1.6}}
h1{{font-size:1.2em;color:#111827;margin:.5em 0 1em;padding-bottom:.4em;border-bottom:2px solid #4f46e5}}
h2{{font-size:1em;margin:1.5em 0 .75em;color:#374151}}
a{{color:#4f46e5;text-decoration:none}}a:hover{{text-decoration:underline}}
.summary-box{{background:#eef2ff;border-left:4px solid #4f46e5;border-radius:0 8px 8px 0;padding:.75em 1em;margin-bottom:1.25em;font-size:.9em;color:#3730a3;line-height:1.7}}
.period{{background:#e0e7ff;border-radius:8px;padding:.5em 1em;font-size:.82em;color:#3730a3;margin-bottom:1em}}
.card{{background:#fff;border-radius:12px;padding:1em;margin-bottom:.75em;box-shadow:0 1px 3px rgba(0,0,0,.1);display:flex;gap:.75em;align-items:flex-start}}
.rank{{font-size:1.4em;font-weight:bold;color:#d1d5db;min-width:2em;text-align:center;padding-top:.1em}}
.card-title{{font-size:.95em;font-weight:bold;margin-bottom:.3em}}
.card-meta{{font-size:.78em;color:#6b7280;display:flex;align-items:center;gap:.4em;flex-wrap:wrap}}
.date{{color:#9ca3af;margin-left:auto}}
.cat-row{{display:flex;align-items:center;gap:.75em;padding:.4em 0;border-bottom:1px solid #f3f4f6;font-size:.9em}}
.cat-name{{min-width:9em}}.cat-cnt{{min-width:3em;text-align:right;color:#6b7280}}
.cat-bar{{flex:1}}
.words{{display:flex;flex-wrap:wrap;gap:.3em;margin:.5em 0}}
</style></head>
<body>
<h1>📊 週間トレンドまとめ {TODAY_FMT}</h1>
<div class="period">📅 対象期間: {period} &nbsp;|&nbsp; ★★★ 記事 {total_cats}件</div>
{summary_html}
<h2>🏆 週間ベスト10</h2>
{cards}
<h2>📊 カテゴリ別集計</h2>
{cat_html}
<h2>🔥 急上昇ワード</h2>
<div class="words">{words_html}</div>
</body></html>"""

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f'=== Weekly Summary {TODAY_FMT} ===')

    all_articles = load_weekly_articles()
    if not all_articles:
        print('No daily files found. Skipping.')
        return
    print(f'Loaded {len(all_articles)} ★★★ articles from daily files')

    top10 = score_articles(all_articles)
    cat_stats, total_cats = category_stats(all_articles)
    words = trending_words(all_articles)

    start = (TODAY - timedelta(days=6)).strftime('%Y-%m-%d')
    period = f'{start} 〜 {TODAY_FMT}'

    print('Generating summary...')
    summary = generate_summary(top10)

    # Markdown
    pathlib.Path(MD_PATH).parent.mkdir(parents=True, exist_ok=True)
    lines = [f'# 週間トレンドまとめ {TODAY_FMT}\n',
             f'> 対象期間: {period}｜★★★ 記事 {len(all_articles)}件\n']
    if summary:
        lines += ['## 今週のまとめ\n', summary, '']
    lines += ['## 🏆 週間ベスト10\n',
              '| # | タイトル | ソース | カテゴリ | 掲載日 |',
              '|---|---|---|---|---|']
    for i, a in enumerate(top10, 1):
        lines.append(f'| {i} | [{a["title"]}]({a["url"]}) | {a["source"]} | {a["category"]} | {a["date"]} |')
    lines += ['\n## 📊 カテゴリ別集計\n',
              '| カテゴリ | 件数 |', '|---|---|']
    for cat, cnt in cat_stats[:7]:
        lines.append(f'| {cat} | {cnt} |')
    if words:
        lines += ['\n## 🔥 急上昇ワード\n',
                  ' '.join(f'`{w}`' for w in words)]
    pathlib.Path(MD_PATH).write_text('\n'.join(lines), encoding='utf-8')
    print(f'Saved: {MD_PATH}')

    # HTML
    pathlib.Path(HTML_PATH).write_text(
        build_html(top10, cat_stats, len(all_articles), words, summary, period),
        encoding='utf-8'
    )
    print(f'Saved: {HTML_PATH}')

    # Discord
    if DISCORD_WEBHOOK:
        html_url = f'{GITHUB_PAGES_BASE}/ideas/weekly/{DATE}-weekly.html'
        msg = (f'**【AIキュレーター】{TODAY_FMT} 週間まとめ**\n'
               f'対象期間: {period} / ★★★ {len(all_articles)}件\n\n'
               f'🌐 {html_url}\n📄 {MD_PATH}')
        subprocess.run([
            'curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
            '-X', 'POST', DISCORD_WEBHOOK,
            '-F', f'payload_json={json.dumps({"content": msg})}',
            '-F', f'file1=@{MD_PATH}',
        ], capture_output=True, text=True)
    print('=== Done ===')

if __name__ == '__main__':
    main()
