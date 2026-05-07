#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.paths import BASE_DIR, REPORTS_DIR, STORAGE_DIR
from core.notification_policy import notification_policy_for_source
from source_selectors.feed_selector import select_feeds
from source_selectors.profile_loader import load_active_config
from config.settings import settings

SOURCE_GROUPS = [
    ('official_only', 'rules/feeds.json'),
    ('social_only', 'rules/social_feeds.json'),
    ('osint_only', 'rules/osint_feeds.json'),
    ('analysis_only', 'rules/analysis_feeds.json'),
]


def _load_health() -> dict:
    path = STORAGE_DIR / 'source_health.json'
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _status_for(source: dict, health: dict, now: float) -> str:
    if not source.get('enabled', True):
        return 'disabled'
    cooldown_until = float(health.get('cooldown_until') or 0)
    if cooldown_until > now:
        return 'cooldown'
    failures = int(health.get('consecutive_failures') or 0)
    if failures > 0:
        return 'degraded'
    if health.get('last_success_at'):
        return 'ok'
    return 'unknown'


def build_report() -> dict:
    active_config = load_active_config()
    health = _load_health()
    now = time.time()
    rows = []
    counts = {'ok': 0, 'degraded': 0, 'cooldown': 0, 'unknown': 0, 'disabled': 0}

    for scan_mode, source_file in SOURCE_GROUPS:
        for source in select_feeds(active_config, mode=scan_mode):
            name = source.get('name', '')
            h = health.get(name, {})
            status = _status_for(source, h, now)
            counts[status] = counts.get(status, 0) + 1
            policy = notification_policy_for_source(
                source,
                scan_mode=scan_mode,
                source_file=source.get('source_file', source_file),
                settings=settings,
                send_unverified_social=active_config.get('overrides', {}).get('send_unverified_social_alerts', settings.send_unverified_social_alerts),
                send_unverified_osint=bool(active_config.get('profile_policies', {}).get('osint', {}).get('allow_unverified', True)),
            )
            rows.append({
                'source_name': name,
                'source_file': source.get('source_file', source_file),
                'scan_mode': scan_mode,
                'kind': source.get('kind') or source.get('source_kind') or '',
                'notify_policy': policy.notify_policy,
                'relay_label': policy.relay_label,
                'applies_to_all_profiles': bool(source.get('applies_to_all_profiles')),
                'source_tags': source.get('source_tags', []),
                'status': status,
                'consecutive_failures': int(h.get('consecutive_failures') or 0),
                'cooldown_remaining_seconds': max(0, int(float(h.get('cooldown_until') or 0) - now)),
                'preferred_base': h.get('preferred_base', ''),
                'last_success_at': h.get('last_success_at'),
                'last_error': h.get('last_error', ''),
                'last_attempted_url': h.get('last_attempted_url', ''),
            })

    counts['total'] = len(rows)
    return {'active_profile': active_config.get('profile_name'), 'counts': counts, 'sources': rows}


def write_report(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / 'source_health_report.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def print_table(report: dict) -> None:
    print('Source health report')
    print(f"active_profile={report.get('active_profile')} total={report.get('counts', {}).get('total')}")
    headers = ['mode', 'source', 'status', 'fail', 'cooldown', 'policy', 'relay']
    widths = [12, 34, 10, 5, 8, 16, 18]
    print(' '.join(h.ljust(w) for h, w in zip(headers, widths)))
    print(' '.join('-' * w for w in widths))
    for row in report['sources']:
        vals = [
            row['scan_mode'],
            row['source_name'],
            row['status'],
            row['consecutive_failures'],
            row['cooldown_remaining_seconds'],
            row['notify_policy'],
            row['relay_label'],
        ]
        print(' '.join(str(v)[:w].ljust(w) for v, w in zip(vals, widths)))


def main() -> int:
    report = build_report()
    path = write_report(report)
    print_table(report)
    print(f'\nJSON report: {path.relative_to(BASE_DIR)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
