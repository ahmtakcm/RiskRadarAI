import json
import time
from urllib.parse import urlparse

from clients.http_client import http_client
from config.paths import RULES_DIR
from config.settings import settings
from core.logger import get_logger

logger = get_logger("social_fetcher")
MIRRORS_PATH = RULES_DIR / "social_mirrors.json"


def _load_mirrors() -> list[dict]:
    try:
        data = json.loads(MIRRORS_PATH.read_text(encoding="utf-8"))
        mirrors = [m for m in data.get("mirrors", []) if m.get("enabled", True)]
        return sorted(mirrors, key=lambda x: x.get("priority", 999))
    except Exception as exc:
        logger.warning("Social mirror config yüklenemedi: %s", exc)
        return []


def _extract_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or "/"


def _extract_base(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


def _candidate_urls(original_url: str, preferred_base: str | None = None) -> list[tuple[str, str]]:
    path = _extract_path(original_url)
    original_base = _extract_base(original_url)
    bases: list[str] = []
    if preferred_base:
        bases.append(preferred_base.rstrip('/'))
    if original_base and original_base.rstrip('/') not in bases:
        bases.append(original_base.rstrip('/'))
    for mirror in _load_mirrors():
        base_url = mirror.get("base_url", "").rstrip("/")
        if base_url and base_url not in bases:
            bases.append(base_url)
    return [(base, f"{base}{path}") for base in bases]


def _looks_like_rss(text: str) -> bool:
    blob = str(text or '').strip().lower()
    if not blob:
        return False
    return '<rss' in blob or '<feed' in blob or '<?xml' in blob


def _log_health_event(level: str, feed_name: str, message: str, health: dict):
    now = time.time()
    last_log_at = float(health.get("last_log_at") or 0)
    if now - last_log_at < settings.social_health_log_interval_seconds:
        return
    health["last_log_at"] = now
    if level == "warning":
        logger.warning("%s: %s", feed_name, message)
    else:
        logger.info("%s: %s", feed_name, message)


def fetch(feed: dict) -> str:
    source_health = settings.state_store.load_source_health()
    feed_name = feed.get("name", "social_feed")
    health = source_health.get(feed_name, {})
    now = time.time()

    cooldown_until = float(health.get("cooldown_until") or 0)
    if cooldown_until > now:
        _log_health_event("info", feed_name, f"sosyal feed cooldown aktif, yeniden deneme {int(cooldown_until - now)} sn sonra", health)
        source_health[feed_name] = health
        settings.state_store.save_source_health(source_health)
        return ""

    preferred_base = health.get("preferred_base")
    errors: list[str] = []

    for base, candidate_url in _candidate_urls(feed["url"], preferred_base=preferred_base):
        try:
            text = http_client.get_text(candidate_url, feed_mode=True)
            if not _looks_like_rss(text):
                raise ValueError('RSS/XML yerine geçersiz içerik döndü')
            previous_failures = int(health.get("consecutive_failures") or 0)
            if previous_failures > 0 and health.get("preferred_base") != base:
                logger.info("%s: sosyal mirror değişti -> %s", feed_name, base)
            elif previous_failures > 0:
                logger.info("%s: sosyal feed toparlandı", feed_name)
            health.update({
                "preferred_base": base,
                "last_success_at": now,
                "consecutive_failures": 0,
                "cooldown_until": 0,
                "last_error": "",
                "last_attempted_url": candidate_url,
            })
            source_health[feed_name] = health
            settings.state_store.save_source_health(source_health)
            return text
        except Exception as exc:
            errors.append(f"{base}: {exc}")

    failures = int(health.get("consecutive_failures") or 0) + 1
    health["consecutive_failures"] = failures
    health["last_error"] = errors[-1] if errors else "unknown social fetch error"
    health["last_attempted_url"] = feed.get("url", "")
    if failures >= settings.social_fail_threshold:
        health["cooldown_until"] = now + (settings.social_cooldown_minutes * 60)
        _log_health_event("warning", feed_name, f"sosyal mirrorlar başarısız, {settings.social_cooldown_minutes} dk cooldown. Son hata: {health['last_error']}", health)
    else:
        _log_health_event("warning", feed_name, f"sosyal feed denemesi başarısız ({failures}/{settings.social_fail_threshold}). Son hata: {health['last_error']}", health)
    source_health[feed_name] = health
    settings.state_store.save_source_health(source_health)
    return ""
