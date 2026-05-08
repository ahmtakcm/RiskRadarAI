from __future__ import annotations

import re
from dataclasses import dataclass

from source_selectors.profile_loader import load_config_for_profile
from workflows.scan_news import scan_news


MANUAL_COMMANDS = ('/ara', '/tara')

# Telegram-visible, stable profile IDs (avoid filesystem surprises in command UX)
KNOWN_PROFILE_IDS = {
    'resmi_aciklamalar',
    'ekonomi',
    'saglik',
    'dunya',
    'turkiye',
    'yerel',
    'osint',
    'analiz',
    'tum_profiller',
}


def _format_results(query: str, candidates: list[dict], *, limit: int = 8) -> str:
    if not candidates:
        return f"Manuel arama sonucu yok: {query}"
    lines = [f"Manuel arama: {query}", ""]
    for candidate in candidates[:limit]:
        item = candidate.get('item', {})
        source = item.get('source_name', 'Bilinmiyor')
        title = item.get('title', '').strip() or '(başlık yok)'
        score = candidate.get('score', 0)
        profiles = item.get('triggered_profiles') or []
        suffix = f" | profiller: {', '.join(profiles)}" if profiles else ''

        origin = ''
        if candidate.get('scan_mode') == 'osint_only' or str(item.get('source_file', '')).endswith('osint_feeds.json'):
            origin = ' | OSINT / teyitsiz sinyal'

        lines.append(f"- {source} | skor={score}{suffix}{origin}")
        lines.append(f"  {title}")
        if item.get('link'):
            lines.append(f"  {item['link']}")
    return '\n'.join(lines)[:3800]


def _is_known_profile_id(value: str) -> bool:
    return str(value or '').strip().lower() in KNOWN_PROFILE_IDS


@dataclass(frozen=True)
class _SettingsProxy:
    drop_stale_items: bool
    social_max_age_minutes: int
    osint_max_age_minutes: int
    official_max_age_minutes: int
    news_max_age_minutes: int
    analysis_max_age_minutes: int


_DURATION_RE = re.compile(r'^\s*(\d+)\s*([sh])\s*$', re.IGNORECASE)


def _parse_duration_hours(text: str) -> int | None:
    m = _DURATION_RE.match(str(text or ''))
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(2).lower()
    # Türkçe komut bağlamında: "s" = saat
    if unit in ('s', 'h'):
        return value
    return None


def _settings_with_window(hours: int):
    # override only freshness windows for manual tarama; keep stale dropping enabled
    minutes = max(0, int(hours) * 60)
    from config.settings import settings as runtime_settings
    return _SettingsProxy(
        drop_stale_items=True,
        social_max_age_minutes=minutes,
        osint_max_age_minutes=minutes,
        official_max_age_minutes=minutes,
        news_max_age_minutes=minutes,
        analysis_max_age_minutes=minutes,
    ), runtime_settings


def handle_manual_scan_command(text: str) -> str | None:
    raw = (text or '').strip()
    if not raw.startswith(MANUAL_COMMANDS):
        return None

    cmd, _, rest = raw.partition(' ')
    rest = rest.strip()
    if not rest:
        return (
            "🔎 Manuel tarama için konu yazmalısın.\n\n"
            "Örnekler:\n"
            "/tara hormuz\n"
            "/tara ekonomi brent\n"
            "/ara resmi_aciklamalar nato"
        )

    tokens = rest.split()
    profile_id = None
    if tokens and _is_known_profile_id(tokens[0]):
        profile_id = tokens[0].lower()
        rest = rest[len(tokens[0]):].strip()
        if not rest:
            return f"Eksik kullanım. Örn: {cmd} {profile_id} hormuz"

    # legacy behavior: /ara hürmüz, /tara hürmüz
    if not profile_id:
        query = rest
        mode_limits = {'official_only': 14, 'social_only': 5, 'osint_only': 3, 'analysis_only': 5}
        modes = ['official_only'] if cmd == '/ara' else ['official_only', 'social_only', 'osint_only', 'analysis_only']
        candidates = []
        state = {}
        settings_override = _settings_with_window(24)[0] if cmd == '/ara' else None
        for mode in modes:
            candidates.extend(scan_news(state, mode=mode, manual_query=query, max_feeds=mode_limits.get(mode), settings_override=settings_override))
        candidates.sort(key=lambda x: (x.get('pattern_hits', 0), x.get('score', 0)), reverse=True)
        return _format_results(query, candidates)

    # scoped behavior
    scoped_config = load_config_for_profile(profile_id, active_profile_names=[profile_id])

    if cmd == '/ara':
        query = rest
        candidates = []
        state = {}
        scoped_search_modes = {
            'osint': ('osint_only', 8),
            'analiz': ('analysis_only', 8),
        }
        search_mode, limit = scoped_search_modes.get(profile_id, ('official_only', 14))
        settings_override = _settings_with_window(24)[0]
        candidates.extend(scan_news(state, mode=search_mode, manual_query=query, max_feeds=limit, active_config=scoped_config, settings_override=settings_override))
        candidates.sort(key=lambda x: (x.get('pattern_hits', 0), x.get('score', 0)), reverse=True)
        if not candidates:
            hint = "Not: Sorgu bu profil kapsamı dışında olabilir. /profile_policy ile anahtar kelimeleri kontrol et."
            return "Bu profilin mevcut kaynaklarında belirtilen konuda sonuç bulunamadı.\n" + hint
        return _format_results(query, candidates)

    # /tara <profile> <duration_or_query>
    second = rest.split()[0]
    hours = _parse_duration_hours(second)
    settings_override = None
    base_settings = None
    if hours is not None:
        proxy, base_settings = _settings_with_window(hours)
        settings_override = proxy
        query = rest[len(second):].strip()
        manual_query = None
    else:
        query = rest
        manual_query = query

    mode_limits = {'official_only': 14, 'social_only': 5, 'osint_only': 3, 'analysis_only': 5}
    modes = ['official_only', 'social_only', 'osint_only', 'analysis_only']
    candidates = []
    state = {}
    for mode in modes:
        candidates.extend(
            scan_news(
                state,
                mode=mode,
                manual_query=manual_query,
                max_feeds=mode_limits.get(mode),
                active_config=scoped_config,
                settings_override=settings_override,
            )
        )
    candidates.sort(key=lambda x: (x.get('pattern_hits', 0), x.get('score', 0)), reverse=True)
    if not candidates:
        return "Bu profilin mevcut kaynaklarında belirtilen konuda sonuç bulunamadı."
    return _format_results(query, candidates)
