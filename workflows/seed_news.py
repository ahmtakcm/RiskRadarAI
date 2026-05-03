from workflows.scan_news import _canonical_story_key
from core.hashing import text_hash
from core.logger import get_logger
from config.settings import settings
from fetchers.feed_fetcher import fetch_feed_items
from source_selectors.profile_loader import load_active_config
from source_selectors.feed_selector import select_feeds
from filters.freshness import evaluate_item_freshness

logger = get_logger('seed_news')


def normalize(item):
    return {
        'title': item.get('title', '').strip(),
        'link': item.get('link', '').strip(),
        'pub_date': item.get('pub_date', '').strip(),
        'description': item.get('description', '').strip(),
        'source_name': item.get('source_name', '').strip(),
        'source_kind': item.get('source_kind', '').strip(),
    }


def seed_existing_news(state: dict):
    active_config = load_active_config()
    seen_hashes = set(state.get('seen_news_hashes', []))
    seen_story_hashes = set(state.get('seen_story_hashes', []))
    mode_by_name = {
        'feeds': 'official_only',
        'social_feeds': 'social_only',
        'osint_feeds': 'osint_only',
        'analysis_feeds': 'analysis_only',
    }
    for group_name, mode in mode_by_name.items():
        feeds = select_feeds(active_config, mode=mode)
        for feed in feeds:
            try:
                for raw_item in fetch_feed_items(feed)[:20]:
                    item = normalize(raw_item)
                    if evaluate_item_freshness(item, mode, settings).get('is_stale'):
                        continue
                    seen_hashes.add(text_hash(item['title'] + '|' + item['link'] + '|' + item['source_name']))
                    seen_story_hashes.add(_canonical_story_key(item))
            except Exception as exc:
                logger.warning('İlk tohumlama hatası (%s): %s', feed['name'], exc)
    state['seen_news_hashes'] = list(seen_hashes)[-2000:]
    state['seen_story_hashes'] = list(seen_story_hashes)[-5000:]
    state['news_seeded'] = True
    settings.state_store.save_runtime_state(state)
    logger.info('İlk haber tohumlama tamamlandı')
