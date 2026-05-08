import argparse
import json
import os
import threading
import time
import requests

from commands.profile_commands import handle_profile_command
from commands.menu import normalize_command_text
from telegram_ui.keyboard import build_reply_keyboard
from config.paths import USER_INPUTS_DIR
from config.settings import settings
from core.logger import get_logger
from clients.telegram_client import telegram_client

logger = get_logger("telegram_command_worker")

STATE_PATH = USER_INPUTS_DIR / "telegram_command_state.json"
_LOCK = threading.Lock()
_STARTED = False


def _csv_set(value: str | None) -> set[str]:
    return {x.strip() for x in str(value or "").split(",") if x.strip()}


def _admin_user_ids() -> set[str]:
    return _csv_set(os.getenv("TELEGRAM_ADMIN_USER_IDS"))


def _allowed_chat_ids() -> set[str]:
    values = _csv_set(os.getenv("TELEGRAM_ALLOWED_CHAT_IDS"))
    if getattr(settings, "chat_id", None):
        values.add(str(settings.chat_id))
    return values


def _is_private_chat(chat: dict) -> bool:
    return str(chat.get("type") or "").lower() == "private"


def _is_admin_user(user_id) -> bool:
    return str(user_id) in _admin_user_ids()


def _authorize_update(chat: dict, from_user: dict) -> tuple[bool, str]:
    chat_id = chat.get("id")
    user_id = from_user.get("id")
    is_admin = _is_admin_user(user_id)

    if _is_private_chat(chat):
        if is_admin:
            return True, "admin_private"
        return False, "non_admin_private"

    if str(chat_id) in _allowed_chat_ids():
        return True, "allowed_group_admin" if is_admin else "allowed_group_member"

    return False, "unknown_chat"


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


def _split_message(text: str, limit: int = 3800) -> list[str]:
    text = str(text or "")
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > limit:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        if line_len > limit:
            for i in range(0, len(line), limit):
                chunks.append(line[i:i + limit])
            continue
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks or [""]


def _send_to_chat(chat_id, text: str):
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    statuses = []
    chunks = _split_message(text)
    for idx, chunk in enumerate(chunks, start=1):
        r = requests.post(url, data={"chat_id": chat_id, "text": chunk}, timeout=20)
        statuses.append(r.status_code)
        logger.info(
            "Telegram komut cevap HTTP: %s | chunk=%s/%s | len=%s",
            r.status_code,
            idx,
            len(chunks),
            len(chunk or ""),
        )
        if r.status_code != 200:
            logger.warning("Telegram komut cevabı gönderilemedi: %s | %s", r.status_code, r.text[:300])
    return statuses[-1] if statuses else None


def _handle_text(text: str) -> tuple[str, str | None]:
    reply = handle_profile_command(text)
    return "handle_profile_command", reply


def _process_update(update: dict) -> bool:
    uid = update.get("update_id")
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    from_user = msg.get("from") or {}
    chat_id = chat.get("id")
    from_user_id = from_user.get("id")
    text = msg.get("text") or ""
    text = normalize_command_text(text)

    allowed, auth_reason = _authorize_update(chat, from_user)

    logger.info(
        "Telegram update alındı | update_id=%s | chat_id=%s | chat_type=%s | from_user_id=%s | auth=%s | text=%s",
        uid,
        chat_id,
        chat.get("type"),
        from_user_id,
        auth_reason,
        str(text)[:300],
    )

    if not allowed:
        if auth_reason == "non_admin_private":
            logger.info("Telegram update reddedildi: non_admin_private | update_id=%s | chat_id=%s | from_user_id=%s", uid, chat_id, from_user_id)
            _send_to_chat(chat_id, "Bu bot özel komutları sadece admin için çalıştırır.")
            return True

        logger.info("Telegram update atlandı: %s | update_id=%s | chat_id=%s | from_user_id=%s", auth_reason, uid, chat_id, from_user_id)
        return False

    replies = []
    for line in str(text).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            handler_name, reply = _handle_text(line)
            logger.info(
                "Telegram handler seçildi | update_id=%s | handler=%s | reply_len=%s",
                uid,
                handler_name,
                len(reply or ""),
            )
            if reply:
                replies.append(reply)
        except Exception as exc:
            logger.exception("Telegram komut handler hatası | update_id=%s | text=%s", uid, line)
            replies.append(f"Komut çalıştırılamadı: {exc}")

    if not replies and str(text).strip():
        replies.append("Komut işlenemedi. /profil")

    if replies:
        payload = "\n\n".join(x for x in replies if x)
        logger.info("Telegram reply gönderiliyor | update_id=%s | chat_id=%s | reply_len=%s", uid, chat_id, len(payload))
        _send_to_chat(chat_id, payload)
        return True
    return False


def poll_once() -> bool:
    if not _LOCK.acquire(blocking=False):
        logger.info("Telegram poll atlandı: worker_lock_busy")
        return False

    handled = False

    try:
        offset = _load_offset()
        data = telegram_client.get_updates(offset=offset)

        if not data.get("ok"):
            logger.warning("Telegram getUpdates ok=false: %s", str(data)[:300])
            return False

        updates = data.get("result", []) or []
        if updates:
            logger.info("Telegram poll updates | offset=%s | update_count=%s", offset, len(updates))

        max_update_id = None
        for upd in updates:
            uid = upd.get("update_id")
            try:
                if uid is not None:
                    max_update_id = uid if max_update_id is None else max(max_update_id, uid)
                if _process_update(upd):
                    handled = True
            except Exception:
                logger.exception("Telegram update işleme hatası | update_id=%s", uid)
                msg = upd.get("message") or {}
                chat_id = (msg.get("chat") or {}).get("id")
                chat = msg.get("chat") or {}
                from_user = msg.get("from") or {}
                allowed, _auth_reason = _authorize_update(chat, from_user)
                if allowed:
                    try:
                        _send_to_chat(chat_id, "Komut işlenirken hata oluştu.")
                    except Exception:
                        logger.exception("Telegram hata cevabı gönderilemedi | update_id=%s", uid)
            finally:
                if uid is not None:
                    _save_offset(int(uid) + 1)
                    logger.info("Telegram offset kaydedildi | offset=%s", int(uid) + 1)

        if max_update_id is not None:
            _save_offset(int(max_update_id) + 1)

        return handled

    except Exception:
        logger.exception("Telegram komut worker poll hatası")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("command", nargs="*")
    args = parser.parse_args(argv)
    text = " ".join(args.command).strip()
    if args.dry_run:
        print(handle_profile_command(text) or "")
        return 0
    poll_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
