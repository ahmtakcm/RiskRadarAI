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

BASE_URL = "https://www.boj.or.jp"

SOURCES = [
    ("boj_announcements", "https://www.boj.or.jp/en/announcements/index.htm"),
    ("boj_outlook", "https://www.boj.or.jp/en/mopo/outlook/index.htm"),
    ("boj_speeches", "https://www.boj.or.jp/en/about/press/koen_2026/index.htm"),
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
    low = f"{label} {url} {text[:800]}".lower()

    if "monetary policy meeting" in low:
        return "boj_rate_decision"
    if "outlook report" in low:
        return "boj_outlook"
    if "speech" in low or "remarks" in low:
        return "boj_speech"
    if "statement" in low:
        return "boj_statement"

    return "boj_document"

def _extract_links(html):
    links = []

    for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
        href = m.group(1)
        label = _clean(strip_html(m.group(2)))

        if not href or "javascript:" in href:
            continue

        if not (href.endswith(".htm") or href.endswith(".html")):
            continue

        low = f"{href} {label}".lower()

        if any(k in low for k in [
            "policy",
            "statement",
            "outlook",
            "speech",
            "meeting"
        ]):
            links.append((label or href.split("/")[-1], urljoin(BASE_URL, href)))

    # dedupe
    seen = set()
    out = []
    for l, u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append((l, u))

    return out

def main(limit=80):
    ITEM_DIR.mkdir(parents=True, exist_ok=True)

    idx = _load_index()
    existing = {x["id"] for x in idx.get("items", [])}

    added = 0
    checked = 0

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

                if len(text) < 300:
                    continue

                t = _classify(label, link, text)
                h = _hash(link + text[:5000])
                item_id = f"{source_id}_{t}_{h}"

                if item_id in existing:
                    continue

                item = {
                    "id": item_id,
                    "source_id": source_id,
                    "source_name": "Bank of Japan",
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
                    "source_name": "Bank of Japan",
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
    print(f"BOJ DEEP ARCHIVE OK | checked={checked} added={added} total_index={len(idx.get('items', []))}")

if __name__ == "__main__":
    main()
