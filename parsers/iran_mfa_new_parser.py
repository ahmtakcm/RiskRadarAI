import re
from html import unescape
from urllib.parse import urljoin

BASE = "https://en.mfa.ir"

BAD_TITLES = {
    "Minister",
    "Minister of Foreign Affairs",
    "Consular, Parliamentary, Iranian Expat Affairs",
    "Ministry",
    "Foreign Policy",
    "Contact Us",
    "Archive",
    "News",
    "Photo",
    "Video",
    "Continues",
    "More",
    "Links",
    "Feedback",
    "Last Update",
}


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?is)</p\s*>", "\n", html)
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def _looks_like_real_title(title: str, href: str) -> bool:
    t = title.strip()
    h = href.lower().strip()

    if not t or t in BAD_TITLES:
        return False

    if len(t) < 20:
        return False

    # Asıl haber/açıklama linkleri NewsView altında
    if "newsview" not in h:
        return False

    bad_words = ["photo album", "video album", "virtual exhibitions"]
    if any(x in t.lower() for x in bad_words):
        return False

    return True


def parse_listing(html: str, source_name: str = "Iran MFA Official EN"):
    items = []
    seen = set()

    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href, title_html = m.group(1), m.group(2)
        title = _strip_html(title_html)

        if not _looks_like_real_title(title, href):
            continue

        url = urljoin(BASE + "/", href)
        if url in seen:
            continue
        seen.add(url)

        items.append({
            "title": title,
            "url": url,
            "source_name": source_name,
            "summary": title,
            "content": title,
        })

    return items


def parse_detail(html: str):
    m_title = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    title = _strip_html(m_title.group(1)) if m_title else None

    text = _strip_html(html)

    start_markers = [
        "Iranian Foreign Minister",
        "Foreign Ministry spokesman",
        "Foreign Ministry Spokesman",
        "The spokesman",
        "Iran strongly",
        "In a statement",
        "Remarks by",
        "Statements by",
    ]

    for marker in start_markers:
        idx = text.find(marker)
        if 0 <= idx < 2500:
            text = text[idx:]
            break

    end_markers = [
        "Related News",
        "Most Viewed",
        "Archive",
        "Contact Us",
        "Links",
        "Last Update",
    ]

    for marker in end_markers:
        idx = text.find(marker)
        if idx > 300:
            text = text[:idx]
            break

    return {
        "title": title,
        "content": text[:4000],
        "summary": text[:900],
    }
