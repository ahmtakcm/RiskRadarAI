import time
from datetime import datetime, timezone
from config.settings import settings
from core.time_utils import ISTANBUL_TZ
from core.logger import get_logger
from core.news_log import collect_digest_candidates, mark_digest_run, should_run_digest
from clients.ai_client import ai_client
from clients.telegram_client import telegram_client
from services.assistant_output import build_digest_message
from filters.ai_parse import is_usable_summary
from workflows.scan_news import scan_news
from workflows.process_candidates import process_candidates
from workflows.scan_calendar import scan_calendar_events
from workflows.process_calendar_events import process_calendar_events
from workflows.daily_macro_update import run_daily_update
from commands.telegram_command_worker import start_telegram_command_worker

logger = get_logger("runner")


def _digest_story_key(item: dict) -> str:
    url = str(item.get("url", "") or item.get("link", "") or "").strip().lower()
    if url:
        return url
    title = str(item.get("title", "") or "").strip().lower()
    source = str(item.get("source_name", "") or "").strip().lower()
    return f"{source}|{title}"


def _digest_slot(now: datetime) -> str:
    return now.astimezone(ISTANBUL_TZ).strftime("%Y-%m-%d %H:00")


def _digest_is_weak(paragraph: str) -> bool:
    text = str(paragraph or "").strip()
    if len(text) < 180:
        return True
    low = text.lower()
    bad_bits = [
        "abd tarafı dahil",
        "iran bağlantılı gelişme",
        "detay için bağlantıyı aç",
        "jeopolitik gelişme",
    ]
    if sum(1 for bit in bad_bits if bit in low) >= 2:
        return True
    if text.count("  ") > 3:
        return True
    return False


def _item_digest_text(item: dict) -> str:
    summary = str(item.get("translated_text", "") or "").strip()
    if summary and is_usable_summary(summary, {"title": item.get("title", "")}):
        return summary.rstrip(". ")
    title = str(item.get("title", "") or "").strip()
    text = str(item.get("text", "") or item.get("description", "") or "").strip()
    if title:
        return title.rstrip(". ")
    return text[:220].rstrip(". ")


def _usable_digest_candidates(items: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for item in items:
        key = _digest_story_key(item)
        if key in seen:
            continue
        seen.add(key)
        if not _item_digest_text(item):
            continue
        unique.append(item)
    return unique


def _build_fallback_digest(items: list[dict]) -> str:
    unique = _usable_digest_candidates(items)
    if not unique:
        return ""

    bullets = []
    for item in unique[:6]:
        source = str(item.get("source_name", "") or "Kaynak").strip()
        summary = _item_digest_text(item)
        url = str(item.get("url", "") or item.get("link", "") or "").strip()
        line = f"• {source}: {summary}."
        if url:
            line += f" {url}"
        bullets.append(line)

    intro = "Son 12 saatte öne çıkan ve bildirim eşiğini aşmayan başlıklar:"
    return "\n".join([intro, *bullets])[:3500]


def build_digest_result(
    state: dict, *, now: datetime | None = None, force: bool = False, send: bool = False
) -> dict:
    now = now or datetime.now(timezone.utc)
    current_slot = _digest_slot(now)
    last_slot = state.get("last_digest_slot")
    due = force or should_run_digest(state, now)
    base = {
        "status": "digest_not_due",
        "candidate_count": 0,
        "usable_candidate_count": 0,
        "last_digest_slot": last_slot,
        "current_slot": current_slot,
        "sent": False,
        "message": "",
    }

    if not due:
        logger.info(
            "digest_not_due | last_digest_slot=%s | current_slot=%s",
            last_slot,
            current_slot,
        )
        base["message"] = (
            f'Digest zamanı değil. Son slot: {last_slot or "yok"} | geçerli slot: {current_slot}'
        )
        return base

    candidates = collect_digest_candidates(state.get("news_log", []), now)
    usable = _usable_digest_candidates(candidates)
    base.update(candidate_count=len(candidates), usable_candidate_count=len(usable))

    if not candidates:
        logger.info(
            "no_candidates | candidate_count=0 | usable_candidate_count=0 | last_digest_slot=%s | current_slot=%s",
            last_slot,
            current_slot,
        )
        base["status"] = "no_candidates"
        base["message"] = "Digest adayı yok; gönderim yapılmadı."
        if not force:
            mark_digest_run(state, now)
            settings.state_store.save_runtime_state(state)
        return base

    if not usable:
        logger.info(
            "no_usable_candidates | candidate_count=%s | usable_candidate_count=0 | last_digest_slot=%s | current_slot=%s",
            len(candidates),
            last_slot,
            current_slot,
        )
        base["status"] = "no_usable_candidates"
        base["message"] = (
            "Digest adayı var ama kullanılabilir başlık/özet/link yok; slot başarılı sayılmadı."
        )
        return base

    paragraph = ""
    try:
        paragraph = ai_client.build_digest_paragraph(usable)
    except Exception as exc:
        logger.warning(
            "weak_or_empty_paragraph | reason=ai_exception | error=%s | candidate_count=%s | usable_candidate_count=%s | last_digest_slot=%s | current_slot=%s",
            exc,
            len(candidates),
            len(usable),
            last_slot,
            current_slot,
        )

    if not paragraph or _digest_is_weak(paragraph):
        logger.info(
            "weak_or_empty_paragraph | candidate_count=%s | usable_candidate_count=%s | last_digest_slot=%s | current_slot=%s",
            len(candidates),
            len(usable),
            last_slot,
            current_slot,
        )
        paragraph = _build_fallback_digest(usable)
        if paragraph:
            logger.info(
                "fallback_used | candidate_count=%s | usable_candidate_count=%s | last_digest_slot=%s | current_slot=%s",
                len(candidates),
                len(usable),
                last_slot,
                current_slot,
            )

    if not paragraph or not str(paragraph).strip():
        logger.info(
            "no_usable_candidates | reason=empty_fallback | candidate_count=%s | usable_candidate_count=%s | last_digest_slot=%s | current_slot=%s",
            len(candidates),
            len(usable),
            last_slot,
            current_slot,
        )
        base["status"] = "no_usable_candidates"
        base["message"] = "Digest paragrafı üretilemedi; slot başarılı sayılmadı."
        return base

    message = build_digest_message(now.astimezone(ISTANBUL_TZ), paragraph=paragraph)
    base["message"] = message

    if not send:
        base["status"] = "ready"
        return base

    try:
        telegram_client.send_message(message)
        mark_digest_run(state, now)
        settings.state_store.save_runtime_state(state)
        logger.info(
            "sent | candidate_count=%s | usable_candidate_count=%s | last_digest_slot=%s | current_slot=%s",
            len(candidates),
            len(usable),
            last_slot,
            current_slot,
        )
        base["status"] = "sent"
        base["sent"] = True
        base["last_digest_slot"] = state.get("last_digest_slot")
        return base
    except Exception as exc:
        logger.warning(
            "send_failed | error=%s | candidate_count=%s | usable_candidate_count=%s | last_digest_slot=%s | current_slot=%s",
            exc,
            len(candidates),
            len(usable),
            last_slot,
            current_slot,
        )
        base["status"] = "send_failed"
        base["message"] = f"Digest gönderilemedi: {exc}"
        return base


def build_digest_now_reply(state: dict | None = None) -> str:
    state = state if state is not None else settings.state_store.load_runtime_state()
    result = build_digest_result(state, force=True, send=False)
    status = result.get("status")
    if status == "ready":
        return result.get("message") or "Digest üretildi ama mesaj boş."
    return f"Digest çalışmadı: {status}\n{result.get('message', '')}".strip()


def _maybe_send_digest(state: dict):
    build_digest_result(state, force=False, send=True)


def run_forever(state: dict):
    start_telegram_command_worker()
    try:
        telegram_client.send_message("✅ Haber alarm botu başlatıldı")
    except Exception as exc:
        logger.warning("Başlangıç Telegram mesajı gönderilemedi: %s", exc)

    last_official_check = 0
    last_news_check = 0
    last_calendar_check = 0
    last_macro_update = 0
    macro_update_interval = 86400
    official_interval = 60

    while True:
        try:
            now_ts = time.time()

            official_candidates = []
            if now_ts - last_official_check >= official_interval:
                official_candidates = scan_news(state, mode="official_only")
                if official_candidates:
                    process_candidates(state, official_candidates, [], [], [])
                    settings.state_store.save_runtime_state(state)
                logger.info("Resmî kaynak taraması yapıldı")
                last_official_check = now_ts

            if now_ts - last_news_check >= settings.news_check_interval:
                social_candidates = scan_news(state, mode="social_only")
                osint_candidates = scan_news(state, mode="osint_only")
                analysis_candidates = scan_news(state, mode="analysis_only")
                process_candidates(
                    state, [], social_candidates, osint_candidates, analysis_candidates
                )
                _maybe_send_digest(state)
                settings.state_store.save_runtime_state(state)
                logger.info("Haber taraması yapıldı")
                last_news_check = now_ts

            if now_ts - last_macro_update >= macro_update_interval:
                logger.info("Günlük makro update tetikleniyor")
                run_daily_update()
                last_macro_update = now_ts
                logger.info("Günlük makro update döngüde tamamlandı")

            if now_ts - last_calendar_check >= settings.calendar_check_interval:
                events = scan_calendar_events()
                process_calendar_events(state, events)
                settings.state_store.save_runtime_state(state)
                logger.info("Takvim taraması yapıldı")
                last_calendar_check = now_ts
        except Exception as exc:
            logger.exception("ANA DÖNGÜ HATASI: %s", exc)
            try:
                telegram_client.send_message(f"⚠️ Bot hata verdi\n{exc}")
            except Exception as inner_exc:
                logger.warning("Telegram hata bildirimi başarısız: %s", inner_exc)
        time.sleep(settings.loop_sleep_seconds)
