from fetchers.feed_fetcher import fetch_feed_items
from source_selectors.profile_loader import load_active_config
from source_selectors.feed_selector import select_feeds
from source_selectors.keyword_selector import select_keywords
from filters.relevance import is_relevant_news
from filters.scoring import get_risk_score
from filters.freshness import evaluate_item_freshness
from filters.content_type import should_drop_from_alerting, classify_content_type
from filters.official_sources import annotate_official_context
from config.settings import settings
from urllib.parse import urlsplit
import re

from core.hashing import text_hash
from core.logger import get_logger
from core.matching import build_topic_tokens

logger = get_logger('scan_news')


def _normalized_title(title: str) -> str:
    text = re.sub(r'\s+', ' ', str(title or '').strip().lower())
    return re.sub(r'[^a-z0-9çğıöşü\s-]+', '', text)


def _canonical_story_key(item: dict) -> str:
    link = str(item.get('link', '') or '').strip()
    title = _normalized_title(item.get('title', ''))
    if link:
        split = urlsplit(link)
        host = split.netloc.lower().replace('www.', '')
        path = split.path.rstrip('/')
        if 'jpost.com' in host:
            match = re.search(r'/article-(\d+)', path)
            if match:
                return f'jpost:article:{match.group(1)}'
        if host in {'nitter.net', 'twitt.re'}:
            match = re.search(r'/status/(\d+)', path)
            if match:
                return f'{host}:status:{match.group(1)}'
        if path:
            return f'{host}:{path}'
    if title:
        return f'title:{title[:180]}'
    return text_hash(str(item))



def normalize(item):
    return {
        'title': item.get('title', '').strip(),
        'link': item.get('link', '').strip(),
        'pub_date': item.get('pub_date', '').strip(),
        'description': item.get('description', '').strip(),
        'source_name': item.get('source_name', '').strip(),
        'source_kind': item.get('source_kind', '').strip(),
        'official_class': item.get('official_class', ''),
        'official_country': item.get('official_country', ''),
        'official_red_alert': item.get('official_red_alert', False),
        'source_class': item.get('source_class', ''),
        'source_country': item.get('source_country', ''),
        'source_family': item.get('source_family', ''),
        'stale_minutes': item.get('stale_minutes'),
        'region_tags': item.get('region_tags', []),
        'verification_group': item.get('verification_group', ''),
        'access_risk': item.get('access_risk', ''),
        'notes': item.get('notes', ''),
    }


def scan_news(state: dict, mode: str = 'all'):
    active_config = load_active_config()
    feeds = select_feeds(active_config, mode=mode)
    keywords = select_keywords(active_config)
    social_rule_name = active_config['profile'].get('social_rule_set', 'strict_geopolitics')
    social_rule = active_config['social_rules'].get(social_rule_name, {})
    min_score = int(active_config['profile'].get('min_score', 9))
    tracked_terms = list(keywords.get('primary_terms', [])) + list(keywords.get('secondary_terms', [])) + list(active_config.get('verification_rules', {}).get('high_priority_terms', [])) + list(active_config.get('official_entities', {}).get('iran_official_entities', []))

    seen_hashes = set(state.get('seen_news_hashes', []))
    seen_story_hashes = set(state.get('seen_story_hashes', []))
    scan_story_hashes = set()
    candidates = []

    for feed in feeds:
        stale_count = 0
        stale_limit = None
        stale_min_age = None
        stale_sample = ''
        try:
            items = fetch_feed_items(feed)
            for raw_item in items[:20]:
                item = normalize(raw_item)
                # inherit feed meta from feed definition if parser didn't add it
                for key in (
                    'official_class',
                    'official_country',
                    'official_red_alert',
                    'source_class',
                    'source_country',
                    'source_family',
                    'stale_minutes',
                    'region_tags',
                    'verification_group',
                    'access_risk',
                    'notes',
                ):
                    if key not in item or item.get(key) in ('', None, [], False):
                        if raw_item.get(key) is not None:
                            item[key] = raw_item.get(key)

                freshness = evaluate_item_freshness(item, mode, settings)
                item.update(freshness)
                if freshness.get('is_stale'):
                    stale_count += 1
                    stale_limit = freshness.get('max_age_minutes')
                    age = int(freshness.get('age_minutes') or 0)
                    stale_min_age = age if stale_min_age is None else min(stale_min_age, age)
                    if not stale_sample:
                        stale_sample = item.get('title', '')[:90]
                    continue

                item['content_class'] = classify_content_type(item)
                official_meta = annotate_official_context(item, active_config)
                item.update(official_meta)

                if should_drop_from_alerting(item) and not item.get('is_official_source'):
                    continue

                h = text_hash(item['title'] + '|' + item['link'] + '|' + item['source_name'])
                story_key = _canonical_story_key(item)
                if h in seen_hashes or story_key in seen_story_hashes or story_key in scan_story_hashes:
                    continue

                force_keep = bool(
                    item.get('official_red_alert_source')
                    and not item.get('is_official_routine')
                    and (item.get('official_keyword_hits') or item.get('official_entity_hits'))
                )
                if not force_keep and not is_relevant_news(item, keywords, social_rule, min_score):
                    continue

                score, _, _, pattern_hits = get_risk_score(item, keywords)
                if force_keep:
                    score = max(score, 25)
                elif item.get('is_official_source') and not item.get('is_official_routine') and (item.get('official_keyword_hits') or item.get('official_entity_hits')):
                    score = max(score, 18)

                topic_tokens = sorted(build_topic_tokens(item, tracked_terms + item.get('official_keyword_hits', []) + item.get('official_entity_hits', [])))
                candidates.append({
                    'hash': h,
                    'story_key': story_key,
                    'score': score,
                    'pattern_hits': pattern_hits,
                    'item': item,
                    'topic_tokens': topic_tokens,
                    'scan_mode': mode,
                })
                scan_story_hashes.add(story_key)

            if stale_count:
                logger.info(
                    'Stale içerik özeti (%s): %s adet elendi | en yeni yaş=%s dk limit=%s dk | örnek=%s',
                    feed['name'],
                    stale_count,
                    stale_min_age or 0,
                    stale_limit or '-',
                    stale_sample
                )
        except Exception as exc:
            logger.warning('Haber feed hatası (%s): %s', feed['name'], exc)

    candidates.sort(
        key=lambda x: (
            x['item'].get('official_red_alert_source', False),
            x['pattern_hits'],
            x['score']
        ),
        reverse=True
    )
    return candidates
