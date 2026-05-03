import os
from dataclasses import dataclass
from dotenv import load_dotenv
from config import defaults
from core.state import StateStore

load_dotenv()

@dataclass
class Settings:
    bot_token: str
    chat_id: str
    news_check_interval: int
    calendar_check_interval: int
    loop_sleep_seconds: int
    news_cooldown_seconds: int
    calendar_cooldown_seconds: int
    max_news_alerts_per_scan: int
    request_timeout: int
    http_retry_total: int
    http_backoff_factor: int
    active_profile: str
    log_level: str
    verification_window_minutes: int
    pending_social_ttl_minutes: int
    send_unverified_social_alerts: bool
    gemini_enabled: bool
    gemini_api_key: str
    gemini_model: str
    gemini_timeout: int
    gemini_min_score: int
    gemini_only_for_unverified: bool
    gemini_summary_enabled: bool
    gemini_matching_enabled: bool
    gemini_sdk_preferred: bool
    gemini_log_enabled: bool
    groq_enabled: bool
    groq_api_key: str
    groq_model: str
    groq_timeout: int
    ai_provider_primary: str
    ai_provider_secondary: str
    github_models_enabled: bool
    github_models_token: str
    github_models_model: str
    github_models_timeout: int
    github_models_cooldown_seconds: int
    drop_stale_items: bool
    social_max_age_minutes: int
    osint_max_age_minutes: int
    official_max_age_minutes: int
    news_max_age_minutes: int
    analysis_max_age_minutes: int
    show_source_time: bool
    social_fail_threshold: int
    social_cooldown_minutes: int
    social_health_log_interval_seconds: int
    full_article_fetch_enabled: bool
    full_article_min_text_length: int
    ai_summary_min_chars: int
    fallback_summary_min_chars: int
    drop_weak_summaries: bool
    url_type_filter_enabled: bool
    drop_analysis_pages: bool
    drop_video_pages: bool
    require_market_relevance: bool
    official_keyword_alerts: bool
    calendar_headsup_enabled: bool
    calendar_headsup_days: int
    state_store: StateStore


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f'{name} tanımlı değil')
    return value


def _to_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')

settings = Settings(
    bot_token=_required('BOT_TOKEN'),
    chat_id=_required('CHAT_ID'),
    news_check_interval=int(os.getenv('NEWS_CHECK_INTERVAL', defaults.DEFAULT_NEWS_CHECK_INTERVAL)),
    calendar_check_interval=int(os.getenv('CALENDAR_CHECK_INTERVAL', defaults.DEFAULT_CALENDAR_CHECK_INTERVAL)),
    loop_sleep_seconds=int(os.getenv('LOOP_SLEEP_SECONDS', defaults.DEFAULT_LOOP_SLEEP_SECONDS)),
    news_cooldown_seconds=int(os.getenv('NEWS_COOLDOWN_SECONDS', defaults.DEFAULT_NEWS_COOLDOWN_SECONDS)),
    calendar_cooldown_seconds=int(os.getenv('CALENDAR_COOLDOWN_SECONDS', defaults.DEFAULT_CALENDAR_COOLDOWN_SECONDS)),
    max_news_alerts_per_scan=int(os.getenv('MAX_NEWS_ALERTS_PER_SCAN', defaults.DEFAULT_MAX_NEWS_ALERTS_PER_SCAN)),
    request_timeout=int(os.getenv('REQUEST_TIMEOUT', '20')),
    http_retry_total=int(os.getenv('HTTP_RETRY_TOTAL', '3')),
    http_backoff_factor=int(os.getenv('HTTP_BACKOFF_FACTOR', '1')),
    active_profile=os.getenv('ACTIVE_PROFILE', defaults.DEFAULT_ENABLED_PROFILE),
    log_level=os.getenv('LOG_LEVEL', 'INFO').upper(),
    verification_window_minutes=int(os.getenv('VERIFICATION_WINDOW_MINUTES', defaults.DEFAULT_VERIFICATION_WINDOW_MINUTES)),
    pending_social_ttl_minutes=int(os.getenv('PENDING_SOCIAL_TTL_MINUTES', defaults.DEFAULT_PENDING_SOCIAL_TTL_MINUTES)),
    send_unverified_social_alerts=_to_bool('SEND_UNVERIFIED_SOCIAL_ALERTS', defaults.DEFAULT_SEND_UNVERIFIED_SOCIAL_ALERTS),
    gemini_enabled=_to_bool('GEMINI_ENABLED', defaults.DEFAULT_GEMINI_ENABLED),
    gemini_api_key=os.getenv('GEMINI_API_KEY', ''),
    gemini_model=os.getenv('GEMINI_MODEL', defaults.DEFAULT_GEMINI_MODEL),
    gemini_timeout=int(os.getenv('GEMINI_TIMEOUT', defaults.DEFAULT_GEMINI_TIMEOUT)),
    gemini_min_score=int(os.getenv('GEMINI_MIN_SCORE', defaults.DEFAULT_GEMINI_MIN_SCORE)),
    gemini_only_for_unverified=_to_bool('GEMINI_ONLY_FOR_UNVERIFIED', defaults.DEFAULT_GEMINI_ONLY_FOR_UNVERIFIED),
    gemini_summary_enabled=_to_bool('GEMINI_SUMMARY_ENABLED', defaults.DEFAULT_GEMINI_SUMMARY_ENABLED),
    gemini_matching_enabled=_to_bool('GEMINI_MATCHING_ENABLED', defaults.DEFAULT_GEMINI_MATCHING_ENABLED),
    gemini_sdk_preferred=_to_bool('GEMINI_SDK_PREFERRED', defaults.DEFAULT_GEMINI_SDK_PREFERRED),
    gemini_log_enabled=_to_bool('GEMINI_LOG_ENABLED', defaults.DEFAULT_GEMINI_LOG_ENABLED),
    groq_enabled=_to_bool('GROQ_ENABLED', defaults.DEFAULT_GROQ_ENABLED),
    groq_api_key=os.getenv('GROQ_API_KEY', ''),
    groq_model=os.getenv('GROQ_MODEL', defaults.DEFAULT_GROQ_MODEL),
    groq_timeout=int(os.getenv('GROQ_TIMEOUT', defaults.DEFAULT_GROQ_TIMEOUT)),
    ai_provider_primary=os.getenv('AI_PROVIDER_PRIMARY', defaults.DEFAULT_AI_PROVIDER_PRIMARY).strip().lower(),
    ai_provider_secondary=os.getenv('AI_PROVIDER_SECONDARY', defaults.DEFAULT_AI_PROVIDER_SECONDARY).strip().lower(),
    github_models_enabled=_to_bool('GITHUB_MODELS_ENABLED', defaults.DEFAULT_GITHUB_MODELS_ENABLED),
    github_models_token=os.getenv('GITHUB_MODELS_TOKEN', ''),
    github_models_model=os.getenv('GITHUB_MODELS_MODEL', defaults.DEFAULT_GITHUB_MODELS_MODEL),
    github_models_timeout=int(os.getenv('GITHUB_MODELS_TIMEOUT', defaults.DEFAULT_GITHUB_MODELS_TIMEOUT)),
    github_models_cooldown_seconds=int(os.getenv('GITHUB_MODELS_COOLDOWN_SECONDS', defaults.DEFAULT_GITHUB_MODELS_COOLDOWN_SECONDS)),
    drop_stale_items=_to_bool('DROP_STALE_ITEMS', defaults.DEFAULT_DROP_STALE_ITEMS),
    social_max_age_minutes=int(os.getenv('SOCIAL_MAX_AGE_MINUTES', defaults.DEFAULT_SOCIAL_MAX_AGE_MINUTES)),
    osint_max_age_minutes=int(os.getenv('OSINT_MAX_AGE_MINUTES', defaults.DEFAULT_OSINT_MAX_AGE_MINUTES)),
    official_max_age_minutes=int(os.getenv('OFFICIAL_MAX_AGE_MINUTES', defaults.DEFAULT_OFFICIAL_MAX_AGE_MINUTES)),
    news_max_age_minutes=int(os.getenv('NEWS_MAX_AGE_MINUTES', defaults.DEFAULT_NEWS_MAX_AGE_MINUTES)),
    analysis_max_age_minutes=int(os.getenv('ANALYSIS_MAX_AGE_MINUTES', defaults.DEFAULT_ANALYSIS_MAX_AGE_MINUTES)),
    show_source_time=_to_bool('SHOW_SOURCE_TIME', defaults.DEFAULT_SHOW_SOURCE_TIME),
    social_fail_threshold=int(os.getenv('SOCIAL_FAIL_THRESHOLD', '3')),
    social_cooldown_minutes=int(os.getenv('SOCIAL_COOLDOWN_MINUTES', '60')),
    social_health_log_interval_seconds=int(os.getenv('SOCIAL_HEALTH_LOG_INTERVAL_SECONDS', '1800')),
    full_article_fetch_enabled=_to_bool('FULL_ARTICLE_FETCH_ENABLED', defaults.DEFAULT_FULL_ARTICLE_FETCH_ENABLED),
    full_article_min_text_length=int(os.getenv('FULL_ARTICLE_MIN_TEXT_LENGTH', defaults.DEFAULT_FULL_ARTICLE_MIN_TEXT_LENGTH)),
    ai_summary_min_chars=int(os.getenv('AI_SUMMARY_MIN_CHARS', defaults.DEFAULT_AI_SUMMARY_MIN_CHARS)),
    fallback_summary_min_chars=int(os.getenv('FALLBACK_SUMMARY_MIN_CHARS', defaults.DEFAULT_FALLBACK_SUMMARY_MIN_CHARS)),
    drop_weak_summaries=_to_bool('DROP_WEAK_SUMMARIES', defaults.DEFAULT_DROP_WEAK_SUMMARIES),
    url_type_filter_enabled=_to_bool('URL_TYPE_FILTER_ENABLED', defaults.DEFAULT_URL_TYPE_FILTER_ENABLED),
    drop_analysis_pages=_to_bool('DROP_ANALYSIS_PAGES', defaults.DEFAULT_DROP_ANALYSIS_PAGES),
    drop_video_pages=_to_bool('DROP_VIDEO_PAGES', defaults.DEFAULT_DROP_VIDEO_PAGES),
    require_market_relevance=_to_bool('REQUIRE_MARKET_RELEVANCE', defaults.DEFAULT_REQUIRE_MARKET_RELEVANCE),
    official_keyword_alerts=_to_bool('OFFICIAL_KEYWORD_ALERTS', defaults.DEFAULT_OFFICIAL_KEYWORD_ALERTS),
    calendar_headsup_enabled=_to_bool('CALENDAR_HEADSUP_ENABLED', defaults.DEFAULT_CALENDAR_HEADSUP_ENABLED),
    calendar_headsup_days=int(os.getenv('CALENDAR_HEADSUP_DAYS', defaults.DEFAULT_CALENDAR_HEADSUP_DAYS)),
    state_store=StateStore(),
)
