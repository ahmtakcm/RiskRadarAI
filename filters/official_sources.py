from __future__ import annotations



def annotate_official_context(item: dict, active_config: dict) -> dict:
    rules = active_config.get('official_entities', {}) or {}
    source_name = str(item.get('source_name', '') or '')
    text = ' '.join([
        str(item.get('title', '') or ''),
        str(item.get('description', '') or ''),
        str(item.get('article_text', '') or ''),
    ]).lower()

    override_terms = [t.lower() for t in rules.get('official_keyword_override_terms', []) if t]
    red_sources = set(rules.get('official_sources_red_alert', []) or [])
    iran_entities = [t.lower() for t in rules.get('iran_official_entities', []) if t]
    trusted_secondary_sources = set(rules.get('trusted_secondary_sources', []) or [])
    routine_terms = [t.lower() for t in rules.get('official_routine_terms', []) if t]

    hard_alert_terms = {
        'blockade', 'abluka', 'strait of hormuz', 'hormuz', 'iranian ports',
        'mine clearance', 'strike', 'strikes', 'attack', 'missile',
        'sanction', 'sanctions', 'swift', 'oil', 'brent', 'wti',
        'ceasefire', 'centcom', 'shipping disruption', 'port closure',
        'maritime traffic', 'closure'
    }

    official_class = item.get('official_class', '') or ''
    is_official_source = bool(official_class) or source_name in red_sources
    trusted_media_source = source_name in trusted_secondary_sources
    official_red_alert_source = bool(item.get('official_red_alert')) or source_name in red_sources

    keyword_hits = sorted({t for t in override_terms if t in text})
    entity_hits = sorted({t for t in iran_entities if t in text})
    routine_hits = sorted({t for t in routine_terms if t in text})

    has_hard_alert = bool(set(keyword_hits) & hard_alert_terms) or bool(entity_hits)
    is_official_routine = bool(is_official_source and routine_hits and not has_hard_alert)

    if is_official_routine:
        official_red_alert_source = False

    return {
        'is_official_source': is_official_source,
        'trusted_media_source': trusted_media_source,
        'official_red_alert_source': official_red_alert_source,
        'official_keyword_hits': keyword_hits,
        'official_keyword_hits_raw': keyword_hits,
        'official_entity_hits': entity_hits,
        'routine_hits': routine_hits,
        'is_official_routine': is_official_routine,
    }
