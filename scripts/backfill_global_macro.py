import json, re, hashlib, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clients.http_client import http_client
from parsers.generic_html_parser import strip_html

SOURCES = [
    ("imf_news", "IMF", "https://www.imf.org/en/News"),
    ("worldbank_news", "World Bank", "https://www.worldbank.org/en/news"),
    ("oecd_news", "OECD", "https://www.oecd.org/newsroom/"),
    ("iea_news", "IEA", "https://www.iea.org/news"),
    ("opec_press", "OPEC", "https://www.opec.org/opec_web/en/press_room/"),
    ("eia_news", "EIA", "https://www.eia.gov/pressroom/releases.php"),
]

ITEM_DIR = ROOT / "storage/macro_archive/items"
INDEX_PATH = ROOT / "storage/macro_archive/index.json"

KEYWORDS = [
    "inflation","gdp","growth","forecast","outlook",
    "oil","production","demand","supply","energy","recession"
]

def _hash(t):
    return hashlib.sha256(t.encode()).hexdigest()[:16]

def main():
    ITEM_DIR.mkdir(parents=True, exist_ok=True)
    idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    existing = {x["id"] for x in idx["items"]}

    added = 0

    for sid, sname, url in SOURCES:
        try:
            html = http_client.get_text(url)
        except Exception as e:
            print("ERR SOURCE:", sname, e)
            continue

        for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, re.I|re.S):
            href = m.group(1)
            label = re.sub(r"\s+"," ", strip_html(m.group(2)))

            if not href or "javascript" in href:
                continue

            link = urljoin(url, href)
            low = (label + link).lower()

            if not any(k in low for k in KEYWORDS):
                continue

            try:
                doc = http_client.get_text(link)
                text = re.sub(r"\s+"," ", strip_html(doc))

                if len(text) < 300:
                    continue

                h = _hash(link+text[:1000])
                iid = f"{sid}_{h}"

                if iid in existing:
                    continue

                item = {
                    "id": iid,
                    "source_name": sname,
                    "title": label,
                    "url": link,
                    "type": "global_macro",
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                    "text": text[:15000]
                }

                (ITEM_DIR / f"{iid}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2))
                idx["items"].append(item)
                existing.add(iid)
                added += 1

            except Exception as e:
                continue

    INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2))
    print("GLOBAL MACRO BACKFILL OK | added =", added)

if __name__ == "__main__":
    main()
