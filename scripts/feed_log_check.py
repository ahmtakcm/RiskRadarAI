import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import subprocess
from datetime import datetime
from config.settings import settings
import requests

LOG_PATH = Path("storage/app.log")
HEALTH_SCRIPT = Path("scripts/feed_health_check.py")


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    requests.post(url, data={"chat_id": settings.chat_id, "text": text}, timeout=20)


def main():
    if not LOG_PATH.exists():
        send_telegram("ℹ️ Feed log kontrolü: app.log henüz yok.")
        print("NO_LOG")
        return

    lines = LOG_PATH.read_text(errors="ignore").splitlines()
    errors = [x for x in lines[-300:] if "Haber feed hatası" in x]

    if not errors:
        send_telegram("✅ Feed log kontrolü temiz. Güncel logda feed hatası yok.")
        print("OK_NO_FEED_ERROR")
        return

    msg = [
        "⚠️ Feed log kontrolü: hata bulundu.",
        f"Son 300 satırda hata sayısı: {len(errors)}",
        "",
        "Detaylı sağlık kontrolü başlatıldı..."
    ]
    for e in errors[-5:]:
        msg.append("• " + e[-220:])

    send_telegram("\n".join(msg))

    subprocess.Popen(
        [sys.executable, str(HEALTH_SCRIPT)],
        cwd=str(Path(__file__).resolve().parents[1])
    )
    print("ERROR_FOUND_HEALTH_STARTED")


if __name__ == "__main__":
    main()
