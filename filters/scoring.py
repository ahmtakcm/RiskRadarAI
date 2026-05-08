from __future__ import annotations


OSINT_HIGH_RISK_TERMS = [
    'hormuz',
    'strait of hormuz',
    'iran',
    'centcom',
    'tanker',
    'blockade',
    'gulf of oman',
    'persian gulf',
    'missile',
    'attack',
    'strike',
    'warship',
    'oil',
    'navy',
    'naval',
    'crude',
    'sanction',
    'sanctions',
]


def news_text(item):
    return f"{item.get('title', '')} {item.get('description', '')} {item.get('article_text', '')}".lower()


def _is_osint_item(item: dict) -> bool:
    if item.get('scan_mode') == 'osint_only':
        return True
    source_file = str(item.get('source_file', '') or '')
    return source_file.endswith('osint_feeds.json')


def _count_hits(terms, text: str) -> int:
    seen = set()
    for term in terms or []:
        term = str(term or '').strip().lower()
        if term and term in text:
            seen.add(term)
    return len(seen)


def get_risk_score(item, keywords: dict):
    text = news_text(item)
    primary = keywords.get('primary_terms', [])
    secondary = keywords.get('secondary_terms', [])
    patterns = keywords.get('high_risk_patterns', [])
    primary_hits = _count_hits(primary, text)
    secondary_hits = _count_hits(secondary, text)
    pattern_hits = sum(1 for pattern in patterns if all(str(p).lower() in text for p in pattern))
    score = (primary_hits * 3) + secondary_hits + (pattern_hits * 5)

    if _is_osint_item(item):
        osint_hits = _count_hits(OSINT_HIGH_RISK_TERMS, text)
        if osint_hits:
            score += osint_hits * 8
        if osint_hits >= 2:
            score += 6
        if osint_hits >= 4:
            score += 8

    return score, primary_hits, secondary_hits, pattern_hits
