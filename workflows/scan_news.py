from fetchers.feed_fetcher import fetch_feed_items
from source_selectors.profile_loader import load_active_config
from source_selectors.feed_selector import select_feeds
from source_selectors.keyword_selector import select_keywords
from source_selectors.profile_policy import evaluate_item_across_active_profiles, profile_keywords
from filters.relevance import is_relevant_news
from filters.scoring import get_risk_score
from filters.query_aliases import expand_query_terms
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
        'notify_policy': item.get('notify_policy', ''),
        'confirmation_required': item.get('confirmation_required', False),
        'relay_label': item.get('relay_label', ''),
    }


def scan_news(
    state: dict,
    mode: str = 'all',
    manual_query: str | None = None,
    max_feeds: int | None = None,
    *,
    active_config: dict | None = None,
    settings_override=None,
):
    active_config = active_config or load_active_config()
    runtime_settings = settings_override or settings
    feeds = select_feeds(active_config, mode=mode)
    if max_feeds is not None:
        feeds = feeds[:max(0, int(max_feeds))]
    keywords = select_keywords(active_config)
    if manual_query:
        manual_text = str(manual_query).strip().lower()
        query_terms = expand_query_terms(manual_text)
        keywords = dict(keywords)
        keywords['primary_terms'] = list(keywords.get('primary_terms', [])) + query_terms
    social_rule_name = active_config['profile'].get('social_rule_set', 'strict_geopolitics')
    social_rule = active_config['social_rules'].get(social_rule_name, {})
    min_score = 0 if manual_query else int(active_config['profile'].get('min_score', 9))
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
                    'source_file',
                    'applies_to_all_profiles',
                    'source_tags',
                    'matching_mode',
                    'ai_matching_enabled',
                    'keywords_include',
                    'keywords_exclude',
                    'topic_tags',
                    'notify_policy',
                    'confirmation_required',
                    'relay_label',
                ):
                    if key not in item or item.get(key) in ('', None, [], False):
                        if raw_item.get(key) is not None:
                            item[key] = raw_item.get(key)

                item['scan_mode'] = mode
                freshness = evaluate_item_freshness(item, mode, runtime_settings)
                item.update(freshness)
                if freshness.get('stale_overridden'):
                    logger.info('Notification stale override | source=%s | mode=%s | age_minutes=%s | freshness_window=%s', feed.get('name'), mode, freshness.get('age_minutes'), freshness.get('max_age_minutes'))
                if freshness.get('is_stale'):
                    logger.info('Notification drop | source=%s | reason=stale | mode=%s | age_minutes=%s | freshness_window=%s', feed.get('name'), mode, freshness.get('age_minutes'), freshness.get('max_age_minutes'))
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
                    logger.info('Notification drop | source=%s | reason=not_relevant | mode=%s | content_class=%s', feed.get('name'), mode, item.get('content_class'))
                    continue

                if mode == 'official_only' and item.get('applies_to_all_profiles'):
                    profile_matches = evaluate_item_across_active_profiles(item, active_config)
                    if not profile_matches and not manual_query:
                        logger.info('Notification drop | source=%s | reason=not_relevant | mode=%s | policy=shared_official_profile_match', feed.get('name'), mode)
                        continue
                    item['triggered_profiles'] = [m['profile'] for m in profile_matches]
                    item['profile_policy_matches'] = profile_matches
                    if profile_matches:
                        top_match = max(profile_matches, key=lambda x: x.get('score', 0))
                        item['matched_profile'] = top_match.get('profile')
                        item['profile_match_score'] = top_match.get('score', 0)
                        if top_match.get('notify_policy'):
                            item['profile_notify_policy'] = top_match.get('notify_policy')

                if manual_query:
                    text_blob = f"{item.get('title', '')} {item.get('description', '')}".lower()
                    q_terms = expand_query_terms(str(manual_query).strip().lower())
                    if q_terms and not any(term in text_blob for term in q_terms):
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
                if not force_keep and item.get('is_official_routine'):
                    logger.info('Notification drop | source=%s | reason=routine_suppressed | mode=%s', feed.get('name'), mode)
                    continue

                pre_score, _, _, pre_pattern_hits = get_risk_score(item, keywords)
                item['score'] = pre_score
                item['pattern_hits'] = pre_pattern_hits

                if not force_keep and not manual_query and not is_relevant_news(item, keywords, social_rule, min_score):
                    logger.info('Notification drop | source=%s | reason=not_relevant | mode=%s | score=%s | pattern_hits=%s', feed.get('name'), mode, item.get('score', ''), item.get('pattern_hits', ''))
                    continue

                if mode == 'official_only' and item.get('matched_profile'):
                    policy = active_config.get('profile_policies', {}).get(item.get('matched_profile'), {})
                    score, _, _, pattern_hits = get_risk_score(item, profile_keywords(active_config, policy))
                else:
                    score, _, _, pattern_hits = get_risk_score(item, keywords)
                item['score'] = score
                item['pattern_hits'] = pattern_hits
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
