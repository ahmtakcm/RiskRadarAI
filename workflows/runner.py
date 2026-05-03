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
from commands.profile_commands import handle_profile_command
from commands.telegram_command_worker import start_telegram_command_worker
from config.paths import USER_INPUTS_DIR
import json
import requests

logger = get_logger('runner')


def _digest_story_key(item: dict) -> str:
    url = str(item.get('url', '') or '').strip().lower()
    if url:
        return url
    title = str(item.get('title', '') or '').strip().lower()
    source = str(item.get('source_name', '') or '').strip().lower()
    return f'{source}|{title}'


def _digest_is_weak(paragraph: str) -> bool:
    text = str(paragraph or '').strip()
    if len(text) < 180:
        return True
    low = text.lower()
    bad_bits = [
        'abd tarafı dahil',
        'iran bağlantılı gelişme',
        'detay için bağlantıyı aç',
        'jeopolitik gelişme',
    ]
    if sum(1 for bit in bad_bits if bit in low) >= 2:
        return True
    if text.count('  ') > 3:
        return True
    return False


def _build_fallback_digest(items: list[dict]) -> str:
    unique = []
    seen = set()
    for item in items:
        key = _digest_story_key(item)
        if key in seen:
            continue
        seen.add(key)
        summary = str(item.get('translated_text', '') or '').strip()
        if not is_usable_summary(summary, {'title': item.get('title', '')}):
            continue
        unique.append(item)

    if not unique:
        return 'Son 12 saatte anlamlı ve yeterli özet kalitesine sahip sessiz aday birikmedi.'

    bullets = []
    for item in unique[:6]:
        source = str(item.get('source_name', '') or 'Kaynak').strip()
        summary = str(item.get('translated_text', '') or '').strip().rstrip('. ')
        bullets.append(f'• {source}: {summary}.')

    intro = 'Son 12 saatte öne çıkan ve bildirim eşiğini aşmayan başlıklar:'
    return '\n'.join([intro, *bullets])[:3500]


def _maybe_send_digest(state: dict):
    now = datetime.now(timezone.utc)
    if not should_run_digest(state, now):
        return

    candidates = collect_digest_candidates(state.get('news_log', []), now)
    if not candidates:
        logger.info('Digest slotu geldi ama uygun sessiz aday yok; mesaj gönderilmedi.')
        mark_digest_run(state, now)
        settings.state_store.save_runtime_state(state)
        return

    paragraph = ai_client.build_digest_paragraph(candidates)
    if not paragraph or _digest_is_weak(paragraph):
        paragraph = _build_fallback_digest(candidates)

    if not paragraph or not str(paragraph).strip():
        logger.info('Digest paragrafı üretilemedi; mesaj gönderilmedi.')
        mark_digest_run(state, now)
        settings.state_store.save_runtime_state(state)
        return

    try:
        telegram_client.send_message(build_digest_message(now.astimezone(ISTANBUL_TZ), paragraph=paragraph))
        mark_digest_run(state, now)
        settings.state_store.save_runtime_state(state)
        logger.info('Sessiz digest gönderildi: %s | aday=%s', now.isoformat(), len(candidates))
    except Exception as exc:
        logger.warning('Digest gönderilemedi: %s', exc)



def _command_state_path():
    return USER_INPUTS_DIR / "telegram_command_state.json"


def _load_command_offset() -> int | None:
    path = _command_state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("offset")
    except Exception:
        return None


def _save_command_offset(offset: int):
    path = _command_state_path()
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"offset": offset}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _poll_telegram_commands():
    handled = False
    try:
        offset = _load_command_offset()
        logger.info('Telegram komut kontrolü çalıştı | offset=%s', offset)
        data = telegram_client.get_updates(offset=offset)
        if not data.get("ok"):
            return

        max_update_id = None
        for upd in data.get("result", []):
            uid = upd.get("update_id")
            if uid is not None:
                max_update_id = uid if max_update_id is None else max(max_update_id, uid)

            msg = upd.get("message") or {}
            chat = msg.get("chat") or {}
            text = msg.get("text") or ""

            if str(chat.get("id")) != str(settings.chat_id):
                continue

            logger.info('Telegram mesaj alındı | chat=%s | text=%s', chat.get('id'), text)
            reply = handle_profile_command(text)
            if reply:
                logger.info('Telegram profil cevabı gönderiliyor')
                logger.info('Telegram profil cevabı metni: %s', reply[:300])
                url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
                resp = requests.post(url, data={"chat_id": chat.get("id"), "text": reply}, timeout=20)
                logger.info("Telegram profil cevap HTTP: %s | %s", resp.status_code, resp.text[:200])
                handled = True

        if max_update_id is not None:
            _save_command_offset(max_update_id + 1)

        return handled

    except Exception as exc:
        logger.warning("Telegram komut kontrolü başarısız: %s", exc)
        return False

def run_forever(state: dict):
    start_telegram_command_worker()
    try:
        telegram_client.send_message('✅ Haber alarm botu başlatıldı')
    except Exception as exc:
        logger.warning('Başlangıç Telegram mesajı gönderilemedi: %s', exc)

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
                official_candidates = scan_news(state, mode='official_only')
                if official_candidates:
                    process_candidates(state, official_candidates, [], [], [])
                    settings.state_store.save_runtime_state(state)
                logger.info('Resmî kaynak taraması yapıldı')
                last_official_check = now_ts

            if now_ts - last_news_check >= settings.news_check_interval:
                social_candidates = scan_news(state, mode='social_only')
                osint_candidates = scan_news(state, mode='osint_only')
                analysis_candidates = scan_news(state, mode='analysis_only')
                process_candidates(state, [], social_candidates, osint_candidates, analysis_candidates)
                _maybe_send_digest(state)
                settings.state_store.save_runtime_state(state)
                logger.info('Haber taraması yapıldı')
                last_news_check = now_ts

            if now_ts - last_macro_update >= macro_update_interval:
                logger.info('Günlük makro update tetikleniyor')
                run_daily_update()
                last_macro_update = now_ts
                logger.info('Günlük makro update döngüde tamamlandı')

            if now_ts - last_calendar_check >= settings.calendar_check_interval:
                events = scan_calendar_events()
                process_calendar_events(state, events)
                settings.state_store.save_runtime_state(state)
                logger.info('Takvim taraması yapıldı')
                last_calendar_check = now_ts
        except Exception as exc:
            logger.exception('ANA DÖNGÜ HATASI: %s', exc)
            try:
                telegram_client.send_message(f'⚠️ Bot hata verdi\n{exc}')
            except Exception as inner_exc:
                logger.warning('Telegram hata bildirimi başarısız: %s', inner_exc)
        time.sleep(settings.loop_sleep_seconds)
