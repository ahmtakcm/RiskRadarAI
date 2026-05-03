from config.settings import settings
from core.logger import get_logger
from workflows.seed_news import seed_existing_news
from workflows.runner import run_forever


def run():
    logger = get_logger('bootstrap')
    logger.info('Bot başlatılıyor')
    state = settings.state_store.load_runtime_state()
    if not state.get('news_seeded'):
        seed_existing_news(state)
    run_forever(state)
