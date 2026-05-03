import json
from config.paths import PROFILES_DIR, RULES_DIR, USER_INPUTS_DIR
from config.settings import settings


def _load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def load_active_config():
    profile_name = settings.active_profile
    overrides = _load_json(USER_INPUTS_DIR / 'overrides.json', {})
    if overrides.get('enabled_profile'):
        profile_name = overrides['enabled_profile']

    profile = _load_json(PROFILES_DIR / f'{profile_name}.json', {})
    feeds = _load_json(RULES_DIR / 'feeds.json', [])
    social_feeds = _load_json(RULES_DIR / 'social_feeds.json', [])
    osint_feeds = _load_json(RULES_DIR / 'osint_feeds.json', [])
    analysis_feeds = _load_json(RULES_DIR / 'analysis_feeds.json', [])
    filters = _load_json(RULES_DIR / 'filters.json', {})
    social_rules = _load_json(RULES_DIR / 'social_rules.json', {})
    calendar_watch = _load_json(RULES_DIR / 'calendar_watch.json', {})
    verification_rules = _load_json(RULES_DIR / 'verification_rules.json', {})
    social_mirrors = _load_json(RULES_DIR / 'social_mirrors.json', {})
    ai_prompts = _load_json(RULES_DIR / 'ai_prompts.json', {})
    official_entities = _load_json(RULES_DIR / 'official_entities.json', {})
    custom_keywords = _load_json(USER_INPUTS_DIR / 'custom_keywords.json', {})
    blocked_sources = set(_load_json(USER_INPUTS_DIR / 'blocked_sources.json', {}).get('sources', []))

    return {
        'profile_name': profile_name,
        'profile': profile,
        'feeds': feeds,
        'social_feeds': social_feeds,
        'osint_feeds': osint_feeds,
        'analysis_feeds': analysis_feeds,
        'filters': filters,
        'social_rules': social_rules,
        'calendar_watch': calendar_watch,
        'verification_rules': verification_rules,
        'social_mirrors': social_mirrors,
        'ai_prompts': ai_prompts,
        'official_entities': official_entities,
        'custom_keywords': custom_keywords,
        'blocked_sources': blocked_sources,
        'overrides': overrides,
    }
