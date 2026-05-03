from __future__ import annotations

from core.time_utils import age_minutes


def freshness_limit_minutes(mode: str, settings) -> int:
    mapping = {
        'social_only': settings.social_max_age_minutes,
        'osint_only': settings.osint_max_age_minutes,
        'official_only': settings.official_max_age_minutes,
        'analysis_only': settings.analysis_max_age_minutes,
        'all': settings.news_max_age_minutes,
    }
    return int(mapping.get(mode, settings.news_max_age_minutes))


def _item_limit_minutes(item: dict, mode: str, settings) -> int:
    raw = item.get('stale_minutes')
    try:
        if raw not in (None, '', 0, '0'):
            return int(raw)
    except Exception:
        pass
    return freshness_limit_minutes(mode, settings)


def evaluate_item_freshness(item: dict, mode: str, settings) -> dict:
    pub_date = item.get('pub_date', '')
    minutes = age_minutes(pub_date)
    limit = _item_limit_minutes(item, mode, settings)
    stale = False
    if minutes is not None and settings.drop_stale_items:
        stale = minutes > limit
    return {
        'age_minutes': minutes,
        'max_age_minutes': limit,
        'is_stale': stale,
    }
