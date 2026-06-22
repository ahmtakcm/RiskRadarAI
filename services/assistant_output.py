from config.settings import settings
from core.time_utils import format_local_time
from enrichers.text_hygiene import (
    clean_telegram_text,
    is_generic_summary,
    is_non_event_index_title,
    is_probably_english,
)
from filters.ai_parse import build_fallback_summary, is_usable_summary


def _clean_user_summary(item: dict, value: str) -> str:
    cleaned = clean_telegram_text(value)
    if not cleaned:
        return ""
    if not is_generic_summary(cleaned) and not is_non_event_index_title(cleaned) and not is_probably_english(cleaned) and is_usable_summary(cleaned, item):
        return cleaned
    return ""


def _summary_from_analysis(item: dict, analysis: dict) -> str:
    if analysis.get('summary_tr'):
        summary = _clean_user_summary(item, analysis['summary_tr'])
        if summary:
            return summary
    gem = analysis.get('gemini') or {}
    if gem.get('summary_tr'):
        summary = _clean_user_summary(item, gem['summary_tr'])
        if summary:
            return summary
    summary = _clean_user_summary(item, build_fallback_summary(item))
    if summary:
        return summary
    for raw in (item.get('translated_text'), item.get('description'), item.get('article_text'), item.get('title')):
        summary = clean_telegram_text(raw)
        if summary and not is_generic_summary(summary) and not is_non_event_index_title(summary) and not is_probably_english(summary) and is_usable_summary(summary, item):
            return summary
    source = clean_telegram_text(item.get('source_name')) or 'Kaynak'
    return f'{source}: Bilgi kaybını önlemek için otomatik özet üretilmedi; özgün referansı inceleyin.'


def _time_lines(item: dict) -> list[str]:
    if not settings.show_source_time:
        return []
    lines: list[str] = []
    if item.get('pub_date'):
        local_text = format_local_time(item['pub_date'])
        if local_text:
            lines += ['', f'Tarih: {local_text}']
        else:
            lines += ['', f"Tarih: {item['pub_date']}"]
    return lines


def _confirmation_label(analysis: dict, verified: bool = False) -> str:
    if verified:
        return 'official_parallel'
    return str(analysis.get('confirmation_class', 'analysis_inferred') or 'analysis_inferred')


def _confirmation_text(label: str) -> str:
    mapping = {
        'official_confirmed': 'Resmî teyit',
        'official_parallel': 'Resmî paralel',
        'media_verified': 'Güçlü medya',
        'analysis_inferred': 'Analiz/çıkarım',
        'osint_unconfirmed': 'OSINT / teyitsiz sinyal',
    }
    return mapping.get(label, 'Analiz/çıkarım')


def _verification_line(origin_label: str, confirmation_class: str, verified: bool) -> str:
    if str(origin_label or '').upper() == 'OSINT' and not verified:
        return 'Teyit: OSINT / teyitsiz sinyal'
    return f'Teyit Sınıfı: {_confirmation_text(confirmation_class)}'


def build_signal_message(item: dict, score: int, analysis: dict, origin_label: str, verified: bool = False, official_match: dict | None = None, overlap: set[str] | None = None):
    header = analysis.get('header', '🧭 İZLEME')
    if verified:
        header = '✅ RESMÎ PARALEL DOĞRULAMA'

    summary = _summary_from_analysis(item, analysis)
    confirmation_class = _confirmation_label(analysis, verified=verified)

    lines = [
        header,
        '',
        f'Akış: {origin_label}',
        f"Kaynak: {item.get('source_name', 'Bilinmiyor')}",
        _verification_line(origin_label, confirmation_class, verified),
    ]
    lines += ['', 'Özet:', summary]

    lines += _time_lines(item)

    if item.get('triggered_profiles'):
        lines += ['', 'Tetiklenen profiller: ' + ', '.join(item.get('triggered_profiles', []))]

    if verified and official_match:
        lines += ['', f"Paralel resmî kaynak: {official_match.get('source_name', 'Bilinmiyor')}"]
        if overlap:
            lines += [f"Ortak sinyaller: {', '.join(sorted(overlap))}"]

    link = clean_telegram_text(item.get('link'))
    if link:
        lines += ['', f"Kaynak/Referans: {link}"]

    return '\n'.join(lines)


def build_analysis_message(item: dict, score: int, analysis: dict):
    summary = _summary_from_analysis(item, analysis)
    confirmation_class = str(analysis.get('confirmation_class', 'analysis_inferred'))

    lines = [
        '🧠 ANALİZ / RAPOR KAYNAĞI',
        '',
        f"Kaynak: {item.get('source_name', 'Bilinmiyor')}",
        f'Teyit Sınıfı: {_confirmation_text(confirmation_class)}',
    ]
    lines += ['', 'Özet:', summary]

    lines += _time_lines(item)

    link = clean_telegram_text(item.get('link'))
    if link:
        lines += ['', f"Kaynak/Referans: {link}"]
    return '\n'.join(lines)


def build_official_confirmation_message(signal: dict, official_item: dict, overlap: set[str], match_note: str | None = None):
    lines = [
        '✅ RESMÎ TEYİT GELDİ',
        '',
        'Önce erken sinyal olarak görülen konu şimdi resmî kaynakta da geçti.',
        '',
        f"İlk sinyal: {signal.get('source_name', 'Bilinmiyor')}",
        f"Resmî kaynak: {official_item.get('source_name', 'Bilinmiyor')}",
    ]
    if official_item.get('link'):
        lines += ['', f"Resmî referans: {official_item['link']}"]
    if overlap:
        lines += ['', f"Ortak sinyaller: {', '.join(sorted(overlap))}"]
    if match_note:
        lines += ['', f'AI eşleşme notu: {match_note}']
    return '\n'.join(lines)


def build_digest_message(*args, **kwargs):
    paragraph = kwargs.get('paragraph')
    if not paragraph and len(args) >= 2 and isinstance(args[1], str):
        paragraph = str(args[1]).strip()

    if paragraph:
        title = kwargs.get('title') or '🧾 12 Saatlik Sessiz Özet'
        lines = [title, '', str(paragraph).strip()]
        return '\n'.join(lines)

    title = kwargs.get('title') or '🗞️ DİGEST'
    max_items = int(kwargs.get('max_items', 5) or 5)

    items = (
        kwargs.get('items')
        or kwargs.get('entries')
        or kwargs.get('candidates')
        or kwargs.get('digest_items')
        or []
    )

    if not items:
        for arg in args:
            if isinstance(arg, (list, tuple)):
                items = list(arg)
                break

    lines = [title, '']

    if not items:
        lines.append('Özetlenecek uygun içerik bulunmadı.')
        return '\n'.join(lines)

    for raw in list(items)[:max_items]:
        entry = raw
        if isinstance(raw, dict) and isinstance(raw.get('item'), dict):
            entry = raw.get('item') or {}

        if isinstance(entry, dict):
            source = str(entry.get('source_name', 'Bilinmiyor') or 'Bilinmiyor')
            title_text = str(entry.get('title', '') or '').strip()
            if title_text:
                lines.append(f"• {source}: {title_text}")
            else:
                lines.append(f"• {source}")
        else:
            text = str(entry).strip()
            if text:
                lines.append(f"• {text}")

    return '\n'.join(lines)
