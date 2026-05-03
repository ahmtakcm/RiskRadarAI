import re
from html import unescape
from parsers.generic_html_parser import strip_html


def parse_whitehouse_html(html: str, base_url: str):
    items = []
    seen = set()
    pattern = re.compile(r'<a[^>]+href="(https://www\.whitehouse\.gov/[^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    for href, inner in pattern.findall(html):
        title = strip_html(inner)
        if len(title) < 12:
            continue
        key = (href, title.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append({
            'title': unescape(title),
            'link': href,
            'pub_date': '',
            'description': '',
        })
    return items[:20]
