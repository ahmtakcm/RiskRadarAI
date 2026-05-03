import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

STATE_PATH = Path("storage/macro_high_alert_state.json")
DEFAULT_ASSETS = ["BTCUSDT", "XAUUSDT", "XAGUSDT"]


def activate_high_alert(event: dict, mode: str = "pre_event", hours: int = 3):
    try:
        now = datetime.now(timezone.utc)
        until = now + timedelta(hours=hours)
        signal = event.get("signal") or {}

        payload = {
            "active": True,
            "created_at": now.isoformat(),
            "until": until.isoformat(),
            "mode": mode,
            "reason": event.get("title") or event.get("id") or "macro_event",
            "source": event.get("source_name") or "",
            "assets": DEFAULT_ASSETS,
            "bias": signal.get("bias") or "unknown",
            "impact": signal.get("impact") or {},
            "confidence": signal.get("confidence") or 0,
        }

        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    except Exception:
        return None
