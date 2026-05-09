#!/usr/bin/env python3
"""
Fetches latest luxury/sustainable tourism news from RSS feeds
and updates the NEWS_FALLBACK array in index.html.
Runs via GitHub Actions every 2 days.
"""
import urllib.request
import xml.etree.ElementTree as ET
import re
import html as html_mod
import sys
from datetime import datetime

FEEDS = [
    ('https://skift.com/feed/', 'Skift'),
    ('https://www.hospitalitynet.org/rss/8000102.rss', 'Hospitality Net'),
    ('https://sustainabletravel.org/feed/', 'Sustainable Travel Intl'),
    ('https://www.luxurytraveladvisor.com/rss.xml', 'Luxury Travel Advisor'),
    ('https://www.traveldailymedia.com/feed/', 'Travel Daily Media'),
]

TAG_MAP = [
    (['wellness', 'spa', 'health', 'yoga', 'wellbeing', 'bienestar', 'mindful'], '🧘 Wellness', '#A8D5BA'),
    (['sustain', 'eco', 'green', 'carbon', 'regenerat', 'sostenib', 'nature', 'wildlife', 'biodiversity'], '🌿 Sostenibilidad', '#00E5A0'),
    (['costa rica', 'manuel antonio', 'quepos', 'guanacaste', 'arenal'], '🇨🇷 Costa Rica', '#FFD700'),
    (['bleisure', 'business travel', 'corporate travel', 'hybrid work'], '💼 Bleisure', '#C8A882'),
    (['adventure', 'hiking', 'surf', 'rafting', 'zip line', 'expedition', 'explorer'], '🏄 Aventura', '#FF4C1C'),
    (['luxury', 'upscale', 'five-star', 'high-end', 'premium', 'ultra-luxury', 'boutique'], '🌟 Lujo', '#D4AF37'),
    (['revenue', 'occupancy', 'adr', 'revpar', 'market', 'forecast', 'demand', 'rate'], '📊 Mercado', '#4BA89A'),
    (['nomad', 'digital nomad', 'remote work', 'work from anywhere'], '💻 Nómada', '#00E5A0'),
]

MONTHS_ES = {
    'Jan': 'Ene', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Abr',
    'May': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
    'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dic',
}

def get_tag_color(text):
    text_lower = text.lower()
    for keywords, tag, color in TAG_MAP:
        if any(kw in text_lower for kw in keywords):
            return tag, color
    return '🌐 Turismo', '#4BA89A'

def clean_html(text):
    text = re.sub(r'<[^>]+>', '', text or '')
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_date(pub_date):
    for fmt in [
        '%a, %d %b %Y %H:%M:%S %z',
        '%a, %d %b %Y %H:%M:%S GMT',
        '%a, %d %b %Y %H:%M:%S +0000',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%SZ',
    ]:
        try:
            d = datetime.strptime((pub_date or '').strip(), fmt)
            month_en = d.strftime('%b')
            month_es = MONTHS_ES.get(month_en, month_en)
            return f"{month_es} {d.year}"
        except Exception:
            continue
    return datetime.now().strftime('%b %Y')

def fetch_feed(url, label):
    articles = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 ADM-NewsBot/1.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            content = r.read()
        root = ET.fromstring(content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//atom:entry', ns)

        for item in items[:5]:
            title = clean_html(item.findtext('title') or item.findtext('atom:title', '', ns))
            desc = clean_html(
                item.findtext('description') or
                item.findtext('content') or
                item.findtext('atom:summary', '', ns) or ''
            )
            link = item.findtext('link') or ''
            if not link:
                link_el = item.find('atom:link', ns)
                if link_el is not None:
                    link = link_el.get('href', '')
            pub_date = item.findtext('pubDate') or item.findtext('atom:published', '', ns) or ''

            if not title:
                continue

            desc_short = desc[:220] + ('…' if len(desc) > 220 else '')
            date_str = parse_date(pub_date)
            tag, color = get_tag_color(title + ' ' + desc)

            articles.append({
                'title': title,
                'desc': desc_short,
                'source': label,
                'date': date_str,
                'tag': tag,
                'color': color,
                'link': link,
            })
    except Exception as e:
        print(f'  ⚠ Error en {label}: {e}', file=sys.stderr)
    return articles

def js_str(s):
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ').replace('\r', '')

def articles_to_js(articles):
    lines = ['const NEWS_FALLBACK = [']
    for a in articles:
        lines.append(
            f"  {{title:'{js_str(a['title'])}',desc:'{js_str(a['desc'])}',source:'{js_str(a['source'])}'"
            f",date:'{a['date']}',tag:'{a['tag']}',color:'{a['color']}',link:'{js_str(a['link'])}'}}, "
        )
    lines.append('];')
    return '\n'.join(lines)

# ── Main ──────────────────────────────────────────────────────
all_articles = []
for url, label in FEEDS:
    print(f'Fetching {label}...')
    arts = fetch_feed(url, label)
    print(f'  → {len(arts)} artículos')
    all_articles.extend(arts)

if len(all_articles) < 4:
    print('Muy pocos artículos obtenidos. Manteniendo contenido existente.')
    sys.exit(0)

# Take up to 8, interleaved from different sources for variety
final = all_articles[:8]
print(f'\nTotal artículos seleccionados: {len(final)}')

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_js = articles_to_js(final)
updated, count = re.subn(
    r'const NEWS_FALLBACK = \[.*?\];',
    new_js,
    content,
    flags=re.DOTALL,
)

if count == 0:
    print('ERROR: No se encontró NEWS_FALLBACK en index.html', file=sys.stderr)
    sys.exit(1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(updated)

print(f'✅ index.html actualizado con {len(final)} noticias')
