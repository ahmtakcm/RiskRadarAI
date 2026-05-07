import json
import threading
import time
import requests

from commands.source_commands import handle_source_command
from commands.audit_commands import handle_audit_command
from commands.manual_scan_commands import handle_manual_scan_command
from commands.profile_commands import (
    handle_profile_command,
    handle_watch_command,
    handle_feed_command,
)
from config.paths import USER_INPUTS_DIR
from config.settings import settings
from core.logger import get_logger
from clients.telegram_client import telegram_client

logger = get_logger("telegram_command_worker")

STATE_PATH = USER_INPUTS_DIR / "telegram_command_state.json"
_LOCK = threading.Lock()
_STARTED = False


def _load_offset():
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8")).get("offset")
    except Exception:
        return None


def _save_offset(offset: int):
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(
        json.dumps({"offset": offset}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _send_to_chat(chat_id, text: str):
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=20)
    if r.status_code != 200:
        logger.warning("Telegram komut cevabı gönderilemedi: %s | %s", r.status_code, r.text[:300])


def poll_once() -> bool:
    if not _LOCK.acquire(blocking=False):
        return False

    handled = False

    try:
        offset = _load_offset()
        data = telegram_client.get_updates(offset=offset)

        if not data.get("ok"):
            logger.warning("Telegram getUpdates ok=false: %s", str(data)[:300])
            return False

        max_update_id = None

        for upd in data.get("result", []):
            uid = upd.get("update_id")
            if uid is not None:
                max_update_id = uid if max_update_id is None else max(max_update_id, uid)

            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            text = msg.get("text") or ""

            if str(chat_id) != str(settings.chat_id):
                continue

            replies = []
            for line in str(text).splitlines():
                line = line.strip()
                if not line:
                    continue

                reply = (
                    handle_profile_command(line)
                    or handle_watch_command(line)
                    or handle_feed_command(line)
                    or handle_source_command(line)
                    or handle_audit_command(line)
                    or handle_manual_scan_command(line)
                )

                if reply:
                    replies.append(reply)

            if replies:
                _send_to_chat(chat_id, "\n\n".join(replies))
                handled = True

        if max_update_id is not None:
            _save_offset(max_update_id + 1)

        return handled

    except Exception as exc:
        logger.warning("Telegram komut worker hatası: %s", exc)
        return False

    finally:
        _LOCK.release()


def _loop():
    logger.info("Telegram komut worker başladı")
    while True:
        poll_once()
        time.sleep(1.5)


def start_telegram_command_worker():
    global _STARTED
    if _STARTED:
        return

    _STARTED = True
    t = threading.Thread(target=_loop, name="telegram-command-worker", daemon=True)
    t.start()
