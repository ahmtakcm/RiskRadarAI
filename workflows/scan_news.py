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
from core.news_log import build_log_entry, upsert_news_log_entry

logger = get_logger('scan_news')

SOCIAL_STATUS_HOSTS = {'nitter.net', 'twitt.re', 'xcancel.com', 'rss.xcancel.com', 'x.com', 'twitter.com'}

OFFICIAL_CRITICAL_TERMS = {
    'iran', 'gaza', 'hezbollah', 'hizbullah', 'ukraine', 'kiev', 'kyiv',
    'russia', 'nato', 'hormuz', 'sanction', 'sanctions', 'ceasefire',
    'strike', 'strikes', 'attack', 'warning', 'military', 'missile',
    'operation', 'operations', 'advisory', 'incident', 'security incident',
    'treasury sanctions', 'state department statement', 'centcom operation',
    'ukmto advisory', 'interest', 'inflation', 'rate decision', 'policy rate',
    'fomc', 'ecb', 'tcmb',
}

OFFICIAL_LOW_VALUE_TERMS = {
    'memorial day', 'ceremony', 'routine visit', 'congratulations',
    'holiday message', 'health awareness', 'generic health awareness',
    'birthday', 'anniversary', 'greeting', 'courtesy', 'protocol',
}


def _inc(counter: dict[str, int], key: str, amount: int = 1):
    counter[key] = counter.get(key, 0) + amount


def _log_skip_counts(mode: str, counts: dict[str, int]):
    for reason, count in sorted(counts.items()):
        logger.info('skip_reason_count | mode=%s | reason=%s | count=%s', mode, reason, count)


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
        if host in SOCIAL_STATUS_HOSTS:
            match = re.search(r'/status/(\d+)', path)
            if match:
                return f'social-status:{match.group(1)}'
        if path:
            return f'{host}:{path}'
    if title:
        return f'title:{title[:180]}'
    return text_hash(str(item))


def _has_digest_text(item: dict) -> bool:
    return bool(
        str(item.get('title', '') or '').strip()
        or str(item.get('description', '') or '').strip()
        or str(item.get('link', '') or '').strip()
    )


def _record_digest_only_drop(state: dict, item: dict, story_key: str, reason: str, runtime_settings, *, force: bool = False):
    age = item.get('age_minutes')
    try:
        age_int = int(age)
    except (TypeError, ValueError):
        return False

    max_age = int(getattr(runtime_settings, 'digest_max_age_minutes', 720))
    if (age_int > max_age and not force) or not _has_digest_text(item):
        return False

    entry = build_log_entry(
        item,
        f'DIGEST_{story_key}',
        alert_sent=False,
        drop_reason=reason,
        translated_text=str(item.get('description', '') or '').strip(),
        delivery_mode='digest',
        meta={
            'origin': item.get('scan_mode', ''),
            'digest_only_reason': reason,
            'story_key': story_key,
            'age_minutes': age_int,
            'digest_max_age_minutes': max_age,
        },
    )
    upsert_news_log_entry(state, entry)
    return True


def _is_official_source(item: dict) -> bool:
    return bool(str(item.get('official_class', '') or '').startswith('official_') or item.get('is_official_source'))


def _is_official_critical_item(item: dict) -> bool:
    if not _is_official_source(item):
        return False
    text = ' '.join([
        str(item.get('source_name', '') or ''),
        str(item.get('title', '') or ''),
        str(item.get('description', '') or ''),
        str(item.get('article_text', '') or ''),
    ]).lower()
    if any(term in text for term in OFFICIAL_LOW_VALUE_TERMS):
        return False
    return any(term in text for term in OFFICIAL_CRITICAL_TERMS)


def _apply_official_critical_keep(item: dict) -> bool:
    if not _is_official_critical_item(item):
        return False
    item['official_critical_relevance_kept'] = True
    if item.get('is_official_routine'):
        item['is_official_routine'] = False
        item['routine_hits'] = []
    return True


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
    scan_digest_story_hashes = set()
    candidates = []
    parsed_item_count = 0
    duplicate_drop_count = 0
    skip_counts: dict[str, int] = {}

    logger.info(
        'scan_started | mode=%s | feed_count=%s | manual_query=%s | max_feeds=%s',
        mode,
        len(feeds),
        bool(manual_query),
        max_feeds if max_feeds is not None else '',
    )

    for feed in feeds:
        stale_count = 0
        stale_limit = None
        stale_min_age = None
        stale_sample = ''
        try:
            items = fetch_feed_items(feed)
            parsed_item_count += len(items)
            logger.info(
                'source_fetch_count | mode=%s | source=%s | count=%s',
                mode,
                feed.get('name', ''),
                len(items),
            )
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
                h = text_hash(item['title'] + '|' + item['link'] + '|' + item['source_name'])
                story_key = _canonical_story_key(item)
                freshness = evaluate_item_freshness(item, mode, runtime_settings)
                item.update(freshness)
                if freshness.get('stale_overridden'):
                    logger.info('Notification stale override | source=%s | mode=%s | age_minutes=%s | freshness_window=%s', feed.get('name'), mode, freshness.get('age_minutes'), freshness.get('max_age_minutes'))
                if freshness.get('is_stale'):
                    stale_reason = 'official_critical_digest_kept' if _is_official_critical_item(item) else 'stale'
                    logger.info('Notification drop | source=%s | reason=%s | mode=%s | age_minutes=%s | freshness_window=%s', feed.get('name'), stale_reason, mode, freshness.get('age_minutes'), freshness.get('max_age_minutes'))
                    _inc(skip_counts, stale_reason)
                    stale_count += 1
                    stale_limit = freshness.get('max_age_minutes')
                    age = int(freshness.get('age_minutes') or 0)
                    stale_min_age = age if stale_min_age is None else min(stale_min_age, age)
                    if not stale_sample:
                        stale_sample = item.get('title', '')[:90]
                    if (
                        h not in seen_hashes
                        and story_key not in seen_story_hashes
                        and story_key not in scan_digest_story_hashes
                    ):
                        if _record_digest_only_drop(state, item, story_key, stale_reason, runtime_settings, force=stale_reason == 'official_critical_digest_kept'):
                            _inc(skip_counts, 'digest_only_stale_recorded')
                        scan_digest_story_hashes.add(story_key)
                    continue

                item['content_class'] = classify_content_type(item)
                official_meta = annotate_official_context(item, active_config)
                item.update(official_meta)
                official_critical_keep = _apply_official_critical_keep(item)

                if should_drop_from_alerting(item) and not item.get('is_official_source'):
                    logger.info('Notification drop | source=%s | reason=not_relevant | mode=%s | content_class=%s', feed.get('name'), mode, item.get('content_class'))
                    _inc(skip_counts, 'content_type')
                    continue

                if mode == 'official_only' and item.get('applies_to_all_profiles'):
                    profile_matches = evaluate_item_across_active_profiles(item, active_config)
                    if not profile_matches and not manual_query:
                        if official_critical_keep:
                            logger.info('Notification keep | source=%s | reason=official_critical_relevance_kept | mode=%s | policy=shared_official_profile_match', feed.get('name'), mode)
                            _inc(skip_counts, 'official_critical_relevance_kept')
                        else:
                            logger.info('Notification drop | source=%s | reason=not_relevant | mode=%s | policy=shared_official_profile_match', feed.get('name'), mode)
                            _inc(skip_counts, 'shared_official_profile_match')
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
                        _inc(skip_counts, 'manual_query_mismatch')
                        continue

                if h in seen_hashes or story_key in seen_story_hashes or story_key in scan_story_hashes:
                    duplicate_drop_count += 1
                    continue

                force_keep = bool(
                    item.get('official_red_alert_source')
                    and not item.get('is_official_routine')
                    and (item.get('official_keyword_hits') or item.get('official_entity_hits'))
                )
                if not force_keep and item.get('is_official_routine'):
                    logger.info('Notification drop | source=%s | reason=routine_suppressed | mode=%s', feed.get('name'), mode)
                    _inc(skip_counts, 'routine_suppressed')
                    continue

                pre_score, _, _, pre_pattern_hits = get_risk_score(item, keywords)
                item['score'] = pre_score
                item['pattern_hits'] = pre_pattern_hits

                if not force_keep and not manual_query and not is_relevant_news(item, keywords, social_rule, min_score):
                    if official_critical_keep:
                        logger.info('Notification keep | source=%s | reason=official_critical_relevance_kept | mode=%s | score=%s | pattern_hits=%s', feed.get('name'), mode, item.get('score', ''), item.get('pattern_hits', ''))
                        _inc(skip_counts, 'official_critical_relevance_kept')
                    else:
                        logger.info('Notification drop | source=%s | reason=not_relevant | mode=%s | score=%s | pattern_hits=%s', feed.get('name'), mode, item.get('score', ''), item.get('pattern_hits', ''))
                        _inc(skip_counts, 'not_relevant')
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
                elif official_critical_keep:
                    score = max(score, 18)
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
            _inc(skip_counts, 'fetch_error')

    candidates.sort(
        key=lambda x: (
            x['item'].get('official_red_alert_source', False),
            x['pattern_hits'],
            x['score']
        ),
        reverse=True
    )
    logger.info('parsed_item_count | mode=%s | count=%s', mode, parsed_item_count)
    logger.info('candidate_count | mode=%s | count=%s', mode, len(candidates))
    logger.info('duplicate_drop_count | mode=%s | count=%s', mode, duplicate_drop_count)
    _log_skip_counts(mode, skip_counts)
    logger.info(
        'scan_finished | mode=%s | parsed_item_count=%s | candidate_count=%s | duplicate_drop_count=%s | skip_reason_count=%s',
        mode,
        parsed_item_count,
        len(candidates),
        duplicate_drop_count,
        sum(skip_counts.values()),
    )
    return candidates
