from datetime import datetime, timezone
import json
import threading
from pathlib import Path

from clients.telegram_client import telegram_client
from clients.http_client import http_client
from core.logger import get_logger
from parsers.generic_html_parser import strip_html
from workflows.signal_engine import analyze_event, export_macro_signal
from workflows.post_release_analysis import build_post_release_analysis
from workflows.macro_high_alert import activate_high_alert
from workflows.macro_event_importance import DEFAULT_PRE_ALERTS, enrich_macro_event

logger = get_logger('process_calendar_events')
CACHE_PATH = Path("storage/calendar_cache.json")
_CALENDAR_CACHE_LOCK = threading.Lock()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _load_cache() -> dict:
    with _CALENDAR_CACHE_LOCK:
        if not CACHE_PATH.exists():
            return {"events": []}
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"events": []}


def _save_cache(data: dict):
    with _CALENDAR_CACHE_LOCK:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sent(event: dict, key: str) -> bool:
    return key in event.setdefault("sent_alerts", [])


def _mark(event: dict, key: str):
    alerts = event.setdefault("sent_alerts", [])
    if key not in alerts:
        alerts.append(key)


def _scenario_text(event: dict) -> str:
    category = str(event.get("category", "")).lower()
    title = str(event.get("title", ""))

    if "tcmb" in title.lower() or category in {"economy_tr"}:
        return (
            "Şahin ton veya sıkı duruş vurgusu gelirse TL varlıklar desteklenebilir; "
            "BIST tarafında banka ve faiz hassas sektörlerde dalgalanma görülebilir. "
            "Güvercin ton gelirse kur, altın ve gümüş tarafında yukarı baskı oluşabilir."
        )

    if "opec" in title.lower() or category in {"energy"}:
        return (
            "Üretim kısıntısı veya arz riski vurgusu petrol fiyatlarını destekleyebilir; "
            "Brent tarafında yukarı baskı, enflasyon beklentilerinde artış ve risk iştahında zayıflama görülebilir. "
            "Arz artışı veya sakin ton petrol için negatif olabilir."
        )

    return (
        "Beklenenden şahin mesajlar DXY ve tahvil faizlerini destekleyebilir; "
        "altın, gümüş, borsa ve kripto üzerinde baskı oluşturabilir. "
        "Güvercin mesajlar risk iştahını destekleyip borsa ve kripto için pozitif olabilir."
    )


def _calendar_message(event: dict, mode: str, minutes_left: int | None = None):
    mode_map = {
        '24h': ('🗓️', '24 saat kala makro uyarı'),
        '3h': ('⏳', '3 saat kala makro uyarı'),
        '60m': ('⏳', '1 saat kala makro uyarı'),
        '30m': ('⏳', '30 dakika kala makro uyarı'),
        'published': ('📣', 'Makro açıklama yayımlandı'),
    }
    icon, label = mode_map.get(mode, ('📣', mode))

    lines = [
        f'{icon} MAKRO TAKVİM',
        '',
        f"Tür: {label}",
        f"Başlık: {event.get('title', '')}",
        f"Kaynak: {event.get('source_name', '')}",
        f"Kategori: {event.get('category')}" if event.get('category') else None,
        f"Zaman: {event.get('datetime', '')}",
    ]

    if minutes_left is not None:
        lines.append(f"Kalan süre: {minutes_left} dk")

    if mode in {'24h', '3h', '60m', '30m'}:
        lines += [
            '',
            'AI Ön Senaryo:',
            _scenario_text(event),
        ]

    if event.get("importance_reason"):
        lines.append(f"Önem: {event.get('importance_reason')}")

    if event.get("actual") is not None and event.get("forecast") is not None:
        lines.append(f"Veri: actual={event.get('actual')} forecast={event.get('forecast')}")

    signal = event.get("signal") or {}
    if signal:
        impact = signal.get("impact") or {}
        lines += [
            '',
            'Makro Sinyal:',
            f"Yön: {'Şahin' if signal.get('bias')=='hawkish' else 'Güvercin' if signal.get('bias')=='dovish' else signal.get('bias')}",
            f"Confidence: {signal.get('confidence', 0)}",
        ]

        if impact:
            for asset, direction in impact.items():
                lines.append(f"{asset.upper()}: " + (
        "Pozitif" if direction == "bullish" else
        "Negatif" if direction == "bearish" else
        direction
    ))

    if event.get('watch_urls'):
        lines += ['', 'İzlenen bağlantılar:']
        lines.extend(event['watch_urls'][:2])

    return '\n'.join(lines)


def _thresholds_for_event(event: dict) -> list[tuple[str, int]]:
    labels = {
        1440: "24h",
        180: "3h",
        60: "60m",
        30: "30m",
    }
    raw_minutes = event.get("pre_alerts_minutes")
    if raw_minutes is None:
        raw_minutes = DEFAULT_PRE_ALERTS

    thresholds = []
    for minute in raw_minutes:
        try:
            minute_int = int(minute)
        except (TypeError, ValueError):
            continue
        thresholds.append((labels.get(minute_int, f"{minute_int}m"), minute_int))

    return sorted(thresholds, key=lambda item: item[1], reverse=True)


def _check_publish_signals(event: dict) -> bool:
    signals = [s.lower() for s in event.get('publish_signals', []) if s]
    if not signals:
        return False

    for url in event.get('watch_urls', []):
        try:
            text = strip_html(http_client.get_text(url)).lower()
            if any(signal in text for signal in signals):
                return True
        except Exception as exc:
            logger.warning('Takvim yayın kontrolü başarısız (%s): %s', url, exc)

    return False


def _handle_event(event: dict, now: datetime) -> bool:
    changed = False
    enrich_macro_event(event)

    try:
        event_time = _parse_iso(event['datetime']).astimezone(timezone.utc)
    except Exception as exc:
        logger.warning('Geçersiz takvim tarihi (%s): %s', event.get('id'), exc)
        event["status"] = "invalid"
        return True

    delta_minutes = int((event_time - now).total_seconds() // 60)
    post_window = int(event.get('post_window_minutes', 0) or 0)

    try:
        event["signal"] = analyze_event({
            "type": event.get("event_type") or event.get("category") or "",
            "title": event.get("title") or "",
            "text": event.get("summary") or event.get("description") or "",
        })
        export_macro_signal(event["signal"], event)
    except Exception as exc:
        logger.warning("Makro sinyal analizi başarısız (%s): %s", event.get("id"), exc)

    # Tamamen geçmiş event: yayın penceresi de geçtiyse kapat
    if delta_minutes < -post_window:
        if event.get("status") != "done":
            event["status"] = "done"
            logger.info("Takvim geçmiş event pasifleştirildi: %s", event.get("id"))
            changed = True
        return changed

    # 24 saatten uzaksa sessiz
    if delta_minutes > 1440:
        return changed

    thresholds = _thresholds_for_event(event)

    if delta_minutes >= 0:
        for key, threshold in thresholds:
            if delta_minutes <= threshold and _sent(event, key):
                logger.info("Notification drop | source=%s | policy=calendar_only | lane=calendar_threshold | reason=cooldown | key=%s:%s", event.get('source_name', ''), event.get('id'), key)
                continue
            if delta_minutes <= threshold and not _sent(event, key):
                telegram_client.send_message(_calendar_message(event, key, delta_minutes))

                if key in {"60m", "30m"}:
                    activate_high_alert(event, mode="pre_event", hours=3)

                _mark(event, key)
                logger.info("Notification sent | source=%s | policy=calendar_only | lane=calendar_threshold | reason=%s | key=%s", event.get('source_name', ''), key, event.get('id'))
                logger.info("Takvim geri sayım alarmı gönderildi: %s %s", event.get("id"), key)
                changed = True
                break

    # Event zamanı geçtiyse yayın kontrolü
    if delta_minutes <= 0 and abs(delta_minutes) <= post_window and _sent(event, "published"):
        logger.info("Notification drop | source=%s | policy=calendar_only | lane=calendar_threshold | reason=cooldown | key=%s:published", event.get('source_name', ''), event.get('id'))

    if delta_minutes <= 0 and abs(delta_minutes) <= post_window and not _sent(event, "published"):
        if _check_publish_signals(event):
            telegram_client.send_message(_calendar_message(event, "published"))

            try:
                release_text = ""
                for url in event.get("watch_urls", []):
                    try:
                        release_text += http_client.get_text(url)[:4000]
                    except Exception:
                        pass

                if release_text:
                    telegram_client.send_message(build_post_release_analysis(event, release_text))
            except Exception as exc:
                logger.warning("Makro açıklama analizi gönderilemedi (%s): %s", event.get("id"), exc)

            activate_high_alert(event, mode="post_release", hours=3)

            _mark(event, "published")
            event["status"] = "done"
            logger.info("Notification sent | source=%s | policy=calendar_only | lane=calendar_threshold | reason=published | key=%s", event.get('source_name', ''), event.get('id'))
            logger.info("Takvim yayınlandı alarmı gönderildi: %s", event.get("id"))
            changed = True

    return changed


def process_calendar_events(state: dict, events: list):
    data = _load_cache()
    cache_events = data.get("events", [])

    if not cache_events:
        cache_events = events or []
        data["events"] = cache_events

    now = datetime.now(timezone.utc)
    changed = False

    for event in cache_events:
        if event.get("status", "active") != "active":
            continue
        if _handle_event(event, now):
            changed = True

    if changed:
        _save_cache(data)
