import json
from config.paths import PROFILES_DIR, RULES_DIR, USER_INPUTS_DIR
from config.settings import settings
from source_selectors.profile_policy import canonical_profile_name


def _load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def _profile_with_policy(profile: dict, policies: dict) -> dict:
    merged = dict(profile or {})
    policy_name = canonical_profile_name(merged.get('policy_profile') or merged.get('name') or '')
    policy = dict(policies.get(policy_name, {}) or {})
    policy.update(merged)
    if policy_name:
        policy['policy_profile'] = policy_name
    return policy


def _active_profile_names(default_profile_name: str, overrides: dict) -> list[str]:
    if overrides.get('enabled_profile'):
        return [str(overrides['enabled_profile'])]
    profile_state = _load_json(USER_INPUTS_DIR / 'profile_state.json', {})
    names = [str(x) for x in profile_state.get('active_profiles', []) if str(x).strip()]
    return names or [default_profile_name]


def load_active_config():
    profile_name = settings.active_profile
    overrides = _load_json(USER_INPUTS_DIR / 'overrides.json', {})
    profile_policies = _load_json(RULES_DIR / 'profile_policies.json', {})
    active_names = _active_profile_names(profile_name, overrides)

    if len(active_names) == 1:
        profile_name = active_names[0]
    elif 'tum_profiller' in active_names:
        profile_name = 'tum_profiller'
    else:
        profile_name = 'tum_profiller'

    profile = _load_json(PROFILES_DIR / f'{profile_name}.json', {})
    profile = _profile_with_policy(profile, profile_policies)

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
        'active_profile_names': active_names,
        'profile': profile,
        'profile_policies': profile_policies,
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
