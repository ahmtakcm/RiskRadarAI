import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import subprocess

from clients.telegram_client import telegram_client

LOG_PATH = Path("storage/app.log")
HEALTH_SCRIPT = Path("scripts/feed_health_check.py")


def send_telegram(text: str):
    telegram_client.send_message(text)


def main():
    if not LOG_PATH.exists():
        send_telegram("â„¹ï¸ Feed log kontrolÃ¼: app.log henÃ¼z yok.")
        print("NO_LOG")
        return

    lines = LOG_PATH.read_text(errors="ignore").splitlines()
    errors = [x for x in lines[-300:] if "Haber feed hatasÄ±" in x]

    if not errors:
        send_telegram("âœ… Feed log kontrolÃ¼ temiz. GÃ¼ncel logda feed hatasÄ± yok.")
        print("OK_NO_FEED_ERROR")
        return

    msg = [
        "âš ï¸ Feed log kontrolÃ¼: hata bulundu.",
        f"Son 300 satÄ±rda hata sayÄ±sÄ±: {len(errors)}",
        "",
        "DetaylÄ± saÄŸlÄ±k kontrolÃ¼ baÅŸlatÄ±ldÄ±..."
    ]
    for e in errors[-5:]:
        msg.append("â€¢ " + e[-220:])

    send_telegram("\n".join(msg))

    subprocess.Popen(
        [sys.executable, str(HEALTH_SCRIPT)],
        cwd=str(Path(__file__).resolve().parents[1])
    )
    print("ERROR_FOUND_HEALTH_STARTED")


if __name__ == "__main__":
    main()
