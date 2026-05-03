import html as html_lib
import re
from datetime import datetime
from urllib.parse import urlparse

from clients.http_client import http_client
from config.settings import settings
from core.logger import get_logger

_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')
_SCRIPT_RE = re.compile(r'<(script|style|noscript|svg)[^>]*>.*?</\1>', re.IGNORECASE | re.DOTALL)

logger = get_logger('html_fetcher')

_CENTCOM_HOME_URL = 'https://www.centcom.mil/'
_CENTCOM_PRIMARY_URL = 'https://www.centcom.mil/MEDIA/PRESS-RELEASES/'


def fetch(url: str) -> str:
    return http_client.get_text(url)


def fetch_centcom_listing(url: str) -> tuple[str, str]:
    year = datetime.utcnow().year
    candidates = []
    for candidate in (
        url,
        f'https://www.centcom.mil/MEDIA/PRESS-RELEASES/Year/{year}/',
        _CENTCOM_HOME_URL,
    ):
        if candidate not in candidates:
            candidates.append(candidate)

    last_exc = None
    for index, candidate in enumerate(candidates, start=1):
        try:
            html_text = http_client.get_text(candidate)
            if html_text and ('Press Releases' in html_text or 'Public Releases' in html_text):
                if candidate != url:
                    logger.info(
                        'CENTCOM fallback başarılı | kaynak=%s | deneme=%s',
                        candidate,
                        index,
                    )
                return html_text, candidate
        except Exception as exc:
            last_exc = exc
            logger.warning(
                'Listing fetch hatası (CENTCOM Press Releases), CENTCOM fallback deneniyor | url=%s | hata=%s',
                candidate,
                exc,
            )
    if last_exc:
        raise last_exc
    raise RuntimeError('CENTCOM listing alınamadı')


def _strip_html(text: str) -> str:
    text = _SCRIPT_RE.sub(' ', text)
    text = re.sub(r'</(p|div|article|section|h1|h2|h3|li|br)>', '\n', text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(' ', text)
    text = html_lib.unescape(text)
    lines = []
    for raw in text.splitlines():
        line = _WS_RE.sub(' ', raw).strip()
        if not line:
            continue
        if len(line) < 30:
            continue
        lines.append(line)
    return '\n'.join(lines)


def extract_article_text(html_text: str) -> str:
    text = _strip_html(html_text)
    if not text:
        return ''
    lines = []
    seen = set()
    for line in text.splitlines():
        low = line.lower()
        if low in seen:
            continue
        seen.add(low)
        if any(skip in low for skip in ['cookie', 'subscribe', 'newsletter', 'advertisement', 'privacy policy']):
            continue
        lines.append(line)
    joined = '\n'.join(lines)
    return joined[:8000]


def should_fetch_full_article(url: str, source_kind: str = '') -> bool:
    if not settings.full_article_fetch_enabled:
        return False
    if not url or not url.startswith('http'):
        return False
    host = (urlparse(url).netloc or '').lower()
    blocked = ('nitter.', 'twitt.re', 'xcancel.com', 'x.com', 'twitter.com', 't.me')
    if any(b in host for b in blocked):
        return False
    if source_kind == 'rss_social':
        return False
    lowered = url.lower()
    if any(bad in lowered for bad in ('/video/', '/videos/', '/podcast/', '/interactive/', '/opinion/', '/analysis/', '/explainer/')):
        return False
    return True


def fetch_article_text(url: str, source_kind: str = '') -> str:
    if not should_fetch_full_article(url, source_kind):
        return ''
    try:
        html_text = fetch(url)
        text = extract_article_text(html_text)
        if len(text) < settings.full_article_min_text_length:
            return text
        return text
    except Exception:
        return ''
