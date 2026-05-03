import re

from parsers.link_listing_parser import parse_link_listing


_ALLOWED_LINK_RE = re.compile(
    r'/MEDIA/PRESS-RELEASES/Press-Release-View/Article/\d+/',
    re.IGNORECASE,
)

_BLOCKED_LINK_PARTS = (
    '/ARABIC-PRESS-RELEASES/',
    '/RUSSIAN-PRESS-RELEASES/',
    '/HEBREW-PRESS-RELEASES/',
    '/FARSI-PRESS-RELEASES/',
    '/URDU-PRESS-RELEASES/',
    '/MEDIA/NEWS-ARTICLES/',
    '/Home/FOIA/',
    '/CIVILIAN-HARM-REPORT/',
    '/Portals/',
)

_NOISE_TITLE_PATTERNS = [
    re.compile(r'^\s*skip to main content', re.IGNORECASE),
    re.compile(r'^\s*press releases\s*$', re.IGNORECASE),
    re.compile(r'^\s*public releases\s*$', re.IGNORECASE),
    re.compile(r'^\s*news archives\s*$', re.IGNORECASE),
    re.compile(r'^\s*press release archive\s*$', re.IGNORECASE),
    re.compile(r'^\s*\d+\s*$', re.IGNORECASE),
    re.compile(r'^\s*\.\.\.\s*$', re.IGNORECASE),
]


def _is_valid_press_release(title: str, link: str) -> bool:
    title = (title or "").strip()
    link = (link or "").strip()

    if not title or not link:
        return False

    for pattern in _NOISE_TITLE_PATTERNS:
        if pattern.search(title):
            return False

    upper_link = link.upper()
    for piece in _BLOCKED_LINK_PARTS:
        if piece.upper() in upper_link:
            return False

    if not _ALLOWED_LINK_RE.search(link):
        return False

    return True


def parse_centcom_listing(html: str, base_url: str):
    items = parse_link_listing(html or '', base_url)

    cleaned = []
    seen = set()

    for item in items:
        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()

        if not _is_valid_press_release(title, link):
            continue

        key = (title.lower(), link.lower())
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(item)

    return cleaned[:20]
