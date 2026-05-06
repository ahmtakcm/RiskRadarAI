#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.paths import BASE_DIR, REPORTS_DIR
from config.settings import settings
from core.notification_policy import notification_policy_for_source
from source_selectors.feed_selector import select_feeds
from source_selectors.profile_loader import load_active_config

SOURCE_GROUPS = [
    ('official_only', 'rules/feeds.json', 'feeds'),
    ('social_only', 'rules/social_feeds.json', 'social_feeds'),
    ('osint_only', 'rules/osint_feeds.json', 'osint_feeds'),
    ('analysis_only', 'rules/analysis_feeds.json', 'analysis_feeds'),
]


def _bool(value) -> bool:
    return bool(value)


def _entry_for_source(source: dict, source_file: str, scan_mode: str, active_config: dict) -> dict:
    overrides = active_config.get('overrides', {}) or {}
    policy = notification_policy_for_source(
        source,
        scan_mode=scan_mode,
        source_file=source_file,
        settings=settings,
        send_unverified_social=overrides.get('send_unverified_social_alerts', settings.send_unverified_social_alerts),
        send_unverified_osint=overrides.get('send_unverified_osint_alerts', True),
    )
    data = policy.as_dict()
    data.update({
        'source_name': source.get('name', ''),
        'source_file': source_file,
        'scan_mode': scan_mode,
        'kind_source_kind': source.get('kind') or source.get('source_kind') or '',
        'kind': source.get('kind', ''),
        'source_kind': source.get('source_kind', ''),
        'official_class': source.get('official_class', ''),
        'source_class': source.get('source_class', ''),
        'official_country': source.get('official_country', ''),
        'official_red_alert': _bool(source.get('official_red_alert')),
    })
    return data


def _calendar_entries(active_config: dict) -> list[dict]:
    events = (active_config.get('calendar_watch') or {}).get('events', [])
    out = []
    for event in events:
        if not event.get('enabled', True):
            continue
        source = {
            'name': event.get('source_name') or event.get('title') or event.get('id', ''),
            'kind': 'calendar',
            'notify_policy': event.get('notify_policy', 'calendar_only'),
            'confirmation_required': event.get('confirmation_required', False),
            'relay_label': event.get('relay_label', 'direct'),
        }
        policy = notification_policy_for_source(source, scan_mode='calendar', source_file='rules/calendar_watch.json', settings=settings)
        data = policy.as_dict()
        data.update({
            'source_name': source['name'],
            'source_file': 'rules/calendar_watch.json',
            'scan_mode': 'calendar',
            'kind_source_kind': 'calendar',
            'kind': 'calendar',
            'source_kind': 'calendar',
            'official_class': event.get('official_class', ''),
            'source_class': event.get('source_class', ''),
            'official_country': event.get('official_country', ''),
            'official_red_alert': _bool(event.get('official_red_alert')),
            'event_id': event.get('id', ''),
            'thresholds': event.get('pre_alerts_minutes', []),
            'post_window_minutes': event.get('post_window_minutes'),
        })
        out.append(data)
    return out


def build_audit() -> dict:
    active_config = load_active_config()
    rows = []
    counts = {}
    for scan_mode, source_file, key in SOURCE_GROUPS:
        selected = select_feeds(active_config, mode=scan_mode)
        counts[scan_mode] = len(selected)
        for source in selected:
            rows.append(_entry_for_source(source, source_file, scan_mode, active_config))
    calendar_rows = _calendar_entries(active_config)
    counts['calendar'] = len(calendar_rows)
    rows.extend(calendar_rows)
    counts['total'] = len(rows)
    return {
        'active_profile': active_config.get('profile_name'),
        'counts': counts,
        'sources': rows,
    }


def write_report(audit: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / 'notification_audit.json'
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def print_table(audit: dict) -> None:
    rows = audit['sources']
    headers = ['mode', 'source_file', 'source', 'kind', 'lane', 'policy', 'direct', 'ai', 'confirm', 'relay', 'fresh']
    widths = [12, 24, 32, 12, 24, 16, 6, 4, 8, 18, 7]
    print('Notification audit')
    print(f"active_profile={audit.get('active_profile')} total={audit.get('counts', {}).get('total')}")
    print(' '.join(h.ljust(w) for h, w in zip(headers, widths)))
    print(' '.join('-' * w for w in widths))
    for row in rows:
        values = [
            row.get('scan_mode', ''),
            row.get('source_file', ''),
            row.get('source_name', ''),
            row.get('kind_source_kind', ''),
            row.get('notification_lane', ''),
            row.get('notify_policy', ''),
            str(row.get('can_notify_direct', False)).lower(),
            str(row.get('requires_ai_should_notify', False)).lower(),
            str(row.get('requires_official_confirmation', False)).lower(),
            row.get('relay_label', ''),
            str(row.get('freshness_window_used', '') or ''),
        ]
        print(' '.join(str(v)[:w].ljust(w) for v, w in zip(values, widths)))


def main() -> int:
    audit = build_audit()
    path = write_report(audit)
    print_table(audit)
    print(f'\nJSON report: {path.relative_to(BASE_DIR)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
