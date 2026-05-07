def _is_social(feed: dict) -> bool:
    return feed.get('kind') == 'rss_social'


def _is_shared_official(feed: dict) -> bool:
    official_class = str(feed.get('official_class', '') or '').lower()
    source_class = str(feed.get('source_class', '') or '').lower()
    return bool(feed.get('applies_to_all_profiles')) or official_class.startswith('official_') or 'official' in source_class


def _allow_feed(feed: dict, enabled_names: set[str], blocked: set[str], *, shared_official: bool = False) -> bool:
    if not feed.get('enabled', True):
        return False
    if feed['name'] in blocked:
        return False
    if shared_official:
        return _is_shared_official(feed)
    if enabled_names and feed['name'] not in enabled_names and not _is_social(feed):
        return False
    return True


def _profile_enabled(active_config: dict, key: str) -> bool:
    profile = active_config.get('profile', {})
    if profile.get(key, False):
        return True
    names = {str(x) for x in active_config.get('active_profile_names', [])}
    if key == 'enabled_osint' and 'osint' in names:
        return True
    if key == 'enabled_analysis' and 'analiz' in names:
        return True
    if 'tum_profiller' in names:
        return True
    return False


def select_feeds(active_config: dict, mode: str = 'all'):
    enabled_names = set(active_config.get('profile', {}).get('enabled_feeds', []))
    blocked = active_config.get('blocked_sources', set())
    selected = []
    seen = set()

    def append_group(feeds, source_file: str, *, shared_official: bool = False, exclude_official: bool = False):
        for raw in feeds:
            if exclude_official and _is_shared_official(raw):
                continue
            if not _allow_feed(raw, enabled_names, blocked, shared_official=shared_official):
                continue
            if raw.get('name') in seen:
                continue
            feed = dict(raw)
            feed['source_file'] = source_file
            selected.append(feed)
            seen.add(feed.get('name'))

    if mode == 'official_only':
        append_group(active_config.get('feeds', []), 'rules/feeds.json', shared_official=True)
        append_group(active_config.get('social_feeds', []), 'rules/social_feeds.json', shared_official=True)
        return selected
    if mode == 'social_only':
        if _profile_enabled(active_config, 'enabled_social'):
            append_group(active_config.get('social_feeds', []), 'rules/social_feeds.json', exclude_official=True)
        return selected
    if mode == 'osint_only':
        if _profile_enabled(active_config, 'enabled_osint'):
            append_group(active_config.get('osint_feeds', []), 'rules/osint_feeds.json')
        return selected
    if mode == 'analysis_only':
        if _profile_enabled(active_config, 'enabled_analysis'):
            append_group(active_config.get('analysis_feeds', []), 'rules/analysis_feeds.json')
        return selected

    append_group(active_config.get('feeds', []), 'rules/feeds.json', shared_official=True)
    append_group(active_config.get('social_feeds', []), 'rules/social_feeds.json', shared_official=True)
    if _profile_enabled(active_config, 'enabled_social'):
        append_group(active_config.get('social_feeds', []), 'rules/social_feeds.json', exclude_official=True)
    if _profile_enabled(active_config, 'enabled_osint'):
        append_group(active_config.get('osint_feeds', []), 'rules/osint_feeds.json')
    if _profile_enabled(active_config, 'enabled_analysis'):
        append_group(active_config.get('analysis_feeds', []), 'rules/analysis_feeds.json')
    return selected
