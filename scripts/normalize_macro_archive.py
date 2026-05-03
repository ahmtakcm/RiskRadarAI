import json
from pathlib import Path

INDEX_PATH = Path("storage/macro_archive/index.json")

HIGH_SIGNAL_TYPES = {
    "fomc_statement",
    "fomc_minutes",
    "ecb_rate_decision",
    "boe_rate_decision",
    "boj_rate_decision",
    "tcmb_rate_decision",
    "pboc_monetary_policy",
    "macro_data"
}

LOW_SIGNAL_TYPES = {
    "boj_speech",
    "boe_speech",
    "ecb_speech",
    "ecb_interview",
    "boe_document",
    "tcmb_document"
}

def normalize():
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    items = data.get("items", [])

    high = 0
    low = 0

    for x in items:
        t = x.get("type")

        # Default
        x["signal_strength"] = "medium"
        x["is_signal"] = False

        if t in HIGH_SIGNAL_TYPES:
            x["signal_strength"] = "high"
            x["is_signal"] = True
            high += 1

        elif t in LOW_SIGNAL_TYPES:
            x["signal_strength"] = "low"
            x["is_signal"] = False
            low += 1

        # global macro özel filtre
        elif t == "global_macro":
            title = (x.get("title") or "").lower()

            if any(k in title for k in [
                "inflation", "gdp", "forecast", "outlook",
                "oil", "energy", "production", "demand"
            ]):
                x["signal_strength"] = "high"
                x["is_signal"] = True
                high += 1
            else:
                x["signal_strength"] = "medium"

    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("NORMALIZATION OK")
    print("HIGH SIGNAL:", high)
    print("LOW SIGNAL:", low)
    print("TOTAL:", len(items))

if __name__ == "__main__":
    normalize()
