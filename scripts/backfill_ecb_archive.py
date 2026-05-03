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

BASE_URL = "https://www.ecb.europa.eu"
SOURCES = [
    ("ecb_policy", "https://www.ecb.europa.eu/press/pr/date/html/index.en.html"),
    ("ecb_speeches", "https://www.ecb.europa.eu/press/key/html/index.en.html"),
]

ITEM_DIR = ROOT / "storage/macro_archive/items"
INDEX_PATH = ROOT / "storage/macro_archive/index.json"

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:20]

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def _load_index():
    if not INDEX_PATH.exists():
        return {"items": []}
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}

def _save_index(index):
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _extract_links(html: str):
    links = []
    for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{3,180})</a>', html, flags=re.I):
        href = m.group(1)
        label = _clean(strip_html(m.group(2)))
        low = f"{href} {label}".lower()

        if not (href.endswith(".html") or href.endswith(".en.html")):
            continue

        if any(k in low for k in [
            "monetary policy decision",
            "monetary policy decisions",
            "press conference",
            "accounts",
            "keynote speech",
            "speech",
            "interview",
            "blog"
        ]):
            links.append((label or href.split("/")[-1], urljoin(BASE_URL, href)))

    seen = set()
    out = []
    for label, url in links:
        if url in seen:
            continue
        seen.add(url)
        out.append((label, url))
    return out

def _classify(label: str, url: str):
    low = f"{label} {url}".lower()
    if "account" in low:
        return "ecb_accounts"
    if "speech" in low or "keynote" in low:
        return "ecb_speech"
    if "interview" in low:
        return "ecb_interview"
    if "monetary policy decision" in low or "monetary policy decisions" in low:
        return "ecb_rate_decision"
    if "press conference" in low:
        return "ecb_press_conference"
    return "ecb_document"

def main(limit_per_source=80):
    ITEM_DIR.mkdir(parents=True, exist_ok=True)
    index = _load_index()
    existing = {x.get("id") for x in index.get("items", [])}

    added = 0
    checked = 0

    for source_id, page_url in SOURCES:
        try:
            html = http_client.get_text(page_url)
            links = _extract_links(html)
        except Exception as exc:
            print("SOURCE ERR:", source_id, exc)
            continue

        for label, url in links[:limit_per_source]:
            checked += 1
            try:
                doc_html = http_client.get_text(url)
                text = _clean(strip_html(doc_html))
                if len(text) < 300:
                    continue

                item_type = _classify(label, url)
                h = _hash(url + text[:5000])
                item_id = f"{source_id}_{item_type}_{h}"

                if item_id in existing:
                    continue

                item = {
                    "id": item_id,
                    "source_id": source_id,
                    "source_name": "ECB",
                    "type": item_type,
                    "title": label,
                    "url": url,
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

                index["items"].append({
                    "id": item_id,
                    "source_id": source_id,
                    "source_name": "ECB",
                    "type": item_type,
                    "title": label,
                    "url": url,
                    "archived_at": item["archived_at"],
                    "text_hash": h
                })

                existing.add(item_id)
                added += 1

            except Exception as exc:
                print("ERR:", label, url, str(exc)[:160])

    _save_index(index)
    print(f"ECB DEEP ARCHIVE OK | checked={checked} added={added} total_index={len(index.get('items', []))}")

if __name__ == "__main__":
    main()
