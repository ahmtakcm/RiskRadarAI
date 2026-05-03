import re
from urllib.parse import urljoin, urlparse
from html import unescape


def parse_link_listing(html: str, base_url: str):
    items = []
    seen = set()
    base_domain = urlparse(base_url).netloc
    pattern = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
    for href, inner in pattern.findall(html):
        href = unescape(href).strip()
        text = re.sub(r'<[^>]+>', ' ', inner)
        text = ' '.join(unescape(text).split())
        if len(text) < 12:
            continue
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.scheme not in ('http', 'https'):
            continue
        if base_domain and parsed.netloc and base_domain not in parsed.netloc and not full_url.lower().endswith('.pdf'):
            continue
        lowered = text.lower()
        if any(skip in lowered for skip in ['privacy', 'cookie', 'terms', 'accessibility', 'subscribe', 'login']):
            continue
        key = (text, full_url)
        if key in seen:
            continue
        seen.add(key)
        desc = 'PDF rapor bağlantısı' if full_url.lower().endswith('.pdf') else ''
        items.append({'title': text, 'link': full_url, 'pub_date': '', 'description': desc})
        if len(items) >= 40:
            break
    return items
