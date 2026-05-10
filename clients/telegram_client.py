import logging
import re
from typing import Any

import requests

from clients.http_client import http_client
from config.settings import settings

logger = logging.getLogger("telegram_client")

MAX_TELEGRAM_TEXT = 4096
SAFE_TELEGRAM_TEXT = 3500
HARD_TRIM_TEXT = 3800
TOKEN_RE = re.compile(r"(https://api\.telegram\.org/bot)([^/\s]+)")


class TelegramSendError(RuntimeError):
    pass


class TelegramChatMigrated(TelegramSendError):
    def __init__(self, new_chat_id: int | str):
        self.new_chat_id = str(new_chat_id)
        super().__init__(f"Telegram chat migrated to {self.new_chat_id}")


def mask_token_text(value: Any) -> str:
    text = str(value or "")
    if settings.bot_token:
        text = text.replace(settings.bot_token, "<SECRET>")
    return TOKEN_RE.sub(r"\1<SECRET>", text)


def _compact_for_telegram(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "⚠️ Boş mesaj üretildi."

    if len(t) <= SAFE_TELEGRAM_TEXT:
        return t

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

    header_lines = []
    body_lines = []
    link_lines = []

    for ln in lines:
        if ln.startswith("http://") or ln.startswith("https://"):
            link_lines.append(ln)
        elif (
            ln.startswith("📢")
            or ln.startswith("Kaynak:")
            or ln.startswith("Haber yaşı:")
            or ln.startswith("Başlık:")
        ):
            header_lines.append(ln)
        else:
            body_lines.append(ln)

    body_text = " ".join(body_lines).strip()

    if len(body_text) > 2200:
        body_text = body_text[:2200].rstrip() + " ...[özetlendi]"

    out = []
    out.extend(header_lines[:6])

    if body_text:
        if out:
            out.append("")
        out.append(body_text)

    if link_lines:
        out.append("")
        out.append(link_lines[0])

    compact = "\n".join(out).strip()

    if len(compact) > HARD_TRIM_TEXT:
        compact = compact[:HARD_TRIM_TEXT].rstrip() + "\n\n...[kısaltıldı]"

    if len(compact) > MAX_TELEGRAM_TEXT:
        compact = compact[: MAX_TELEGRAM_TEXT - 20].rstrip() + "\n\n...[kısaltıldı]"

    return compact


def _telegram_api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.bot_token}/{method}"


def _response_body(response) -> tuple[dict, str]:
    if response is None:
        return {}, ""
    try:
        body_json = response.json()
        return body_json, mask_token_text(str(body_json))[:500]
    except Exception:
        return {}, mask_token_text(getattr(response, "text", ""))[:500]


def _migrate_to_chat_id(body_json: dict) -> Any:
    params = body_json.get("parameters") if isinstance(body_json, dict) else None
    if isinstance(params, dict):
        return params.get("migrate_to_chat_id")
    return None


class TelegramClient:
    def send_message(self, text: str, chat_id: str | int | None = None, *, disable_web_page_preview: bool = True):
        safe_text = _compact_for_telegram(text)
        target_chat_id = settings.chat_id if chat_id is None else chat_id

        if len(safe_text) < len(text or ""):
            logger.warning(
                "Telegram mesajı uzun olduğu için kısaltıldı | eski=%s yeni=%s",
                len(text or ""),
                len(safe_text),
            )

        payload = {
            "chat_id": target_chat_id,
            "text": safe_text,
            "disable_web_page_preview": disable_web_page_preview,
        }
        try:
            response = http_client.post_form(_telegram_api_url("sendMessage"), payload)
        except requests.HTTPError as exc:
            response = exc.response
            body_json, body = _response_body(response)
            retry_after = (body_json.get("parameters") or {}).get("retry_after") if isinstance(body_json, dict) else None
            migrated_to = _migrate_to_chat_id(body_json)
            status = getattr(response, "status_code", None)

            if migrated_to:
                logger.error(
                    "Telegram chat migrated | old_chat_id=%s | new_chat_id=%s | status=%s",
                    target_chat_id,
                    migrated_to,
                    status,
                )
                raise TelegramChatMigrated(migrated_to) from exc

            if retry_after:
                logger.warning("Telegram rate limit verdi | retry_after=%s sn | body=%s", retry_after, body)
            else:
                logger.warning("Telegram mesajı gönderilemedi | status=%s | body=%s", status, body)
            raise TelegramSendError(mask_token_text(str(exc))) from exc
        except requests.RequestException as exc:
            logger.warning("Telegram mesajı gönderilemedi | error=%s", mask_token_text(str(exc)))
            raise TelegramSendError(mask_token_text(str(exc))) from exc

        logger.info(
            "Telegram mesajı gönderildi | status=%s | chars=%s | chat_id=%s",
            getattr(response, "status_code", None),
            len(safe_text),
            target_chat_id,
        )
        return response

    def get_updates(self, offset: int | None = None):
        data = {
            "timeout": 1,
            "allowed_updates": '["message"]',
        }
        if offset is not None:
            data["offset"] = offset
        try:
            response = http_client.post_form(_telegram_api_url("getUpdates"), data)
        except requests.RequestException as exc:
            logger.warning("Telegram getUpdates başarısız | error=%s", mask_token_text(str(exc)))
            raise TelegramSendError(mask_token_text(str(exc))) from exc
        return response.json()


telegram_client = TelegramClient()
