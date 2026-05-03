import json
import requests
from pathlib import Path
from xml.etree import ElementTree as ET

FEEDS_PATH = Path("rules/feeds.json")
PROFILES_DIR = Path("profiles")
STORAGE_DIR = Path("storage")

# Buraya ileride yeni kaynakları ekleyeceğiz
SOURCE_PLAN = [
    {
        "name": "Reuters World RSS",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
        "kind": "rss",
        "profiles": ["haber", "tum_profiller"],
        "replace": ["Reuters World"],
        "priority": 8,
        "source_class": "news_agency",
        "source_family": "media",
    },
    {
        "name": "Reuters Top News",
        "url": "https://feeds.reuters.com/reuters/topNews",
        "kind": "rss",
        "profiles": ["haber", "tum_profiller"],
        "replace": ["Reuters World"],
        "priority": 9,
        "source_class": "news_agency",
        "source_family": "media",
    },
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "kind": "rss",
        "profiles": ["ekonomi", "tum_profiller"],
        "replace": [],
        "priority": 8,
        "source_class": "news_agency",
        "source_family": "media",
    },
    {
        "name": "Reuters Commodities",
        "url": "https://feeds.reuters.com/reuters/commoditiesNews",
        "kind": "rss",
        "profiles": ["ekonomi", "tum_profiller"],
        "replace": [],
        "priority": 8,
        "source_class": "news_agency",
        "source_family": "media",
    },
]


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


def check_source(src):
    url = src["url"]
    kind = src.get("kind", "rss")

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 RiskRadarAI/1.0"},
            timeout=15,
            allow_redirects=True,
        )

        if r.status_code < 200 or r.status_code >= 400:
            return False, f"HTTP {r.status_code}"

        if kind in ("rss", "rss_social"):
            text = r.text.lower()
            if "<rss" in text or "<feed" in text or "<item" in text or "<entry" in text:
                return True, "OK"

            try:
                ET.fromstring(r.content)
                return True, "OK_XML"
            except Exception:
                return False, "RSS/XML değil"

        if kind in ("listing_html", "official_html"):
            if len(r.text) > 300:
                return True, "OK_HTML"
            return False, "HTML çok kısa"

        return True, "OK"

    except Exception as exc:
        return False, str(exc)[:180]


def clean_obj(obj, removed):
    if isinstance(obj, list):
        out = []
        for x in obj:
            if isinstance(x, str) and x in removed:
                continue
            if isinstance(x, dict) and x.get("name") in removed:
                continue
            out.append(clean_obj(x, removed))
        return out

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k in removed:
                continue
            if isinstance(v, str) and v in removed:
                continue
            if isinstance(v, dict) and v.get("name") in removed:
                continue
            out[k] = clean_obj(v, removed)
        return out

    return obj


def main():
    feeds = load_json(FEEDS_PATH, [])
    removed = set()
    added = []
    skipped = []

    for src in SOURCE_PLAN:
        removed.update(src.get("replace", []))

    # 1) Eski kaynakları feeds.json'dan çıkar
    feeds = [f for f in feeds if f.get("name") not in removed]

    # 2) Yeni kaynakları test et ve ekle/güncelle
    for src in SOURCE_PLAN:
        ok, reason = check_source(src)

        if not ok:
            skipped.append((src["name"], reason))
            continue

        feed = {
            "name": src["name"],
            "url": src["url"],
            "kind": src.get("kind", "rss"),
            "enabled": True,
            "priority": src.get("priority", 5),
            "source_class": src.get("source_class"),
            "source_family": src.get("source_family"),
            "notes": src.get("notes", "Source manager tarafından eklendi/güncellendi.")
        }

        feed = {k: v for k, v in feed.items() if v is not None}

        found = False
        for f in feeds:
            if f.get("name") == src["name"]:
                f.update(feed)
                found = True
                break

        if not found:
            feeds.append(feed)

        added.append(src["name"])

    save_json(FEEDS_PATH, feeds)

    # 3) Profillerden eski kaynakları sil, yenileri doğru profillere ekle
    for profile_path in PROFILES_DIR.glob("*.json"):
        data = load_json(profile_path, {})
        if not isinstance(data, dict):
            continue

        profile_name = profile_path.stem

        add_for_profile = [
            src["name"]
            for src in SOURCE_PLAN
            if src["name"] in added and profile_name in src.get("profiles", [])
        ]

        changed = False

        for key in ("sources", "enabled_feeds"):
            arr = data.setdefault(key, [])
            before = list(arr)

            arr = [x for x in arr if x not in removed]

            for name in add_for_profile:
                if name not in arr:
                    arr.append(name)

            data[key] = arr
            changed = changed or before != arr

        if changed:
            save_json(profile_path, data)

    # 4) Rules / profiles / storage JSON kalıntı temizliği
    targets = (
        list(Path("rules").glob("*.json")) +
        list(Path("profiles").glob("*.json")) +
        list(STORAGE_DIR.glob("*.json"))
    )

    for path in targets:
        data = load_json(path, None)
        if data is None:
            continue
        cleaned = clean_obj(data, removed)
        if cleaned != data:
            save_json(path, cleaned)

    print("\n✅ EKLENEN/GÜNCELLENEN:")
    for x in added:
        print("-", x)

    print("\n🗑 KALDIRILAN:")
    for x in sorted(removed):
        print("-", x)

    print("\n⚠️ EKLENMEYEN / TESTTEN GEÇMEYEN:")
    for name, reason in skipped:
        print(f"- {name}: {reason}")

    print("\nOK - Source manager tamamlandı.")


if __name__ == "__main__":
    main()
