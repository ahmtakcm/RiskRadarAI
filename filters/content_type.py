from urllib.parse import urlparse

DROP_URL_HINTS = (
    '/opinion/', '/analysis/', '/features/', '/feature/', '/video/', '/videos/',
    '/podcast/', '/interactive/', '/explainer/', '/longform/'
)
DROP_TITLE_HINTS = (
    'what we know', 'how shaky', 'why this matters', 'can ', 'opinion', 'analysis', 'explainer'
)
KEEP_URL_HINTS = ('/news/', '/business/', '/markets/', '/economy/', '/press/', '/releases/', '/media/press-releases/')
LIVE_URL_HINTS = ('/liveblog/', '/live/', '/live-news/', '/live-updates/')
LIVE_TITLE_HINTS = (
    'live updates', 'live update', 'live blog', 'liveblog', 'as it happened',
    'minute-by-minute', 'follow our live', 'follow live'
)


def classify_content_type(item: dict) -> str:
    url = str(item.get('link', '') or '').lower()
    title = str(item.get('title', '') or '').lower()
    desc = str(item.get('description', '') or '').lower()
    host = (urlparse(url).netloc or '').lower()
    blob = ' '.join([url, title, desc])

    if any(h in url for h in DROP_URL_HINTS):
        return 'drop'
    if any(h in title for h in DROP_TITLE_HINTS):
        return 'drop'
    if host and 'aljazeera.com' in host and '/video/' in url:
        return 'drop'
    if any(h in blob for h in LIVE_URL_HINTS) or any(h in blob for h in LIVE_TITLE_HINTS):
        return 'liveblog'
    if any(h in url for h in KEEP_URL_HINTS):
        return 'event_candidate'
    if any(word in title for word in ('live', 'breaking', 'announces', 'announced', 'agrees', 'approved', 'imposes', 'blockade', 'strikes', 'talks begin')):
        return 'event_candidate'
    if any(word in desc for word in ('announced', 'will begin', 'prices jumped', 'rose above', 'began', 'confirmed', 'said it would')):
        return 'event_candidate'
    return 'general_news'


def should_drop_from_alerting(item: dict) -> bool:
    return classify_content_type(item) == 'drop'
