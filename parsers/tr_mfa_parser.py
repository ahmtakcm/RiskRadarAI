import re
from html import unescape
from urllib.parse import urljoin

BASE = "https://www.mfa.gov.tr"

BAD_TITLES = {
    "Açıklamalar",
    "Güncel Açıklamalar",
    "Diğer Bakanlık Açıklamaları...",
    "Duyurular",
    "Basın Merkezi",
    "Dış Politika",
    "Bakanlık",
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


def _looks_like_real_mfa_title(title: str, href: str) -> bool:
    t = title.strip()
    h = href.lower()

    if not t or t in BAD_TITLES:
        return False

    # sub.tr.mfa kategori/listedir, tekil açıklama değildir
    if "sub.tr.mfa" in h:
        return False

    # Tekil açıklama URL'leri genelde slug.tr.mfa formatında olur
    if not h.endswith(".tr.mfa"):
        return False

    markers = [
        "No:",
        "SC-",
        "QA-",
        "Seyahat Duyurusu",
        "Güvenlik ve Seyahat",
        "Basın Açıklaması",
        "Hk.",
        "Hakkında",
    ]

    return any(m.lower() in t.lower() for m in markers)


def parse_listing(html: str, source_name: str = "TR MFA Açıklamalar"):
    items = []
    seen = set()

    for m in re.finditer(
        r'<a[^>]+href=["\']([^"\']+\.tr\.mfa)["\'][^>]*>(.*?)</a>',
        html,
        re.I | re.S,
    ):
        href, title_html = m.group(1), m.group(2)
        title = _strip_html(title_html)

        if not _looks_like_real_mfa_title(title, href):
            continue

        url = urljoin(BASE, href)
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
    title = None
    m_title = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if m_title:
        title = _strip_html(m_title.group(1))

    text = _strip_html(html)

    start_markers = ["No:", "SC-", "QA-", "İran’a Yönelik", "İran'a Yönelik", "Güvenlik ve Seyahat", "Basın Açıklaması"]
    for marker in start_markers:
        idx = text.find(marker)
        if 0 <= idx < 2500:
            text = text[idx:]
            break

    end_markers = [
        "Yurtdışındaki Temsilciliklerimiz",
        "Türkiye Cumhuriyeti Dışişleri Bakanlığı Tarihçesi",
        "Bilgi Edinme",
        "Sosyal Medya",
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
