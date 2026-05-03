import json
import re
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RAW_DIR = ROOT / "storage/macro_archive/raw"
ITEM_DIR = ROOT / "storage/macro_archive/items"
INDEX_PATH = ROOT / "storage/macro_archive/index.json"

IMPORTANT_PATTERNS = [
    ("fomc_statement", ["statement", "fomc", "federal funds rate"]),
    ("fomc_minutes", ["minutes", "fomc"]),
    ("central_bank_speech", ["speech", "remarks", "testimony"]),
    ("rate_decision", ["monetary policy", "rate decision", "bank rate", "policy rate", "faiz", "ppk"]),
    ("inflation_report", ["inflation report", "enflasyon raporu"]),
    ("macro_data", ["gdp", "personal income", "pce", "consumer price index", "employment situation"]),
    ("energy_report", ["oil", "petroleum", "short-term energy outlook", "opec", "production"]),
]

def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text

def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:20]

def classify(text: str) -> str:
    low = text.lower()
    for label, keys in IMPORTANT_PATTERNS:
        if any(k in low for k in keys):
            return label
    return "macro_raw"

def source_from_file(name: str) -> str:
    if name.startswith("fed_"):
        return "Federal Reserve"
    if name.startswith("ecb_"):
        return "ECB"
    if name.startswith("tcmb_"):
        return "TCMB"
    if name.startswith("boe_"):
        return "Bank of England"
    if name.startswith("boj_"):
        return "Bank of Japan"
    if name.startswith("pboc_"):
        return "PBOC"
    if name.startswith("bea_"):
        return "BEA"
    if name.startswith("bls_"):
        return "BLS"
    if name.startswith("opec_"):
        return "OPEC"
    if name.startswith("eia_"):
        return "EIA"
    if name.startswith("iea_"):
        return "IEA"
    if name.startswith("imf_"):
        return "IMF"
    if name.startswith("oecd_"):
        return "OECD"
    if name.startswith("worldbank_"):
        return "World Bank"
    return name

def make_item(raw_file: Path):
    text = clean_text(raw_file.read_text(encoding="utf-8", errors="ignore"))
    if len(text) < 200:
        return None

    source_id = raw_file.stem
    source_name = source_from_file(source_id)
    item_type = classify(text)
    h = digest(source_id + text[:5000])

    title = text[:160]
    title = re.sub(r"\s+", " ", title).strip()

    return {
        "id": f"{source_id}_{h}",
        "source_id": source_id,
        "source_name": source_name,
        "type": item_type,
        "title": title,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "text_hash": h,
        "text": text[:12000],
        "summary": "",
        "tone": "",
        "market_effect": {},
    }

def main():
    ITEM_DIR.mkdir(parents=True, exist_ok=True)

    existing = {}
    if INDEX_PATH.exists():
        try:
            for item in json.loads(INDEX_PATH.read_text(encoding="utf-8")).get("items", []):
                existing[item["id"]] = item
        except Exception:
            existing = {}

    added = 0
    updated_items = list(existing.values())

    for raw_file in sorted(RAW_DIR.glob("*.txt")):
        item = make_item(raw_file)
        if not item:
            continue
        if item["id"] in existing:
            continue

        item_path = ITEM_DIR / f"{item['id']}.json"
        item_path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        index_item = {k: item[k] for k in ["id", "source_id", "source_name", "type", "title", "archived_at", "text_hash"]}
        updated_items.append(index_item)
        added += 1

    INDEX_PATH.write_text(json.dumps({"items": updated_items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"MACRO ARCHIVE BACKFILL OK | added={added} total={len(updated_items)}")

if __name__ == "__main__":
    main()
