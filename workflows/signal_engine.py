import json
import time
from pathlib import Path
def analyze_event(event):
    t = (event.get("type") or "").lower()
    title = (event.get("title") or "").lower()
    text = (event.get("text") or "").lower()
    body = f"{title} {text}"

    result = {
        "bias": "neutral",
        "impact": {},
        "confidence": 0.5
    }

    hawkish_words = [
        "raise", "raises", "raised", "hike", "hikes", "hiked",
        "higher rates", "persistent inflation", "inflation pressures",
        "tightening", "restrictive", "above target"
    ]

    dovish_words = [
        "cut", "cuts", "lower rates", "rate reduction",
        "easing", "accommodative", "slowdown", "weak growth",
        "disinflation", "below target"
    ]

    # Faiz / merkez bankası sinyali
    if any(k in t for k in ["rate", "fomc", "decision", "monetary", "policy"]):
        if any(w in body for w in hawkish_words):
            result["bias"] = "hawkish"
            result["impact"] = {
                "usd": "bullish",
                "gold": "bearish",
                "silver": "bearish",
                "btc": "bearish",
                "stocks": "bearish"
            }
            result["confidence"] = 0.85

        elif any(w in body for w in dovish_words):
            result["bias"] = "dovish"
            result["impact"] = {
                "usd": "bearish",
                "gold": "bullish",
                "silver": "bullish",
                "btc": "bullish",
                "stocks": "bullish"
            }
            result["confidence"] = 0.85

    # Enflasyon / CPI
    elif any(k in body for k in ["inflation", "cpi", "consumer price index"]):
        if any(k in body for k in ["higher than expected", "above expectations", "accelerated", "persistent"]):
            result["bias"] = "inflation_hot"
            result["impact"] = {
                "usd": "bullish",
                "gold": "bearish",
                "silver": "bearish",
                "btc": "bearish"
            }
            result["confidence"] = 0.8
        elif any(k in body for k in ["lower than expected", "below expectations", "cooled", "slowed"]):
            result["bias"] = "inflation_cool"
            result["impact"] = {
                "usd": "bearish",
                "gold": "bullish",
                "silver": "bullish",
                "btc": "bullish"
            }
            result["confidence"] = 0.8

    # Enerji / petrol
    elif any(k in body for k in ["oil", "petroleum", "opec", "production", "supply"]):
        if any(k in body for k in ["cut production", "supply disruption", "shortage", "hormuz", "outage"]):
            result["bias"] = "energy_supply_shock"
            result["impact"] = {
                "oil": "bullish",
                "inflation": "bullish",
                "gold": "bullish",
                "stocks": "bearish"
            }
            result["confidence"] = 0.75

    return result


def export_macro_signal(signal: dict, event: dict):
    try:
        payload = {
            "timestamp": int(time.time()),
            "event": event.get("title"),
            "source": event.get("source_name"),
            "bias": signal.get("bias"),
            "impact": signal.get("impact"),
            "confidence": signal.get("confidence"),
        }

        out = Path("storage/macro_trade_signals.json")
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    except Exception:
        pass
