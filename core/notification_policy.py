from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DROP_REASON_CATALOG = [
    'stale',
    'official_critical_digest_kept',
    'official_critical_relevance_kept',
    'not_relevant',
    'routine_suppressed',
    'below_alert_threshold',
    'unverified_hold',
    'scan_limit_reached',
    'cooldown',
    'no_usable_summary',
]

NEWS_LANES = {
    'strict_official_direct',
    'primary_news_ai',
    'social_ai_or_verified',
    'osint_ai_or_verified',
    'analysis_priority',
    'calendar_threshold',
}


@dataclass(frozen=True)
class NotificationPolicy:
    notification_lane: str
    notify_policy: str
    can_notify_direct: bool
    requires_ai_should_notify: bool
    requires_official_confirmation: bool
    can_be_digest_only: bool
    drop_reasons: list[str]
    cooldown_setting_used: Any
    freshness_window_used: Any
    relay_archive: bool
    relay_label: str

    def as_dict(self) -> dict:
        return {
            'notification_lane': self.notification_lane,
            'notify_policy': self.notify_policy,
            'can_notify_direct': self.can_notify_direct,
            'requires_ai_should_notify': self.requires_ai_should_notify,
            'requires_official_confirmation': self.requires_official_confirmation,
            'can_be_digest_only': self.can_be_digest_only,
            'drop_reasons': list(self.drop_reasons),
            'cooldown_setting_used': self.cooldown_setting_used,
            'freshness_window_used': self.freshness_window_used,
            'relay_archive': self.relay_archive,
            'relay_label': self.relay_label,
        }


def is_relay_or_archive(source: dict) -> bool:
    blob = ' '.join([
        str(source.get('name', '') or ''),
        str(source.get('source_class', '') or ''),
        str(source.get('source_family', '') or ''),
        str(source.get('notes', '') or ''),
    ]).lower()
    return 'relay' in blob or 'archive' in blob or 'ar?iv' in blob


def relay_label_for(source: dict) -> str:
    explicit = str(source.get('relay_label', '') or '').strip()
    if explicit:
        return explicit
    if not is_relay_or_archive(source):
        return 'direct'
    source_class = str(source.get('source_class', '') or '').strip()
    source_family = str(source.get('source_family', '') or '').strip()
    if source_class:
        return source_class
    if source_family:
        return source_family
    return 'relay'


def source_kind_for(source: dict) -> str:
    return str(source.get('kind') or source.get('source_kind') or '').strip()


def is_strict_official(source: dict) -> bool:
    return str(source.get('official_class', '') or '').strip().lower().startswith('official_')


def infer_lane(source: dict, scan_mode: str | None = None, source_file: str | None = None) -> str:
    scan_mode = str(scan_mode or '').strip()
    source_file = str(source_file or '').strip()
    kind = source_kind_for(source)
    if source_file.endswith('calendar_watch.json') or kind == 'calendar':
        return 'calendar_threshold'
    if scan_mode == 'social_only' or source_file.endswith('social_feeds.json'):
        return 'social_ai_or_verified'
    if scan_mode == 'osint_only' or source_file.endswith('osint_feeds.json'):
        return 'osint_ai_or_verified'
    if scan_mode == 'analysis_only' or source_file.endswith('analysis_feeds.json'):
        return 'analysis_priority'
    if is_strict_official(source):
        return 'strict_official_direct'
    return 'primary_news_ai'


def policy_name_for_lane(lane: str, source: dict | None = None) -> str:
    source = source or {}
    explicit = str(source.get('notify_policy', '') or '').strip()
    if explicit:
        return explicit
    return {
        'strict_official_direct': 'direct_official',
        'primary_news_ai': 'ai_threshold',
        'social_ai_or_verified': 'verified_or_ai',
        'osint_ai_or_verified': 'keyword_or_score',
        'analysis_priority': 'ai_threshold',
        'calendar_threshold': 'calendar_only',
    }.get(lane, 'support_only')


def freshness_window_for(source: dict, scan_mode: str, settings) -> int | None:
    raw = source.get('stale_minutes')
    try:
        if raw not in (None, '', 0, '0'):
            return int(raw)
    except Exception:
        pass
    if scan_mode == 'social_only':
        return int(settings.social_max_age_minutes)
    if scan_mode == 'osint_only':
        return int(settings.osint_max_age_minutes)
    if scan_mode == 'analysis_only':
        return int(settings.analysis_max_age_minutes)
    if scan_mode == 'official_only':
        return int(settings.official_max_age_minutes)
    if scan_mode == 'all':
        return int(settings.news_max_age_minutes)
    return None


def _settings_or_default(settings):
    if settings is not None:
        return settings
    from config.settings import settings as runtime_settings
    return runtime_settings


def notification_policy_for_source(
    source: dict,
    *,
    scan_mode: str | None = None,
    source_file: str | None = None,
    settings=None,
    send_unverified_social: bool = True,
    send_unverified_osint: bool = True,
) -> NotificationPolicy:
    settings = _settings_or_default(settings)
    lane = infer_lane(source, scan_mode=scan_mode, source_file=source_file)
    policy = policy_name_for_lane(lane, source)
    relay = is_relay_or_archive(source)
    label = relay_label_for(source)

    if lane == 'strict_official_direct':
        can_direct = True
        requires_ai = False
        requires_confirmation = False
        digest = False
        reasons = ['stale', 'not_relevant', 'routine_suppressed', 'scan_limit_reached', 'cooldown', 'no_usable_summary']
    elif lane == 'primary_news_ai':
        can_direct = True
        requires_ai = True
        requires_confirmation = False
        digest = True
        reasons = ['stale', 'not_relevant', 'routine_suppressed', 'below_alert_threshold', 'scan_limit_reached', 'cooldown', 'no_usable_summary']
    elif lane == 'social_ai_or_verified':
        can_direct = bool(send_unverified_social)
        requires_ai = True
        requires_confirmation = not bool(send_unverified_social)
        digest = True
        reasons = ['stale', 'not_relevant', 'below_alert_threshold', 'unverified_hold', 'scan_limit_reached', 'cooldown', 'no_usable_summary']
    elif lane == 'osint_ai_or_verified':
        can_direct = bool(send_unverified_osint)
        requires_ai = True
        requires_confirmation = False
        digest = True
        reasons = ['stale', 'not_relevant', 'below_alert_threshold', 'unverified_hold', 'scan_limit_reached', 'cooldown', 'no_usable_summary']
    elif lane == 'analysis_priority':
        can_direct = True
        requires_ai = True
        requires_confirmation = False
        digest = True
        reasons = ['stale', 'not_relevant', 'below_alert_threshold', 'scan_limit_reached', 'cooldown', 'no_usable_summary']
    elif lane == 'calendar_threshold':
        can_direct = True
        requires_ai = False
        requires_confirmation = False
        digest = False
        reasons = ['cooldown']
    else:
        can_direct = False
        requires_ai = False
        requires_confirmation = True
        digest = True
        reasons = DROP_REASON_CATALOG[:]

    if source.get('confirmation_required') is True and lane != 'osint_ai_or_verified':
        requires_confirmation = True

    cooldown = 'sent_alerts' if lane == 'calendar_threshold' else getattr(settings, 'news_cooldown_seconds', None)
    freshness = None if lane == 'calendar_threshold' else freshness_window_for(source, str(scan_mode or ''), settings)
    return NotificationPolicy(
        notification_lane=lane,
        notify_policy=policy,
        can_notify_direct=can_direct,
        requires_ai_should_notify=requires_ai,
        requires_official_confirmation=requires_confirmation,
        can_be_digest_only=digest,
        drop_reasons=reasons,
        cooldown_setting_used=cooldown,
        freshness_window_used=freshness,
        relay_archive=relay,
        relay_label=label,
    )


def source_policy_metadata(source: dict, *, scan_mode: str | None = None, source_file: str | None = None, settings=None, send_unverified_social: bool = True, send_unverified_osint: bool = True) -> dict:
    policy = notification_policy_for_source(
        source,
        scan_mode=scan_mode,
        source_file=source_file,
        settings=settings,
        send_unverified_social=send_unverified_social,
        send_unverified_osint=send_unverified_osint,
    )
    return {
        'notify_policy': policy.notify_policy,
        'confirmation_required': policy.requires_official_confirmation,
        'relay_label': policy.relay_label,
        'matching_mode': source.get('matching_mode', 'keyword'),
        'ai_matching_enabled': bool(source.get('ai_matching_enabled', False)),
        'allow_unverified': bool(source.get('allow_unverified', True)),
    }


def item_policy_context(item: dict, *, origin_label: str | None = None, settings=None, send_unverified_social: bool = True, send_unverified_osint: bool = True) -> dict:
    source = dict(item or {})
    scan_mode = str(source.get('scan_mode') or '')
    source_file = str(source.get('source_file') or '')
    if origin_label and not scan_mode:
        low = origin_label.lower()
        scan_mode = {
            'sosyal': 'social_only',
            'osint': 'osint_only',
            'analiz': 'analysis_only',
            'haber': 'official_only',
            'resmi': 'official_only',
            'resm?/kurumsal': 'official_only',
        }.get(low, '')
    policy = notification_policy_for_source(
        source,
        scan_mode=scan_mode,
        source_file=source_file,
        settings=settings,
        send_unverified_social=send_unverified_social,
        send_unverified_osint=send_unverified_osint,
    )
    data = policy.as_dict()
    data['source_name'] = source.get('source_name') or source.get('name') or ''
    data['notify_policy'] = source.get('notify_policy') or data['notify_policy']
    data['relay_label'] = source.get('relay_label') or data['relay_label']
    return data
