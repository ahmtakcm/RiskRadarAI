import re
from html import unescape
from urllib.parse import urljoin


_ITEM_RE = re.compile(
    r'<span[^>]*class="date-display-single"[^>]*>(.*?)</span>.*?'
    r'<div[^>]*class="field-title"[^>]*>.*?'
    r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html_text(value: str) -> str:
    text = _TAG_RE.sub(" ", value or "")
    return " ".join(unescape(text).split())


def parse_truth_social_archive(html: str, base_url: str):
    items = []
    seen = set()
    for raw_date, href, raw_title in _ITEM_RE.findall(html or ""):
        title = _clean_html_text(raw_title)
        pub_date = _clean_html_text(raw_date)
        if not title.lower().startswith("truth social posts of "):
            continue
        link = urljoin(base_url, unescape(href).strip())
        if link in seen:
            continue
        seen.add(link)
        items.append({
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "description": "American Presidency Project Truth Social archive listing",
        })
        if len(items) >= 40:
            break
    return items