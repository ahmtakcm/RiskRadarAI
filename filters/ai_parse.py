from __future__ import annotations

import html
import re
from enrichers.turkish_summary import build_turkish_summary
from enrichers.text_hygiene import (
    clean_telegram_text,
    is_generic_summary,
    is_non_event_index_title,
)

_ALLOWED_LABELS = {
    'ignore': 'ignore',
    'watch': 'watch',
    'early_signal': 'early_signal',
    'verified_alert': 'verified_alert',
    'kritik': 'verified_alert',
    'critical': 'verified_alert',
    'krıtık': 'verified_alert',
    'piyasa_uyarisi': 'watch',
    'market_alert': 'watch',
    'bilgi': 'watch',
    'info': 'watch',
}

_ALLOWED_IMPACT = {
    'low': 'Düşük',
    'medium': 'Orta',
    'high': 'Yüksek',
    'belirsiz': 'Belirsiz',
    'unclear': 'Belirsiz',
    'dusuk': 'Düşük',
    'orta': 'Orta',
    'yuksek': 'Yüksek',
    'low_unclear': 'Düşük/Belirsiz',
}

_ALLOWED_CATEGORY = {
    'security': 'security',
    'market': 'market',
    'health': 'health',
    'political': 'political',
    'analysis': 'analysis',
    'mixed': 'mixed',
}

_GENERIC_SUMMARY_BITS = (
    'iran bağlantılı gelişme',
    'abd tarafı dahil',
    'hürmüz boğazı etkisi olabilir',
    'nükleer başlık içeriyor',
    'detay için bağlantıyı aç',
    'navigation menu',
    'show more',
    'what we know about',
    'al jazeera navigation menu',
    'iran gündemine ilişkin açıklama yaptı',
    'iran gündemine ilişkin resmi açıklama yaptı',
    'dünya gündemine ilişkin açıklama yaptı',
    'dünya gündemine ilişkin resmi açıklama yaptı',
    'hürmüz hattı gündemine ilişkin açıklama yaptı',
    'hürmüz hattı gündemine ilişkin resmi açıklama yaptı',
)

_NOISE_BITS = (
    'skip to content', 'skip to site index', 'navigation menu', 'show more',
    'our channels', 'our network', 'click here to share', 'published on',
    'credit', 'liveblog', 'follow our live', 'follow live', 'read more',
    'open in app', 'cookie', 'subscribe', 'newsletter', 'privacy policy'
)

_CONTEXT_TERMS = ['iran', 'nato', 'trump', 'hormuz', 'russia', 'ukraine', 'israel', 'oil', 'gold']

_MARKET_HIGH_TERMS = ['blockade', 'abluka', 'strait of hormuz', 'hormuz', 'shipping', 'liman', 'port', 'iranian ports', 'oil', 'petrol', 'brent', 'wti', '$100', 'sanction', 'yaptirim', 'tariff', 'trade', 'ceasefire', 'baris gorusmeleri', 'peace talks', 'blockade of maritime traffic']
_SECURITY_HIGH_TERMS = ['strike', 'saldiri', 'attack', 'airstrike', 'missile', 'abluka', 'blockade', 'military', 'askeri', 'resume strikes', 'limited strikes', 'high tempo strikes', 'mine clearance']


def _norm(value: str) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('🚨', '').replace('💹', '').replace('ℹ️', '').replace('ℹ', '')
    text = text.replace('/', '_').replace('-', '_').replace(' ', '_')
    translate = str.maketrans({'ğ':'g','ü':'u','ş':'s','ö':'o','ç':'c','ı':'i','Ğ':'g','Ü':'u','Ş':'s','Ö':'o','Ç':'c','İ':'i'})
    text = text.translate(translate)
    text = re.sub(r'[^a-zA-Z0-9_]+', '', text)
    text = text.strip('_')
    return text


def _pick(mapping: dict[str, str], value: str, default: str) -> str:
    key = _norm(value)
    return mapping.get(key, default)


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clean_text(value: str) -> str:
    return clean_telegram_text(html.unescape(str(value or '')))


def _strip_noise_text(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ''
    parts = re.split(r'(?<=[.!?])\s+', text)
    kept = []
    seen = set()
    for part in parts:
        line = part.strip(' -–•')
        low = line.lower()
        if not line:
            continue
        if low in seen:
            continue
        seen.add(low)
        if any(bit in low for bit in _NOISE_BITS):
            continue
        if len(line) < 30:
            continue
        kept.append(line)
    return ' '.join(kept).strip()


def _context_text(item: dict) -> str:
    return ' '.join([
        _clean_text(item.get('title', '')),
        _clean_text(item.get('description', '')),
        _clean_text(item.get('article_text', '')),
    ]).strip().lower()


def _extract_sentences(text: str) -> list[str]:
    text = _strip_noise_text(text)
    if not text:
        return []
    parts = re.split(r'(?<=[.!?])\s+', text)
    out = []
    for p in parts:
        s = p.strip(' -–•')
        low = s.lower()
        if len(s) < 35:
            continue
        if any(bit in low for bit in _NOISE_BITS):
            continue
        out.append(s)
    return out


def _looks_like_live_content(item: dict) -> bool:
    if str(item.get('content_class', '')).lower() == 'liveblog':
        return True
    blob = ' '.join([
        _clean_text(item.get('title', '')),
        _clean_text(item.get('description', '')),
        str(item.get('link', '') or ''),
    ]).lower()
    return any(term in blob for term in ('live updates', 'live update', 'live blog', 'liveblog', 'as it happened', '/liveblog/', '/live/'))


def _safe_turkish_stub(item: dict, live_mode: bool = False) -> str:
    return ''


def _is_title_like(summary: str, item: dict | None = None) -> bool:
    text = _clean_text(summary).lower()
    title = _clean_text((item or {}).get('title', '')).lower()
    if not text or not title:
        return False
    if text == title:
        return True
    if text.startswith(title[:120]) or title.startswith(text[:120]):
        return True
    text_words = set(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9']+", text))
    title_words = set(re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9']+", title))
    if not text_words or not title_words:
        return False
    overlap = len(text_words & title_words) / max(1, len(text_words | title_words))
    return overlap >= 0.82


def _meaningful_source_prefix(item: dict) -> str:
    source = _clean_text(item.get('source_name', ''))
    title = _clean_text(item.get('title', ''))
    title_low = title.lower()
    if 'envoy' in title_low:
        return 'Büyükelçi düzeyinde yapılan açıklamaya göre'
    if 'minister' in title_low:
        return 'Bakan düzeyindeki açıklamaya göre'
    if 'president' in title_low:
        return 'Cumhurbaşkanlığı düzeyinde yapılan açıklamaya göre'
    if source:
        return f'{source} kaynağına göre'
    return ''


def _content_summary_from_text(value: str, item: dict, max_sentences: int = 2) -> str:
    sentences = _extract_sentences(value)
    if not sentences:
        return ''
    title = _clean_text(item.get('title', ''))
    if is_non_event_index_title(title):
        title = ''
    chosen = []
    for sentence in sentences:
        line = sentence.strip()
        if not line:
            continue
        if title and line.lower().startswith(title.lower()):
            line = line[len(title):].strip(' .:-–—')
        if len(line) < 30:
            continue
        if _is_title_like(line, item):
            continue
        chosen.append(line)
        if len(chosen) >= max_sentences:
            break
    if not chosen:
        return ''
    summary = ' '.join(chosen).strip()
    if _looks_english_heavy(summary) or is_generic_summary(summary) or is_non_event_index_title(summary):
        return ''
    return summary[:700]


def _content_summary_from_item(item: dict, live_mode: bool = False) -> str:
    article_text = _strip_noise_text(item.get('article_text', ''))
    desc = _strip_noise_text(item.get('description', ''))
    preferred = [article_text, desc]
    if live_mode:
        preferred = [desc, article_text]
    for raw in preferred:
        summary = _content_summary_from_text(raw, item)
        if summary:
            return summary
    return ''


def build_turkish_fallback_summary(item: dict) -> str:
    if item.get('_non_event_index'):
        return ''
    live_mode = _looks_like_live_content(item)
    heuristic = build_turkish_summary(item).strip()
    content_summary = _content_summary_from_item(item, live_mode=live_mode)
    if content_summary and not _summary_is_weak(content_summary, item):
        return content_summary[:700]
    if heuristic and not _summary_is_weak(heuristic, item):
        return heuristic[:700]
    return ''


def build_fallback_summary(item: dict) -> str:
    if item.get('_non_event_index'):
        return ''
    if _looks_like_live_content(item):
        return build_turkish_fallback_summary(item)
    content_summary = _content_summary_from_item(item, live_mode=False)
    if content_summary and not _summary_is_weak(content_summary, item):
        return content_summary[:700]
    heuristic = build_turkish_summary(item).strip()
    if heuristic and not _summary_is_weak(heuristic, item):
        return heuristic[:700]
    return ''

def _looks_english_heavy(text: str) -> bool:
    t = _clean_text(text)
    if not t:
        return False
    words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü']+", t)
    if not words:
        return False
    tr_hits = sum(1 for w in words if re.search(r'[ÇĞİÖŞÜçğıöşü]', w))
    en_hits = sum(1 for w in words if re.search(r'[A-Za-z]', w))
    return en_hits > 20 and tr_hits == 0


def _summary_is_weak(summary: str, item: dict | None = None) -> bool:
    text = _clean_text(summary).lower()
    min_chars = 20
    if len(text) < min_chars:
        return True
    if any(bit in text for bit in _GENERIC_SUMMARY_BITS):
        return True
    if is_generic_summary(text) or is_non_event_index_title(text):
        return True
    if any(bit in text for bit in _NOISE_BITS):
        return True
    if _looks_english_heavy(text):
        return True
    if _is_title_like(text, item):
        return True
    # Türkçe metin her zaman Türkçe karakter içermek zorunda değildir.
    # Sadece Latin harfi çok diye özeti zayıf saymak false-positive üretir.
    if _looks_english_heavy(text):
        return True
    return False


def is_usable_summary(summary: str, item: dict | None = None) -> bool:
    return bool(_clean_text(summary)) and not _summary_is_weak(summary, item)


def _mentions_absent_context(summary: str, context: str) -> bool:
    s = _clean_text(summary).lower()
    for term in _CONTEXT_TERMS:
        if term in s and term not in context:
            return True
    return False


def choose_best_summary(item: dict, result: dict | None) -> str:
    candidate = _clean_text((result or {}).get('summary_tr', ''))
    context = _context_text(item)
    if candidate and not (_summary_is_weak(candidate, item) or _mentions_absent_context(candidate, context)):
        return candidate[:700]
    fb = build_fallback_summary(item)
    if fb and not _summary_is_weak(fb, item):
        return fb[:700]
    tr_fb = build_turkish_fallback_summary(item)
    if tr_fb and not _summary_is_weak(tr_fb, item):
        return tr_fb[:700]
    return ''


def normalize_gemini_result(data: dict | None) -> dict | None:
    if not data:
        return None
    result = dict(data)
    result['label'] = _pick(_ALLOWED_LABELS, result.get('label', ''), 'watch')
    result['category'] = _pick(_ALLOWED_CATEGORY, result.get('category', ''), 'mixed')
    result['market_impact'] = _pick(_ALLOWED_IMPACT, result.get('market_impact', ''), 'Belirsiz')
    result['security_impact'] = _pick(_ALLOWED_IMPACT, result.get('security_impact', ''), 'Belirsiz')
    result['severity'] = max(0.0, min(10.0, _to_float(result.get('severity', 0))))
    result['summary_tr'] = _clean_text(result.get('summary_tr', ''))[:700]
    result['reason_short'] = _clean_text(result.get('reason_short', ''))[:240]
    if 'confidence' in result:
        result['confidence'] = max(0.0, min(1.0, _to_float(result.get('confidence', 0))))
    same_event = str(result.get('same_event', '')).strip().lower()
    if same_event in {'true', '1', 'yes', 'evet'}:
        result['same_event'] = True
    elif same_event in {'false', '0', 'no', 'hayir', 'hayır'}:
        result['same_event'] = False

    context_blob = ' '.join([
        str(result.get('summary_tr', '')),
        str(result.get('reason_short', '')),
    ]).lower()
    if any(term in context_blob for term in _MARKET_HIGH_TERMS):
        if any(x in context_blob for x in ['blockade', 'oil', 'brent', 'wti', '$100', 'hormuz']):
            result['market_impact'] = 'Yüksek'
        elif result['market_impact'] in {'Belirsiz', 'Düşük', 'Düşük/Belirsiz'}:
            result['market_impact'] = 'Orta'
    if any(term in context_blob for term in _SECURITY_HIGH_TERMS):
        if any(x in context_blob for x in ['blockade', 'strike', 'saldiri', 'attack', 'mine clearance']):
            result['security_impact'] = 'Yüksek'
        elif result['security_impact'] in {'Belirsiz', 'Düşük', 'Düşük/Belirsiz'}:
            result['security_impact'] = 'Orta'
    return result
