from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from clients.telegram_client import mask_token_text, telegram_client


def _send_telegram(text: str) -> None:
    telegram_client.send_message(text)


def main() -> int:
    bot_name = sys.argv[1] if len(sys.argv) > 1 else "RiskRadarAI"
    code = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pc = os.getenv("COMPUTERNAME", "unknown-pc")
    user = os.getenv("USERNAME", "unknown-user")

    if str(code) == "0":
        title = "ℹ️ Bot süreci kapandı"
    else:
        title = "⚠️ Bot süreci durdu / kapandı"

    text = (
        f"{title}\n\n"
        f"Bot: {bot_name}\n"
        f"Kod: {code}\n"
        f"Zaman: {now}\n"
        f"PC/Kullanıcı: {pc}/{user}\n"
        f"Klasör: {BASE_DIR}"
    )
    try:
        _send_telegram(text)
    except Exception as exc:
        print(f"notify_exit failed: {mask_token_text(exc)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
