import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fetchers.feed_fetcher import fetch_feed_items

FEEDS_PATH = Path("rules/feeds.json")

def main():
    if not FEEDS_PATH.exists():
        print("feeds.json bulunamadı")
        sys.exit(1)

    data = json.loads(FEEDS_PATH.read_text(encoding="utf-8"))

    query = " ".join(sys.argv[1:]).strip().lower()
    targets = []

    if query:
        for feed in data:
            name = str(feed.get("name", "")).lower()
            url = str(feed.get("url", "")).lower()
            if query in name or query in url:
                targets.append(feed)
    else:
        targets = data

    if not targets:
        print("Eşleşen feed bulunamadı")
        sys.exit(1)

    print(f"TEST EDILECEK FEED SAYISI: {len(targets)}")

    for idx, feed in enumerate(targets, start=1):
        print("\n" + "=" * 80)
        print(f"[{idx}] FEED: {feed.get('name')}")
        print("URL:", feed.get("url"))
        print("kind:", feed.get("kind"))
        print("source_class:", feed.get("source_class"))
        print("source_country:", feed.get("source_country"))
        print("source_family:", feed.get("source_family"))
        print("stale_minutes:", feed.get("stale_minutes"))
        print("verification_group:", feed.get("verification_group"))
        print("-" * 80)

        try:
            items = fetch_feed_items(feed)
            print("item_count:", len(items))

            for i, item in enumerate(items[:3], start=1):
                slim = {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "pub_date": item.get("pub_date"),
                    "source_name": item.get("source_name"),
                    "source_kind": item.get("source_kind"),
                    "source_class": item.get("source_class"),
                    "source_country": item.get("source_country"),
                    "verification_group": item.get("verification_group"),
                }
                print(f"item_{i}:", json.dumps(slim, ensure_ascii=False))
        except Exception as exc:
            print("FETCH_ERROR:", repr(exc))

if __name__ == "__main__":
    main()
