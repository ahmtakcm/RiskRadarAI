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
    # American Presidency Project exposes archive index pages such as
    # "Truth Social Posts of June X". Those pages are not events and this
    # parser does not extract individual post bodies, so returning them would
    # create generic Telegram alerts. Keep them out of the common summary
    # pipeline until real post content extraction is available.
    return []
