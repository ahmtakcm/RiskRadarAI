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
        send_telegram("Ã¢â€Â¹Ã¯Â¸Â Feed log kontrolÃƒÂ¼: app.log henÃƒÂ¼z yok.")
        print("NO_LOG")
        return

    lines = LOG_PATH.read_text(errors="ignore").splitlines()
    errors = [x for x in lines[-300:] if "Haber feed hatasÃ„Â±" in x]

    if not errors:
        send_telegram("Ã¢Å“â€¦ Feed log kontrolÃƒÂ¼ temiz. GÃƒÂ¼ncel logda feed hatasÃ„Â± yok.")
        print("OK_NO_FEED_ERROR")
        return

    msg = [
        "Ã¢Å¡Â Ã¯Â¸Â Feed log kontrolÃƒÂ¼: hata bulundu.",
        f"Son 300 satÃ„Â±rda hata sayÃ„Â±sÃ„Â±: {len(errors)}",
        "",
        "DetaylÃ„Â± saÃ„Å¸lÃ„Â±k kontrolÃƒÂ¼ baÃ…Å¸latÃ„Â±ldÃ„Â±..."
    ]
    for e in errors[-5:]:
        msg.append("Ã¢â‚¬Â¢ " + e[-220:])

    send_telegram("\n".join(msg))

    subprocess.Popen(
        [sys.executable, str(HEALTH_SCRIPT)],
        cwd=str(Path(__file__).resolve().parents[1])
    )
    print("ERROR_FOUND_HEALTH_STARTED")


if __name__ == "__main__":
    main()
