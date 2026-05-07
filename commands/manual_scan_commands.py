from __future__ import annotations

from workflows.scan_news import scan_news


MANUAL_COMMANDS = ('/ara', '/tara')


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
        lines.append(f"- {source} | skor={score}{suffix}")
        lines.append(f"  {title}")
        if item.get('link'):
            lines.append(f"  {item['link']}")
    return '\n'.join(lines)[:3800]


def handle_manual_scan_command(text: str) -> str | None:
    raw = (text or '').strip()
    if not raw.startswith(MANUAL_COMMANDS):
        return None
    cmd, _, query = raw.partition(' ')
    query = query.strip()
    if not query:
        return f"Aranacak ifade eksik. Örn: {cmd} hormuz"

    mode_limits = {'official_only': 14, 'social_only': 5, 'osint_only': 3, 'analysis_only': 5}
    modes = ['official_only'] if cmd == '/ara' else ['official_only', 'social_only', 'osint_only', 'analysis_only']
    candidates = []
    state = {}
    for mode in modes:
        candidates.extend(scan_news(state, mode=mode, manual_query=query, max_feeds=mode_limits.get(mode)))
    candidates.sort(key=lambda x: (x.get('pattern_hits', 0), x.get('score', 0)), reverse=True)
    return _format_results(query, candidates)
