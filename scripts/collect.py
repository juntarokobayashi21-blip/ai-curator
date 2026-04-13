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

# .env 読み込み
_env = pathlib.Path(__file__).parent.parent / '.env'
if _env.exists():
    for _line in _env.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.startswith('#'):
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')
DATE  = datetime.now(JST).strftime('%Y%m%d')

GITHUB_TOKEN      = os.environ.get('GITHUB_TOKEN', '')
DISCORD_WEBHOOK   = os.environ.get('DISCORD_WEBHOOK_URL', '')
SKIP_DISCORD      = os.environ.get('SKIP_DISCORD', '') == '1'
GITHUB_PAGES_BASE = 'https://juntarokobayashi21-blip.github.io/ai-curator'
MD_PATH   = f'ideas/daily/{DATE}-trend.md'
HTML_PATH = f'ideas/daily/{DATE}-trend.html'

# ─── Fetch helpers ────────────────────────────────────────────────────────────

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 news-collector/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  [WARN] {url}: {e}')
        return ''

def parse_rss(xml, source):
    out = []
    for item in re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)[:20]:
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
    out = []
    for item in re.findall(r'<item>(.*?)</item>', get('https://b.hatena.ne.jp/hotentry/it.rss'), re.DOTALL)[:30]:
        title = re.search(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', item)
        link  = re.search(r'<link>(.*?)</link>', item)
        bm    = re.search(r'<hatena:bookmarkcount>(\d+)</hatena:bookmarkcount>', item)
        if title and link:
            out.append({
                'title':  (title.group(1) or '').strip(),
                'url':    (link.group(1) or '').strip(),
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
    it  = parse_rss(get('https://news.google.com/rss/search?q=technology&hl=ja&gl=JP&ceid=JP:ja'), 'GoogleNews(IT)')
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
                    'title':  d['title'],
                    'url':    f"https://reddit.com{d['permalink']}",
                    'source': f"Reddit/r/{sub}({d['score']})",
                })
        except Exception as e:
            print(f'  [WARN] Reddit/{sub}: {e}')
    return out

# ─── AI helper ────────────────────────────────────────────────────────────────

def call_ai(messages, temperature=0.3, timeout=60):
    """GitHub Models API を呼び出してテキストを返す。失敗時は None。"""
    if not GITHUB_TOKEN:
        return None
    payload = json.dumps({
        'model': 'gpt-4o-mini',
        'messages': messages,
        'temperature': temperature,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://models.inference.ai.azure.com/chat/completions',
        data=payload,
        headers={'Authorization': f'Bearer {GITHUB_TOKEN}', 'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())['choices'][0]['message']['content']
    except Exception as e:
        print(f'[WARN] AI API failed: {e}')
        return None

# ─── Keyword fallback evaluation ──────────────────────────────────────────────

KEYWORDS = {
    'AI開発': {
        'high': ['LLM','llm','AI','人工知能','GPT','Claude','Gemini','agent','エージェント',
                 'プロンプト','RAG','機械学習','deep learning','transformer','OpenAI','Anthropic',
                 'コーディング','vibe coding','バイブコーディング','Claude Code','Copilot'],
        'mid':  ['モデル','推論','ファインチューニング','embedding','生成AI','自動化'],
    },
    'セキュリティ': {
        'high': ['CVE','脆弱性','マルウェア','ransomware','ランサム','hack','hacked','breach',
                 'exploit','zero-day','ゼロデイ','インシデント','セキュリティ','phishing'],
        'mid':  ['認証','暗号','パスワード','WAF','firewall','SIEM','SOC'],
    },
    '個人開発': {
        'high': ['SaaS','indie hacker','個人開発','副業','収益化','ノーコード','no-code',
                 'side project','個人事業','フリーランス'],
        'mid':  ['スタートアップ','起業','プロダクト','launch'],
    },
    '自動運転': {
        'high': ['自動運転','Tesla','Waymo','EV','電気自動車','autonomous','自動車'],
        'mid':  ['LIDAR','センサー','車載'],
    },
    'キャリア/転職': {
        'high': ['転職','給与','年収','salary','採用','リモートワーク','エンジニア市場',
                 'career','job','layoff','レイオフ','解雇','QA','エンジニア'],
        'mid':  ['働き方','スキル','評価','昇給'],
    },
    'テクノロジー企業': {
        'high': ['Google','Apple','Microsoft','Amazon','Meta','OpenAI','NVIDIA','Anthropic',
                 'スタートアップ','買収','M&A','資金調達','IPO'],
        'mid':  ['Big Tech','GAFAM','決算'],
    },
    'ビジネス動向': {
        'high': ['DX','デジタル変革','新規事業','市場','ビジネス','経営','戦略'],
        'mid':  ['業界','トレンド','導入事例'],
    },
}

def keyword_evaluate(articles):
    results = []
    for i, a in enumerate(articles):
        text = a['title']
        best_cat, best_score = '', 0
        for cat, kw in KEYWORDS.items():
            score = sum(3 for k in kw['high'] if k.lower() in text.lower())
            score += sum(1 for k in kw['mid']  if k.lower() in text.lower())
            if score > best_score:
                best_score, best_cat = score, cat
        if best_score >= 6:
            results.append({'index': i+1, 'rating': '★★★', 'category': best_cat})
        elif best_score >= 3:
            results.append({'index': i+1, 'rating': '★★',  'category': best_cat})
        elif best_score >= 1:
            results.append({'index': i+1, 'rating': '★',   'category': best_cat})
    return results

# ─── Evaluation ───────────────────────────────────────────────────────────────

def evaluate(articles):
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
  {{"index": 1, "rating": "★★★", "category": "AI開発"}},
  {{"index": 3, "rating": "★★",  "category": "セキュリティ"}},
  {{"index": 5, "rating": "★",   "category": "ビジネス動向"}}
]"""

    content = call_ai([{'role': 'user', 'content': prompt}], timeout=60)
    if content:
        m = re.search(r'\[.*\]', content, re.DOTALL)
        if m:
            result = json.loads(m.group())
            if result:
                print(f'[INFO] AI evaluated: {len(result)} articles')
                return result
        print('[WARN] AI returned empty evaluation')
    else:
        print('[INFO] GITHUB_TOKEN not set or API failed')

    print('[INFO] Falling back to keyword evaluation')
    result = keyword_evaluate(articles)
    print(f'[INFO] Keyword evaluated: {len(result)} articles')
    return result

# ─── Comments ─────────────────────────────────────────────────────────────────

def _comment_fallback(a):
    src = a.get('source', '')
    cat = a.get('category', '')
    n = re.search(r'\((\d+)\)', src)
    count = n.group(1) if n else None
    if 'はてブ' in src:
        base = f'はてブ{count}件を集めた{cat}分野の注目エントリ。' if count else f'{cat}分野のはてブ人気記事。'
        return base + '多くのエンジニアが注目しており、現場での関心の高さがうかがえる。ざっと目を通しておきたい一本。'
    if 'HN' in src:
        return f'Hacker Newsで話題になっている{cat}領域の記事。海外エンジニアコミュニティでの反応が大きく、グローバルなトレンドを把握するのに役立つ。英語だが概要だけでも確認しておく価値がある。'
    if 'Reddit' in src:
        base = f'Reddit で{count}upvotesを獲得した{cat}関連の投稿。' if count else f'{cat}分野の海外コミュニティ発の話題。'
        return base + 'コメント欄にも実践者の知見が集まりやすく、記事本文と合わせて読むと理解が深まる。'
    if 'Zenn' in src or 'Qiita' in src:
        return f'日本人エンジニアによる{cat}の実践的な解説記事。実際の開発経験をもとに書かれており、コードや具体例が豊富で手を動かしながら学べる内容になっている可能性が高い。'
    return f'{cat}分野の注目記事。実務や最新動向を把握するうえで参考になる内容が含まれている。気になるキーワードがあれば詳しく読んでみよう。'

def generate_comments(s3):
    """★★★ 記事に2〜3文のコメントを付与（API失敗時は定型文）"""
    if not s3:
        return s3
    numbered = '\n'.join(f'{i+1}. [{a.get("category","")}] {a["title"]}' for i, a in enumerate(s3))
    prompt = f"""以下の記事それぞれに、日本語で紹介コメントを書いてください。
各コメントは「背景」「注目点」「読む価値」の3点を含む2〜3文にしてください。

記事：
{numbered}

以下の形式で出力してください（番号と「|||」で区切る）：
1|||背景を説明する文。注目すべき点を説明する文。読む価値を説明する文。
2|||背景を説明する文。注目すべき点を説明する文。読む価値を説明する文。"""

    content = call_ai([
        {'role': 'system', 'content': 'あなたはITニュースのキュレーターです。各記事に必ず2〜3文（句点で区切られた複数の文）の日本語コメントを書いてください。1文だけのコメントは絶対に書かないでください。'},
        {'role': 'user',   'content': prompt},
    ], temperature=0.7, timeout=30)

    if content:
        cmap = {}
        for line in content.splitlines():
            m = re.match(r'^(\d+)\|\|\|(.+)', line.strip())
            if m:
                cmap[int(m.group(1))] = m.group(2).strip()
        if cmap:
            for i, a in enumerate(s3, 1):
                a['comment'] = cmap.get(i) or _comment_fallback(a)
            return s3

    for a in s3:
        a['comment'] = _comment_fallback(a)
    return s3

# ─── Summary ──────────────────────────────────────────────────────────────────

def _summary_fallback(s3):
    cats = {}
    for a in s3:
        for c in a.get('category', '').split('/'):
            c = c.strip()
            if c:
                cats[c] = cats.get(c, 0) + 1
    top = sorted(cats.items(), key=lambda x: x[1], reverse=True)
    total = len(s3)
    main_cat, main_cnt = top[0] if top else ('テクノロジー', total)
    second = f'次いで{top[1][0]}（{top[1][1]}件）が続きます。' if len(top) > 1 else ''
    titles_sample = '、'.join(f'「{a["title"][:20]}…」' for a in s3[:2])
    return (f'本日は{total}件の注目記事を収集しました。'
            f'{main_cat}関連が{main_cnt}件と最多で、{titles_sample}などが話題です。'
            f'{second}気になる記事をチェックしてみてください。')

def generate_summary(s3):
    """★★★ 記事をもとに今日のまとめ文を生成（API失敗時は定型文）"""
    if not s3:
        return ''
    titles = '\n'.join(f'- [{a.get("category","")}] {a["title"]}' for a in s3[:12])
    prompt = f"""以下は今日の注目ニュース（★★★）です。これらを踏まえ、今日のトレンドを3〜4文の日本語でまとめてください。

観点：
1. 今日もっとも多かったカテゴリとその傾向
2. 特に印象的だったトピック
3. 読者へのひと言（今日読むべき理由・注目ポイント）

記事：
{titles}

まとめ文のみ出力（箇条書き不要、3〜4文の連続した文章で）："""

    content = call_ai([{'role': 'user', 'content': prompt}], temperature=0.7, timeout=30)
    if content and content.strip():
        return content.strip()

    print('[INFO] Using fallback summary')
    return _summary_fallback(s3)

# ─── HTML ─────────────────────────────────────────────────────────────────────

def badge(cat):
    colors = {'AI開発':'#4f46e5','セキュリティ':'#dc2626','個人開発':'#16a34a',
              'キャリア':'#d97706','テクノロジー':'#0891b2','ビジネス':'#7c3aed'}
    color = next((c for k, c in colors.items() if k in cat), '#6b7280')
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:99px;font-size:.75em">{cat}</span>'

def build_html(s3, s2, s1, summary=''):
    summary_html = f'<div class="summary-box">{summary}</div>' if summary else ''
    def fmt_comment(text):
        # 句点ごとに改行を入れる（末尾の句点は除く）
        return re.sub(r'。(?!$)', '。<br>', text.strip().rstrip('。')) + '。'

    cards = ''.join(
        f'<div class="card"><div class="card-title"><a href="{a["url"]}">{a["title"]}</a></div>'
        f'<div class="card-meta">{a["source"]} &nbsp;{badge(a.get("category",""))}</div>'
        f'<div class="card-comment">{fmt_comment(a.get("comment",""))}</div></div>'
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
.summary-box{{background:#eef2ff;border-left:4px solid #4f46e5;border-radius:0 8px 8px 0;padding:.75em 1em;margin-bottom:1.25em;font-size:.9em;color:#3730a3;line-height:1.7}}
</style></head>
<body>
<h1>📰 トレンドニュース {TODAY}</h1>
{summary_html}
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
            a = {**articles[idx], 'category': ev.get('category', '')}
            rated.setdefault(ev['rating'], []).append(a)

    s3 = rated.get('★★★', [])
    s2 = rated.get('★★', [])
    s1 = rated.get('★', [])
    print(f'★★★:{len(s3)}  ★★:{len(s2)}  ★:{len(s1)}')

    print('Generating comments for ★★★ articles...')
    s3 = generate_comments(s3)

    print('Generating summary...')
    summary = generate_summary(s3)
    print(f'Summary: {summary[:60]}...' if len(summary) > 60 else f'Summary: {summary}')

    # Markdown
    pathlib.Path(MD_PATH).parent.mkdir(parents=True, exist_ok=True)
    lines = [f'# トレンドニュース {TODAY}\n']
    if summary:
        lines += ['## 今日のまとめ\n', summary, '']
    lines += ['## ★★★ 注目記事\n',
              '| タイトル | ソース | カテゴリ | コメント |', '|---|---|---|---|']
    for a in s3:
        lines.append(f'| [{a["title"]}]({a["url"]}) | {a["source"]} | {a["category"]} | {a.get("comment","")} |')
    lines += ['\n## ★★ 気になる記事\n', '| タイトル | ソース | カテゴリ |', '|---|---|---|']
    for a in s2:
        lines.append(f'| [{a["title"]}]({a["url"]}) | {a["source"]} | {a["category"]} |')
    lines.append('\n## ★ その他\n')
    for a in s1:
        lines.append(f'- [{a["title"]}]({a["url"]}) — {a["source"]}')
    pathlib.Path(MD_PATH).write_text('\n'.join(lines), encoding='utf-8')
    print(f'Saved: {MD_PATH}')

    # HTML
    pathlib.Path(HTML_PATH).write_text(build_html(s3, s2, s1, summary), encoding='utf-8')
    print(f'Saved: {HTML_PATH}')

    # Discord
    if SKIP_DISCORD:
        print('Discord: skipped (SKIP_DISCORD=1)')
    else:
        notify()

    print('=== Done ===')

def notify():
    """生成済みのMDファイルからDiscord通知だけ送る"""
    if not DISCORD_WEBHOOK:
        print('Discord: skipped (no webhook)')
        return
    if not pathlib.Path(MD_PATH).exists():
        print(f'[WARN] {MD_PATH} not found, skipping notification')
        return

    # ★★★ のタイトルをMDから抽出
    md = pathlib.Path(MD_PATH).read_text(encoding='utf-8')
    s3_titles = []
    m = re.search(r'## ★★★ 注目記事\n(.*?)(?=\n## |\Z)', md, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            tm = re.match(r'\|\s*\[(.+?)\]', line)
            if tm:
                s3_titles.append(tm.group(1))

    html_url = f'{GITHUB_PAGES_BASE}/ideas/daily/{DATE}-trend.html'
    header = (f'**【AIキュレーター】{TODAY} トレンドニュース**\n'
              f'★★★ 注目記事 {len(s3_titles)}件\n\n')
    footer = f'\n🌐 {html_url}\n📄 {MD_PATH}'
    items = ''
    for title in s3_titles:
        line = f'▶ {title}\n'
        if len(header) + len(items) + len(line) + len(footer) > 1900:
            items += f'…他{len(s3_titles) - items.count("▶")}件\n'
            break
        items += line
    msg = header + items + footer

    r = subprocess.run([
        'curl', '-s', '-w', '\n%{http_code}',
        '-X', 'POST', DISCORD_WEBHOOK,
        '-F', f'payload_json={json.dumps({"content": msg})}',
        '-F', f'file1=@{MD_PATH}',
    ], capture_output=True, text=True)
    *body_lines, status = r.stdout.strip().splitlines()
    print(f'Discord: HTTP {status}')
    if status != '200':
        print(f'Discord error: {"".join(body_lines)}')


if __name__ == '__main__':
    import sys
    if '--notify-only' in sys.argv:
        notify()
    else:
        main()
