import json
from pathlib import Path

CACHE_PATH = Path("storage/calendar_cache.json")

def scan_calendar_events():
    if not CACHE_PATH.exists():
        return []

    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return [e for e in data.get("events", []) if e.get("status", "active") == "active"]
    except Exception:
        return []
