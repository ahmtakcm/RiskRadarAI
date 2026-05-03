import json
import re
import sys
import time
import requests
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse
from xml.etree import ElementTree as ET
from html import unescape

PENDING_PATH = Path("user_inputs/source_pending.json")
FEEDS_PATH = Path("rules/feeds.json")

SEARCH_URL = "https://duckduckgo.com/html/?q={q}"

PROFILE_QUERIES = {
    "resmi_kritik": [
        "{q} official rss",
        "{q} ministry rss",
        "{q} government press release rss",
        "{q} defense ministry rss",
        "{q} foreign ministry rss",
    ],
    "haber": [
        "{q} news rss",
        "{q} world news rss",
        "{q} breaking news rss",
        "{q} agency rss",
    ],
    "ekonomi": [
        "{q} economy rss",
        "{q} market news rss",
        "{q} oil market RSS feed",
        "{q} energy news RSS feed",
        "{q} commodity news RSS feed",
        "{q} central bank rss",
        "site:eia.gov rss {q}",
        "site:iea.org rss {q}",
        "site:oilprice.com rss {q}",
        "site:investing.com rss {q}",
    ],
    "osint": [
        "{q} osint rss",
        "{q} conflict rss",
        "{q} military updates rss",
        "{q} geopolitical risk rss",
    ],
    "saglik": [
        "{q} health rss",
        "{q} who health news rss",
        "{q} disease outbreak rss",
        "{q} public health rss",
    ],
}

RSS_PATHS = [
    "/rss",
    "/rss.xml",
    "/feed",
    "/feed.xml",
    "/atom.xml",
    "/news/rss",
    "/news/rss.xml",
    "/rss/news",
    "/rss/latest",
    "/rss/all",
    "/feed/rss",
    "/news/feed",
]

BAD_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "tiktok.com", "pinterest.com", "reddit.com"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 RiskRadarAI/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def domain_of(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def is_bad_domain(url):
    d = domain_of(url)
    return any(d == bad or d.endswith("." + bad) for bad in BAD_DOMAINS)


def strip_html(text):
    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def search_web(query, limit=8):
    url = SEARCH_URL.format(q=quote_plus(query))
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception:
        return []

    links = []
    # DuckDuckGo result links
    for m in re.finditer(r'href="([^"]+)"', r.text):
        href = unescape(m.group(1))
        if not href.startswith("http"):
            continue
        if "duckduckgo.com" in href:
            continue
        if is_bad_domain(href):
            continue
        if href not in links:
            links.append(href)
        if len(links) >= limit:
            break
    return links


def discover_rss_from_html(page_url, html):
    found = []

    # <link rel="alternate" type="application/rss+xml" href="...">
    for m in re.finditer(r'<link[^>]+>', html, re.I):
        tag = m.group(0)
        low = tag.lower()
        if "alternate" not in low:
            continue
        if "rss" not in low and "atom" not in low and "xml" not in low:
            continue
        hm = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if hm:
            found.append(urljoin(page_url, hm.group(1)))

    # Direkt görünen RSS linkleri
    for m in re.finditer(r'href=["\']([^"\']+(?:rss|feed|atom)[^"\']*)["\']', html, re.I):
        found.append(urljoin(page_url, m.group(1)))

    return list(dict.fromkeys(found))


def candidate_paths(site_url):
    parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return [base + p for p in RSS_PATHS]


def test_rss(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code < 200 or r.status_code >= 400:
            return False, f"HTTP {r.status_code}", 0, ""

        text_low = r.text.lower()
        if not ("<rss" in text_low or "<feed" in text_low or "<item" in text_low or "<entry" in text_low):
            try:
                ET.fromstring(r.content)
            except Exception:
                return False, "RSS/XML değil", 0, ""

        item_count = len(re.findall(r"<item\b|<entry\b", text_low))
        title = ""
        mt = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S)
        if mt:
            title = strip_html(mt.group(1))[:80]

        if item_count <= 0:
            return False, "item yok", 0, title

        return True, "RSS OK", item_count, title
    except Exception as exc:
        return False, str(exc)[:140], 0, ""


def guess_profiles(url, title, requested_profile):
    blob = f"{url} {title}".lower()
    profiles = set()

    if requested_profile and requested_profile != "all":
        profiles.add(requested_profile)

    if any(x in blob for x in ["mfa", "ministry", "government", ".gov", "defense", "whitehouse", "centralbank"]):
        profiles.add("resmi_kritik")
    if any(x in blob for x in ["oil", "energy", "market", "economy", "finance", "bank", "commodity", "eia", "iea"]):
        profiles.add("ekonomi")
    if any(x in blob for x in ["osint", "conflict", "military", "war", "intel", "defender"]):
        profiles.add("osint")
    if any(x in blob for x in ["health", "who", "disease", "outbreak", "medical"]):
        profiles.add("saglik")
    if any(x in blob for x in ["news", "world", "agency", "rss"]):
        profiles.add("haber")

    profiles.add("tum_profiller")

    order = ["resmi_kritik", "haber", "ekonomi", "osint", "saglik", "tum_profiller"]
    return [p for p in order if p in profiles]


def make_name(url, title):
    d = domain_of(url)
    base = title or d or "RSS Source"
    base = re.sub(r"\s+", " ", base).strip()
    if len(base) < 4:
        base = d
    name = base[:60]
    if "rss" not in name.lower():
        name += " RSS"
    return name


def build_queries(profile, query):
    q = query.strip()
    if not q:
        q = profile

    if profile == "all":
        templates = []
        for arr in PROFILE_QUERIES.values():
            templates.extend(arr[:2])
    else:
        templates = PROFILE_QUERIES.get(profile, ["{q} rss", "{q} news rss"])

    return [t.format(q=q) for t in templates]


def main():
    args = sys.argv[1:]
    profile = "all"
    query_parts = []

    if args and args[0] in {"resmi_kritik", "haber", "ekonomi", "osint", "saglik", "all"}:
        profile = args[0]
        query_parts = args[1:]
    else:
        query_parts = args

    query = " ".join(query_parts).strip() or profile

    feeds = load_json(FEEDS_PATH, [])
    existing_names = {str(f.get("name", "")).lower() for f in feeds}
    existing_urls = {str(f.get("url", "")).lower() for f in feeds}

    pending = load_json(PENDING_PATH, {})

    seen_rss = set()
    accepted = []
    failed = []

    for search_query in build_queries(profile, query):
        pages = search_web(search_query, limit=6)

        for page in pages:
            if is_bad_domain(page):
                continue

            rss_candidates = []

            try:
                r = requests.get(page, headers=HEADERS, timeout=15)
                if 200 <= r.status_code < 400:
                    rss_candidates.extend(discover_rss_from_html(page, r.text))
            except Exception:
                pass

            rss_candidates.extend(candidate_paths(page))

            for rss_url in rss_candidates:
                rss_url = rss_url.split("#")[0]
                if rss_url.lower() in seen_rss:
                    continue
                seen_rss.add(rss_url.lower())

                if rss_url.lower() in existing_urls:
                    continue

                ok, reason, item_count, title = test_rss(rss_url)
                if not ok:
                    failed.append((rss_url, reason))
                    continue

                name = make_name(rss_url, title)
                original_name = name
                i = 2
                while name.lower() in existing_names or name in pending:
                    name = f"{original_name} {i}"
                    i += 1

                profiles = guess_profiles(rss_url, title, profile)

                pending[name] = {
                    "name": name,
                    "url": rss_url,
                    "kind": "rss",
                    "profiles": profiles,
                    "enabled": True,
                    "priority": 5,
                    "notes": f"Auto Source Intelligence bulundu. Query: {query}"
                }

                accepted.append((name, rss_url, item_count, profiles))

                if len(accepted) >= 8:
                    break

            if len(accepted) >= 8:
                break

        if len(accepted) >= 8:
            break

        time.sleep(1)

    save_json(PENDING_PATH, pending)

    print("🛰 Auto Source Intelligence Raporu")
    print(f"Profil: {profile}")
    print(f"Arama: {query}")
    print("")

    if accepted:
        print("✅ Onay bekleyen adaylar:")
        for name, url, item_count, profiles in accepted:
            print(f"- {name}")
            print(f"  URL: {url}")
            print(f"  Item: {item_count}")
            print(f"  Profil: {', '.join(profiles)}")
            print(f"  Onay: /kaynak_onay {name}")
    else:
        print("Uygun çalışan RSS adayı bulunamadı.")

    if failed:
        print("\n❌ Elenen ilk adaylar:")
        for url, reason in failed[:8]:
            print(f"- {reason} | {url}")


if __name__ == "__main__":
    main()
