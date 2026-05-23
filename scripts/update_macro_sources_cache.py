import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from clients.http_client import http_client
from parsers.generic_html_parser import strip_html

SOURCES_PATH = Path("rules/calendar_sources.json")
CACHE_DIR = Path("storage/macro_sources_cache")
RAW_DIR = Path("storage/macro_archive/raw")
REPORT_PATH = Path("storage/macro_sources_report.json")

KEYWORDS = [
    "interest rate", "monetary policy", "policy rate", "rate decision",
    "inflation", "cpi", "employment", "nonfarm", "gdp", "retail sales",
    "pce", "pmi", "unemployment", "housing", "building permits",
    "industrial production", "speech", "remarks", "minutes", "statement",
    "press conference", "chair", "governor", "nomination", "sanctions",
    "systemic risk", "financial stability", "opec", "production", "oil",
    "energy", "enflasyon", "faiz", "ppk"
]

def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())[:80]

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def _interesting_lines(text: str, limit: int = 20):
    lines = []
    low_keywords = [k.lower() for k in KEYWORDS]
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) < 25:
            continue
        low = line.lower()
        if any(k in low for k in low_keywords):
            lines.append(line[:500])
        if len(lines) >= limit:
            break
    return lines

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8")).get("sources", [])
    now = datetime.now(timezone.utc).isoformat()

    report = {
        "updated_at": now,
        "total": 0,
        "ok": 0,
        "failed": 0,
        "changed": 0,
        "sources": []
    }

    for src in sources:
        if not src.get("enabled", True):
            continue

        report["total"] += 1
        sid = _safe_id(src.get("id") or src.get("source_name") or "source")
        cache_path = CACHE_DIR / f"{sid}.json"
        raw_path = RAW_DIR / f"{sid}.txt"

        entry = {
            "id": src.get("id"),
            "source_name": src.get("source_name"),
            "category": src.get("category"),
            "url": src.get("url"),
            "checked_at": now,
            "ok": False,
            "changed": False,
            "error": "",
            "hash": "",
            "interesting_lines": []
        }

        try:
            html = http_client.get_text(src["url"])
            text = strip_html(html or "")
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            digest = _hash(text[:200000])

            old_hash = ""
            if cache_path.exists():
                try:
                    old_hash = json.loads(cache_path.read_text(encoding="utf-8")).get("hash", "")
                except Exception:
                    old_hash = ""

            entry["ok"] = bool(text)
            entry["hash"] = digest
            entry["changed"] = bool(old_hash and old_hash != digest)
            entry["interesting_lines"] = _interesting_lines(text)

            raw_path.write_text(text[:50000], encoding="utf-8")
            cache_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            report["ok"] += 1
            if entry["changed"]:
                report["changed"] += 1

        except Exception as exc:
            entry["error"] = str(exc)[:500]
            report["failed"] += 1
            cache_path.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        report["sources"].append(entry)

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MACRO SOURCE UPDATE OK | total={report['total']} ok={report['ok']} failed={report['failed']} changed={report['changed']}")

if __name__ == "__main__":
    main()
