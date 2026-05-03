def _merge_keyword_sets(keyword_sets: dict, names: list[str]) -> dict:
    merged = {'primary_terms': [], 'secondary_terms': [], 'high_risk_patterns': []}
    for name in names:
        data = keyword_sets.get(name, {}) or {}
        for key in ('primary_terms', 'secondary_terms'):
            for term in data.get(key, []) or []:
                if term not in merged[key]:
                    merged[key].append(term)
        for pattern in data.get('high_risk_patterns', []) or []:
            if pattern not in merged['high_risk_patterns']:
                merged['high_risk_patterns'].append(pattern)
    return merged


def select_keywords(active_config: dict):
    profile = active_config['profile']
    keyword_sets = active_config['filters'].get('keyword_sets', {})

    selected = {}
    multi = [name for name in profile.get('keyword_sets', []) if name]
    if multi:
        selected = _merge_keyword_sets(keyword_sets, multi)
    else:
        keyword_set_name = profile.get('keyword_set', 'geopolitik')
        selected = (keyword_sets.get(keyword_set_name, {}) or {}).copy()

    custom = active_config.get('custom_keywords', {})
    if custom:
        for key in ('primary_terms', 'secondary_terms', 'high_risk_patterns'):
            if custom.get(key):
                selected[key] = custom[key]
    return selected
