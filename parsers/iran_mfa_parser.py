import re
from html import unescape
from urllib.parse import urljoin

from parsers.generic_html_parser import strip_html

KEYWORDS = (
    'statement',
    'iran',
    'foreign ministry',
    'minister',
    'spokesman',
    'region',
    'sanctions',
    'gaza',
    'israel',
    'united states',
    'security council',
    'ceasefire',
    'aggression',
    'diplomacy',
    'foreign affairs',
)

DATE_RE = re.compile(r'(20\d{2}/\d{2}/\d{2}|[A-Z][a-z]{2},\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})')
A_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def _clean(text: str) -> str:
    text = strip_html(text or '')
    return ' '.join(unescape(text).split()).strip()


def _is_good_title(title: str) -> bool:
    if not title:
        return False
    lower = title.lower()
    if len(title) < 18:
        return False
    bads = (
        'continues',
        'more',
        'pictures',
        'videos',
        'contacts',
        'overview',
        'embassies',
        'consulates',
        'travel to iran',
        'covid-19',
        'feedback',
        'quick access',
        'links',
    )
    if any(b in lower for b in bads):
        return False
    return True


def _looks_relevant(title: str) -> bool:
    lower = title.lower()
    return any(k in lower for k in KEYWORDS)


def parse_iran_mfa_html(html: str, base_url: str):
    items = []
    seen = set()

    # 1) İlk geçiş: tüm anchor'ları tara, daha esnek filtre uygula
    matches = list(A_RE.finditer(html))
    for m in matches:
        href = unescape(m.group(1)).strip()
        inner = m.group(2)
        title = _clean(inner)

        if not _is_good_title(title):
            continue

        full_url = urljoin(base_url, href)
        key = (title.lower(), full_url)
        if key in seen:
            continue

        context = html[max(0, m.start() - 160): min(len(html), m.end() + 220)]
        ctx_clean = _clean(context)
        pub_date_match = DATE_RE.search(ctx_clean)
        pub_date = pub_date_match.group(1) if pub_date_match else ''

        # ilgili başlıkları doğrudan al; ayrıca "Statements"/"Events" yakınlığını bonus kabul et
        context_lower = ctx_clean.lower()
        section_bonus = ('statements' in context_lower) or ('events' in context_lower)
        if not (_looks_relevant(title) or section_bonus):
            continue

        seen.add(key)
        items.append({
            'title': title,
            'link': full_url,
            'pub_date': pub_date,
            'description': '',
        })

    # 2) Eğer yine az çıktı varsa, görünür metindeki section linklerini gevşek yakala
    if len(items) < 5:
        rough_links = []
        for m in matches:
            href = unescape(m.group(1)).strip()
            title = _clean(m.group(2))
            if _is_good_title(title):
                rough_links.append((title, urljoin(base_url, href)))

        for title, full_url in rough_links:
            key = (title.lower(), full_url)
            if key in seen:
                continue
            if _looks_relevant(title):
                seen.add(key)
                items.append({
                    'title': title,
                    'link': full_url,
                    'pub_date': '',
                    'description': '',
                })

    # 3) Dedupe + limit
    deduped = []
    used_titles = set()
    for item in items:
        t = item['title'].lower().strip()
        if t in used_titles:
            continue
        used_titles.add(t)
        deduped.append(item)

    return deduped[:20]
