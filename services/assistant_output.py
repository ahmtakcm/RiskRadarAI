from config.settings import settings
from core.time_utils import format_local_time
from filters.ai_parse import build_fallback_summary


def _summary_from_analysis(item: dict, analysis: dict) -> str:
    if analysis.get('summary_tr'):
        return str(analysis['summary_tr']).strip()
    gem = analysis.get('gemini') or {}
    if gem.get('summary_tr'):
        return str(gem['summary_tr']).strip()
    return build_fallback_summary(item)


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
    }
    return mapping.get(label, 'Analiz/çıkarım')


def build_signal_message(item: dict, score: int, analysis: dict, origin_label: str, verified: bool = False, official_match: dict | None = None, overlap: set[str] | None = None):
    header = analysis.get('header', '🧭 İZLEME')
    if verified:
        header = '✅ RESMÎ PARALEL DOĞRULAMA'

    summary = _summary_from_analysis(item, analysis)
    alarm_score = int(analysis.get('alarm_score', score or 0))
    level_label = str(analysis.get('level_label', 'İzleme'))
    confirmation_class = _confirmation_label(analysis, verified=verified)

    lines = [
        header,
        '',
        f'Akış: {origin_label}',
        f"Kaynak: {item.get('source_name', 'Bilinmiyor')}",
        f'Teyit Sınıfı: {_confirmation_text(confirmation_class)}',
        f'Alarm Düzeyi: {level_label}',
        f'Alarm Puanı: {alarm_score}/100',
        '',
        'Özet:',
        summary,
    ]

    lines += _time_lines(item)

    if verified and official_match:
        lines += ['', f"Paralel resmî kaynak: {official_match.get('source_name', 'Bilinmiyor')}"]
        if overlap:
            lines += [f"Ortak sinyaller: {', '.join(sorted(overlap))}"]

    if item.get('link'):
        lines += ['', f"Kaynak/Referans: {item['link']}"]

    return '\n'.join(lines)


def build_analysis_message(item: dict, score: int, analysis: dict):
    summary = _summary_from_analysis(item, analysis)
    alarm_score = int(analysis.get('alarm_score', score or 0))
    level_label = str(analysis.get('level_label', 'İzleme'))
    confirmation_class = str(analysis.get('confirmation_class', 'analysis_inferred'))

    lines = [
        '🧠 ANALİZ / RAPOR KAYNAĞI',
        '',
        f"Kaynak: {item.get('source_name', 'Bilinmiyor')}",
        f'Teyit Sınıfı: {_confirmation_text(confirmation_class)}',
        f'Alarm Düzeyi: {level_label}',
        f'Alarm Puanı: {alarm_score}/100',
        '',
        'Özet:',
        summary
    ]

    lines += _time_lines(item)

    if item.get('link'):
        lines += ['', f"Kaynak/Referans: {item['link']}"]
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
            score = entry.get('alarm_score', entry.get('score'))
            if score is None and isinstance(raw, dict):
                score = raw.get('score')

            if title_text and score is not None:
                lines.append(f"• {source}: {title_text} — Alarm Puanı: {int(score)}/100")
            elif title_text:
                lines.append(f"• {source}: {title_text}")
            else:
                lines.append(f"• {source}")
        else:
            text = str(entry).strip()
            if text:
                lines.append(f"• {text}")

    return '\n'.join(lines)
