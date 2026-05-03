import logging

from clients.http_client import http_client
from config.settings import settings

logger = logging.getLogger("telegram_client")

MAX_TELEGRAM_TEXT = 4096
SAFE_TELEGRAM_TEXT = 3500
HARD_TRIM_TEXT = 3800


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


class TelegramClient:
    def send_message(self, text: str):
        safe_text = _compact_for_telegram(text)

        if len(safe_text) < len(text or ""):
            logger.warning(
                "Telegram mesajı uzun olduğu için kısaltıldı | eski=%s yeni=%s",
                len(text or ""),
                len(safe_text),
            )

        url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
        payload = {
            "chat_id": settings.chat_id,
            "text": safe_text,
            "disable_web_page_preview": True,
        }
        response = http_client.post_form(url, payload)
        print('TELEGRAM_SEND_STATUS:', getattr(response, 'status_code', None))
        print('TELEGRAM_SEND_BODY:', getattr(response, 'text', '')[:500])

    def get_updates(self, offset: int | None = None):
        url = f"https://api.telegram.org/bot{settings.bot_token}/getUpdates"
        data = {
            "timeout": 1,
            "allowed_updates": '["message"]',
        }
        if offset is not None:
            data["offset"] = offset
        response = http_client.post_form(url, data)
        return response.json()


telegram_client = TelegramClient()
