from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from core.time_utils import ISTANBUL_TZ, parse_datetime

NEWS_LOG_LIMIT = 4000
DIGEST_HOURS = {8, 20}


def _safe_text(value: str, limit: int = 4000) -> str:
    return str(value or '').strip()[:limit]


def build_log_entry(item: dict, item_id: str, **overrides) -> dict:
    entry = {
        'id': item_id,
        'timestamp': overrides.get('timestamp') or item.get('pub_date') or datetime.now(timezone.utc).isoformat(),
        'source_type': overrides.get('source_type') or _source_type(item),
        'source_name': item.get('source_name', ''),
        'title': _safe_text(item.get('title', ''), 500),
        'text': _safe_text(item.get('article_text') or item.get('description') or '', 8000),
        'url': item.get('link', ''),
        'in_scope': bool(overrides.get('in_scope', item.get('official_scope_match') or item.get('is_relevant'))),
        'alert_sent': bool(overrides.get('alert_sent', False)),
        'drop_reason': overrides.get('drop_reason'),
        'translated_text': _safe_text(overrides.get('translated_text') or item.get('translated_text', ''), 8000),
        'delivery_mode': overrides.get('delivery_mode', 'none'),
        'official_fast_track': bool(overrides.get('official_fast_track', item.get('official_fast_track'))),
        'score': overrides.get('score', item.get('score')),
        'meta': overrides.get('meta', {}),
    }
    return entry


def _source_type(item: dict) -> str:
    if item.get('source_kind') == 'rss_social':
        return 'social'
    if item.get('is_official_source') or item.get('official_class'):
        return 'official'
    return 'media'


def append_news_log(state: dict, entry: dict):
    logs = list(state.get('news_log', []))
    logs.append(entry)
    state['news_log'] = logs[-NEWS_LOG_LIMIT:]


def update_news_log(state: dict, item_id: str, **updates):
    logs = list(state.get('news_log', []))
    for idx in range(len(logs) - 1, -1, -1):
        if logs[idx].get('id') != item_id:
            continue
        merged = dict(logs[idx])
        merged.update({k: v for k, v in updates.items() if v is not None})
        logs[idx] = merged
        state['news_log'] = logs[-NEWS_LOG_LIMIT:]
        return
    # yoksa ekle
    entry = {'id': item_id}
    entry.update({k: v for k, v in updates.items() if v is not None})
    logs.append(entry)
    state['news_log'] = logs[-NEWS_LOG_LIMIT:]


def collect_digest_candidates(log_items: Iterable[dict], now: datetime) -> list[dict]:
    window_start = now - timedelta(hours=12)
    results: list[dict] = []
    seen_ids: set[str] = set()
    for item in reversed(list(log_items)):
        item_id = str(item.get('id', '') or '')
        if item_id and item_id in seen_ids:
            continue
        ts = parse_datetime(str(item.get('timestamp', '') or ''))
        if ts is None:
            continue
        ts_utc = ts.astimezone(timezone.utc)
        if ts_utc < window_start.astimezone(timezone.utc) or ts_utc > now.astimezone(timezone.utc):
            continue
        if item.get('alert_sent') is True:
            continue
        meaningful = ' '.join(str(item.get(k, '') or '').strip() for k in ('translated_text', 'title', 'text', 'url'))
        if not meaningful.strip():
            continue
        if item.get('delivery_mode') not in {'digest', 'none'}:
            continue
        results.append(item)
        if item_id:
            seen_ids.add(item_id)
    return results


DIGEST_WINDOW_MINUTES = 10


def should_run_digest(state: dict, now: datetime) -> bool:
    local_now = now.astimezone(ISTANBUL_TZ)

    if local_now.hour not in DIGEST_HOURS:
        return False

    # 08:00 / 20:00 slotunu tam dakikada kaçırmamak için pencere
    if not (0 <= local_now.minute < DIGEST_WINDOW_MINUTES):
        return False

    slot = local_now.strftime('%Y-%m-%d %H:00')
    if state.get('last_digest_slot') == slot:
        return False

    return True
def mark_digest_run(state: dict, now: datetime):
    local_now = now.astimezone(ISTANBUL_TZ)
    state['last_digest_slot'] = local_now.strftime('%Y-%m-%d %H:00')


def group_digest_items(items: Iterable[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        bucket = str(item.get('digest_bucket') or item.get('meta', {}).get('digest_bucket') or 'general')
        groups[bucket].append(item)
    return dict(groups)
