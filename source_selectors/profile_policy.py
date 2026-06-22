from __future__ import annotations

from filters.scoring import get_risk_score

PROFILE_ALIASES = {
    'haber': 'dunya',
    'resmi_kritik': 'resmi_aciklamalar',
}

TOPIC_PROFILE_ORDER = [
    'resmi_aciklamalar',
    'ekonomi',
    'saglik',
    'dunya',
    'turkiye',
    'yerel',
    'osint',
    'analiz',
]


def canonical_profile_name(name: str) -> str:
    raw = str(name or '').strip()
    return PROFILE_ALIASES.get(raw, raw)


def _keyword_data(active_config: dict, policy: dict) -> dict:
    keyword_sets = active_config.get('filters', {}).get('keyword_sets', {})
    data = dict(keyword_sets.get(policy.get('keyword_set', ''), {}) or {})
    include = list(data.get('primary_terms', []) or []) + list(data.get('secondary_terms', []) or [])
    for term in policy.get('keywords_include', []) or []:
        if term not in include:
            include.append(term)
    data['primary_terms'] = include
    data.setdefault('secondary_terms', [])
    data.setdefault('high_risk_patterns', [])
    return data


def active_topic_policies(active_config: dict) -> list[dict]:
    policies = active_config.get('profile_policies', {}) or {}
    active_names = active_config.get('active_profile_names') or [active_config.get('profile_name')]
    canonical = [canonical_profile_name(name) for name in active_names if name]

    if not canonical or 'tum_profiller' in canonical:
        names = policies.get('tum_profiller', {}).get('topic_profiles') or TOPIC_PROFILE_ORDER
    else:
        names = canonical

    selected = []
    seen = set()
    for name in names:
        key = canonical_profile_name(name)
        if key in seen or key == 'tum_profiller':
            continue
        policy = dict(policies.get(key, {}) or {})
        if not policy:
            continue
        policy.setdefault('name', key)
        policy.setdefault('policy_profile', key)
        policy.setdefault('matching_mode', 'keyword')
        policy.setdefault('ai_matching_enabled', False)
        selected.append(policy)
        seen.add(key)
    return selected


def profile_keywords(active_config: dict, policy: dict) -> dict:
    return _keyword_data(active_config, policy)


def evaluate_item_for_profile(item: dict, active_config: dict, policy: dict) -> dict:
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    excludes = [str(x).lower() for x in policy.get('keywords_exclude', []) or [] if str(x).strip()]
    if any(term in text for term in excludes):
        return {'matched': False, 'score': 0, 'keyword_hits': [], 'topic_tag_hits': [], 'reason': 'excluded_keyword'}

    keywords = _keyword_data(active_config, policy)
    raw_score, primary_hits, secondary_hits, pattern_hits = get_risk_score(item, keywords)
    debug_score = min(100, raw_score * 10)

    include_terms = [str(x).lower() for x in policy.get('keywords_include', []) or [] if str(x).strip()]
    keyword_hits = sorted({term for term in include_terms if term in text})

    source_tags = {str(x).lower() for x in item.get('source_tags', []) or []} - {'official'}
    topic_tags = {str(x).lower() for x in policy.get('topic_tags', []) or []} - {'official'}
    tag_hits = sorted(source_tags & topic_tags)

    matched = bool(
        pattern_hits
        or keyword_hits
        or primary_hits
        or secondary_hits
        or tag_hits
    )
    if policy.get('include_shared_official_sources') and item.get('applies_to_all_profiles') and tag_hits:
        matched = True

    return {
        'matched': matched,
        'debug_score': debug_score,
        'keyword_hits': keyword_hits,
        'topic_tag_hits': tag_hits,
        'primary_hits': primary_hits,
        'secondary_hits': secondary_hits,
        'pattern_hits': pattern_hits,
        'notify_policy': policy.get('notify_policy', ''),
        'matching_mode': policy.get('matching_mode', 'keyword'),
        'ai_matching_enabled': bool(policy.get('ai_matching_enabled', False)),
    }


def evaluate_item_across_active_profiles(item: dict, active_config: dict) -> list[dict]:
    matches = []
    for policy in active_topic_policies(active_config):
        if item.get('applies_to_all_profiles') and not policy.get('include_shared_official_sources', False):
            continue
        result = evaluate_item_for_profile(item, active_config, policy)
        if result.get('matched'):
            result['profile'] = policy.get('name') or policy.get('policy_profile')
            matches.append(result)
    return matches
