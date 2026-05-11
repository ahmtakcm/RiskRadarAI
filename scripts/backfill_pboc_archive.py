import json
import re
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clients.http_client import http_client
from parsers.generic_html_parser import strip_html

BASE_URL = "https://www.pbc.gov.cn"

SOURCES = [
    ("pboc_news", "https://www.pbc.gov.cn/en/3688006/index.html"),
]

ITEM_DIR = ROOT / "storage/macro_archive/items"
INDEX_PATH = ROOT / "storage/macro_archive/index.json"

def _hash(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:20]

def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()

def _load_index():
    if not INDEX_PATH.exists():
        return {"items": []}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))

def _save_index(idx):
    INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _classify(label, url, text):
    low = f"{label} {url} {text[:1000]}".lower()

    if "monetary policy" in low or "policy rate" in low or "interest rate" in low:
        return "pboc_monetary_policy"
    if "press release" in low or "news" in low:
        return "pboc_news"
    if "speech" in low or "remarks" in low:
        return "pboc_speech"
    if "financial stability" in low:
        return "pboc_financial_stability"

    return "pboc_document"

def _extract_links(html):
    links = []

    for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
        href = m.group(1)
        label = _clean(strip_html(m.group(2)))

        if not href or "javascript:" in href:
            continue

        low = f"{href} {label}".lower()

        if any(k in low for k in [
            "monetary",
            "policy",
            "press",
            "news",
            "speech",
            "financial",
            "rate",
            "yuan",
            "rmb"
        ]):
            links.append((label or href.split("/")[-1], urljoin(BASE_URL, href)))

    seen = set()
    out = []
    for label, u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append((label, u))

    return out

def main(limit=120):
    ITEM_DIR.mkdir(parents=True, exist_ok=True)

    idx = _load_index()
    existing = {x["id"] for x in idx.get("items", [])}

    checked = 0
    added = 0

    for source_id, url in SOURCES:
        try:
            html = http_client.get_text(url)
            links = _extract_links(html)
            links.insert(0, (source_id, url))
        except Exception as e:
            print("SOURCE ERR:", source_id, e)
            continue

        for label, link in links[:limit]:
            checked += 1

            try:
                doc_html = http_client.get_text(link)
                text = _clean(strip_html(doc_html))

                if len(text) < 250:
                    continue

                t = _classify(label, link, text)
                h = _hash(link + text[:5000])
                item_id = f"{source_id}_{t}_{h}"

                if item_id in existing:
                    continue

                item = {
                    "id": item_id,
                    "source_id": source_id,
                    "source_name": "PBOC",
                    "type": t,
                    "title": label,
                    "url": link,
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                    "text_hash": h,
                    "text": text[:20000],
                    "summary": "",
                    "tone": "",
                    "market_effect": {}
                }

                (ITEM_DIR / f"{item_id}.json").write_text(
                    json.dumps(item, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8"
                )

                idx["items"].append({
                    "id": item_id,
                    "source_id": source_id,
                    "source_name": "PBOC",
                    "type": t,
                    "title": label,
                    "url": link,
                    "archived_at": item["archived_at"],
                    "text_hash": h
                })

                existing.add(item_id)
                added += 1

            except Exception as e:
                print("ERR:", label, link, str(e)[:120])

    _save_index(idx)
    print(f"PBOC DEEP ARCHIVE OK | checked={checked} added={added} total_index={len(idx.get('items', []))}")

if __name__ == "__main__":
    main()

