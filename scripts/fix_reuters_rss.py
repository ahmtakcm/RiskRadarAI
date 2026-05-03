import json
import requests
from pathlib import Path
from xml.etree import ElementTree as ET

OLD_NAMES = {"Reuters World"}

CANDIDATES = [
    # haber
    ("Reuters Top News", "https://feeds.reuters.com/reuters/topNews", ["haber", "tum_profiller"], 9),
    ("Reuters World RSS", "https://feeds.reuters.com/Reuters/worldNews", ["haber", "tum_profiller"], 8),
    ("Reuters Politics", "https://feeds.reuters.com/Reuters/PoliticsNews", ["haber", "tum_profiller"], 7),

    # ekonomi
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews", ["ekonomi", "tum_profiller"], 8),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/marketsNews", ["ekonomi", "tum_profiller"], 8),
    ("Reuters Economy", "https://feeds.reuters.com/news/economy", ["ekonomi", "tum_profiller"], 8),
    ("Reuters Financials", "https://feeds.reuters.com/reuters/financialsNews", ["ekonomi", "tum_profiller"], 7),
    ("Reuters Dollar", "https://feeds.reuters.com/reuters/USdollarreportNews", ["ekonomi", "tum_profiller"], 7),

    # emtia / enerji
    ("Reuters Commodities", "https://feeds.reuters.com/reuters/commoditiesNews", ["ekonomi", "tum_profiller"], 8),
    ("Reuters Energy", "https://feeds.reuters.com/reuters/USenergyNews", ["ekonomi", "tum_profiller"], 8),
    ("Reuters Basic Materials", "https://feeds.reuters.com/reuters/basicmaterialsNews", ["ekonomi", "tum_profiller"], 6),

    # sağlık
    ("Reuters Health", "https://feeds.reuters.com/reuters/healthNews", ["saglik", "tum_profiller"], 7),

    # teknoloji opsiyonel ama haber değeri var
    ("Reuters Technology", "https://feeds.reuters.com/reuters/technologyNews", ["haber", "tum_profiller"], 6),
]


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rss_works(url):
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 RiskRadarAI/1.0"},
            timeout=15,
            allow_redirects=True,
        )
        if r.status_code != 200 or len(r.text) < 100:
            return False, f"HTTP {r.status_code}"

        root = ET.fromstring(r.content)
        tag = root.tag.lower()
        text = r.text.lower()

        if "rss" in tag or "<rss" in text or "<feed" in text or "<item" in text or "<entry" in text:
            return True, "OK"

        return False, "not rss/xml"
    except Exception as exc:
        return False, str(exc)[:160]


# 1) RSS adaylarını test et
working = []
failed = []

for name, url, profiles, priority in CANDIDATES:
    ok, reason = rss_works(url)
    if ok:
        working.append((name, url, profiles, priority))
    else:
        failed.append((name, url, reason))

print("\nÇALIŞAN REUTERS RSS:")
for x in working:
    print("✅", x[0], x[1])

print("\nÇALIŞMAYAN / PAS GEÇİLEN:")
for name, url, reason in failed:
    print("❌", name, "|", reason, "|", url)


# 2) feeds.json temizle + ekle
feeds_path = Path("rules/feeds.json")
feeds = load_json(feeds_path, [])

feeds = [f for f in feeds if f.get("name") not in OLD_NAMES]

for name, url, profiles, priority in working:
    feed = {
        "name": name,
        "url": url,
        "kind": "rss",
        "enabled": True,
        "priority": priority,
        "source_class": "news_agency",
        "source_family": "media",
        "official_class": "international_media",
        "notes": "Reuters RSS; HTML sayfa botta 401 verdiği için RSS tercih edildi."
    }

    found = False
    for f in feeds:
        if f.get("name") == name:
            f.update(feed)
            found = True
            break

    if not found:
        feeds.append(feed)

save_json(feeds_path, feeds)


# 3) Profillerden eski Reuters World kaldır, çalışanları ekle
profile_names = ["haber", "ekonomi", "saglik", "tum_profiller"]

for profile in profile_names:
    p = Path("profiles") / f"{profile}.json"
    if not p.exists():
        continue

    data = load_json(p, {})
    add_names = [name for name, url, profiles, priority in working if profile in profiles]

    for key in ("sources", "enabled_feeds"):
        arr = data.setdefault(key, [])
        arr = [x for x in arr if x not in OLD_NAMES]

        for name in add_names:
            if name not in arr:
                arr.append(name)

        data[key] = arr

    save_json(p, data)
    print("profile updated:", profile)


# 4) storage kalıntısı temizle
for sp in Path("storage").glob("*.json"):
    try:
        data = load_json(sp, None)
    except Exception:
        continue

    def clean(obj):
        if isinstance(obj, list):
            return [clean(x) for x in obj if not (isinstance(x, str) and x in OLD_NAMES) and not (isinstance(x, dict) and x.get("name") in OLD_NAMES)]
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items() if not (isinstance(v, str) and v in OLD_NAMES) and not (isinstance(v, dict) and v.get("name") in OLD_NAMES)}
        return obj

    new = clean(data)
    if new != data:
        save_json(sp, new)
        print("storage cleaned:", sp)

print("\nOK - Reuters RSS düzenlemesi tamam.")
