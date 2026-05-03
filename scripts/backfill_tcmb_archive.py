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

BASE_URL = "https://www.tcmb.gov.tr"

SOURCES = [
    ("tcmb_ppk", "https://www.tcmb.gov.tr/wps/wcm/connect/tr/tcmb%2Btr/main%2Bmenu/temel%2Bfaaliyetler/para%2Bpolitikasi/ppk"),
    ("tcmb_enflasyon", "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Yayinlar/Raporlar/Enflasyon+Raporu"),
    ("tcmb_calendar", "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Takvim"),
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

def _classify(label: str, url: str, text: str):
    low = f"{label} {url} {text[:800]}".lower()
    if "toplantı özeti" in low or "ppk özeti" in low:
        return "tcmb_ppk_minutes"
    if "para politikası kurulu" in low or "faiz" in low or "politika faizi" in low:
        return "tcmb_rate_decision"
    if "enflasyon raporu" in low:
        return "tcmb_inflation_report"
    if "finansal istikrar" in low:
        return "tcmb_financial_stability"
    return "tcmb_document"

def _extract_links(html: str):
    links = []

    for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.I | re.S):
        href = m.group(1)
        label = _clean(strip_html(m.group(2)))

        low = f"{href} {label}".lower()

        if not href:
            continue

        if any(k in low for k in [
            "para politikası kurulu",
            "para+politikasi",
            "ppk",
            "faiz",
            "enflasyon",
            "finansal",
            "rapor",
            "basin",
            "duyuru"
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

def main(limit_per_source=80):
    ITEM_DIR.mkdir(parents=True, exist_ok=True)

    index = _load_index()
    existing = {x.get("id") for x in index.get("items", [])}

    checked = 0
    added = 0

    for source_id, page_url in SOURCES:
        try:
            html = http_client.get_text(page_url)
            links = _extract_links(html)

            # Kaynak sayfanın kendisini de arşivle
            links.insert(0, (source_id, page_url))

        except Exception as exc:
            print("SOURCE ERR:", source_id, exc)
            continue

        for label, url in links[:limit_per_source]:
            checked += 1

            try:
                doc_html = http_client.get_text(url)
                text = _clean(strip_html(doc_html))

                if len(text) < 250:
                    continue

                item_type = _classify(label, url, text)
                h = _hash(url + text[:5000])
                item_id = f"{source_id}_{item_type}_{h}"

                if item_id in existing:
                    continue

                item = {
                    "id": item_id,
                    "source_id": source_id,
                    "source_name": "TCMB",
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
                    "source_name": "TCMB",
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
    print(f"TCMB DEEP ARCHIVE OK | checked={checked} added={added} total_index={len(index.get('items', []))}")

if __name__ == "__main__":
    main()
