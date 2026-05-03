def _is_social(feed: dict) -> bool:
    return feed.get('kind') == 'rss_social'


def _allow_feed(feed: dict, enabled_names: set[str], blocked: set[str]) -> bool:
    if not feed.get('enabled', True):
        return False
    if enabled_names and feed['name'] not in enabled_names and not _is_social(feed):
        return False
    if feed['name'] in blocked:
        return False
    return True


def select_feeds(active_config: dict, mode: str = 'all'):
    enabled_names = set(active_config['profile'].get('enabled_feeds', []))
    blocked = active_config['blocked_sources']
    selected = []

    def append_group(feeds):
        for feed in feeds:
            if _allow_feed(feed, enabled_names, blocked):
                selected.append(feed)

    if mode == 'official_only':
        append_group(active_config.get('feeds', []))
        return selected
    if mode == 'social_only':
        if active_config['profile'].get('enabled_social', False):
            append_group(active_config.get('social_feeds', []))
        return selected
    if mode == 'osint_only':
        if active_config['profile'].get('enabled_osint', False):
            append_group(active_config.get('osint_feeds', []))
        return selected
    if mode == 'analysis_only':
        if active_config['profile'].get('enabled_analysis', False):
            append_group(active_config.get('analysis_feeds', []))
        return selected

    append_group(active_config.get('feeds', []))
    if active_config['profile'].get('enabled_social', False):
        append_group(active_config.get('social_feeds', []))
    if active_config['profile'].get('enabled_osint', False):
        append_group(active_config.get('osint_feeds', []))
    if active_config['profile'].get('enabled_analysis', False):
        append_group(active_config.get('analysis_feeds', []))
    return selected
