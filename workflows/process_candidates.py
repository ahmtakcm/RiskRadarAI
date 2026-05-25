from core.cooldown import should_send_alert, mark_alert_sent
from clients.telegram_client import telegram_client
from clients.ai_client import ai_client
from config.settings import settings
from core.logger import get_logger
from core.matching import now_ts, topic_overlap
from source_selectors.profile_loader import load_active_config
from services.assistant_output import build_signal_message, build_analysis_message, build_official_confirmation_message
from fetchers.html_fetcher import fetch_article_text
from filters.ai_parse import choose_best_summary
from core.news_log import build_log_entry, append_news_log
from core.event_merger import group_items, should_send_cluster, build_alert, cluster_key
from core.notification_policy import item_policy_context

logger = get_logger('process_candidates')


def _inc_metric(metrics: dict[str, int] | None, key: str, amount: int = 1):
    if metrics is not None:
        metrics[key] = metrics.get(key, 0) + amount


def _log_process_metrics(metrics: dict[str, int]):
    logger.info(
        'candidate_count | stage=process_candidates | official=%s | social=%s | osint=%s | analysis=%s | total=%s',
        metrics.get('official_candidate_count', 0),
        metrics.get('social_candidate_count', 0),
        metrics.get('osint_candidate_count', 0),
        metrics.get('analysis_candidate_count', 0),
        metrics.get('candidate_count', 0),
    )
    logger.info('alert_sent_count | count=%s', metrics.get('alert_sent_count', 0))
    logger.info('digest_candidate_count | count=%s', metrics.get('digest_candidate_count', 0))
    logger.info('cooldown_drop_count | count=%s', metrics.get('cooldown_drop_count', 0))
    logger.info('low_score_digest_count | count=%s', metrics.get('low_score_digest_count', 0))
    skip_reasons = {
        key.removeprefix('skip_reason_'): value
        for key, value in metrics.items()
        if key.startswith('skip_reason_') and value
    }
    for reason, count in sorted(skip_reasons.items()):
        logger.info('skip_reason_count | stage=process_candidates | reason=%s | count=%s', reason, count)
    logger.info('skip_reason_count | stage=process_candidates | count=%s', sum(skip_reasons.values()))


def _notification_context(item: dict, origin_label: str | None = None) -> dict:
    return item_policy_context(
        item,
        origin_label=origin_label,
        settings=settings,
        send_unverified_social=item.get('_send_unverified_social', settings.send_unverified_social_alerts),
        send_unverified_osint=item.get('_send_unverified_osint', True),
    )


def _log_notification_decision(action: str, item: dict, *, reason: str | None = None, origin_label: str | None = None, alert_key: str | None = None):
    ctx = _notification_context(item, origin_label=origin_label)
    logger.info(
        'Notification %s | source=%s | policy=%s | lane=%s | reason=%s | score=%s | direct=%s | requires_ai=%s | requires_confirmation=%s | digest_only=%s | relay=%s | key=%s',
        action, item.get('source_name', ''), ctx.get('notify_policy'), ctx.get('notification_lane'), reason or '', item.get('score', ''),
        ctx.get('can_notify_direct'), ctx.get('requires_ai_should_notify'), ctx.get('requires_official_confirmation'),
        ctx.get('can_be_digest_only'), ctx.get('relay_label'), alert_key or '',
    )


def _is_strict_official_item(item: dict) -> bool:
    official_class = str(item.get('official_class', '') or '').strip().lower()
    return official_class.startswith('official_')


def _split_primary_feed_candidates(candidates: list) -> tuple[list, list]:
    strict_official = []
    primary_news = []
    for candidate in candidates:
        if _is_strict_official_item(candidate.get('item', {})):
            strict_official.append(candidate)
        else:
            primary_news.append(candidate)
    return strict_official, primary_news


def _trim_history(entries: list, limit: int = 300):
    return sorted(entries, key=lambda x: x.get('ts', 0), reverse=True)[:limit]


def _remember_story(state: dict, candidate: dict):
    story_hashes = set(state.get('seen_story_hashes', []))
    story_key = str(candidate.get('story_key', '') or '').strip()
    if story_key:
        story_hashes.add(story_key)
    state['seen_story_hashes'] = list(story_hashes)[-5000:]


def _alert_identity(candidate: dict) -> str:
    story_key = str(candidate.get('story_key') or '').strip()
    if story_key.startswith('social-status:'):
        return story_key

    item = candidate.get('item', {}) or {}
    event_key = cluster_key({
        'title': item.get('title', ''),
        'summary': item.get('description') or item.get('summary') or '',
        'content': item.get('article_text') or item.get('content') or '',
        'source_name': item.get('source_name', ''),
    })
    if event_key in {'russia-ukraine-starobelsk', 'russia-ukraine-bila-tserkva'}:
        return f'event:{event_key}'

    return candidate.get('hash', '')


def _cleanup_pending(state: dict):
    cutoff = now_ts() - (settings.pending_social_ttl_minutes * 60)
    pending = [x for x in state.get('pending_unofficial_signals', []) if x.get('ts', 0) >= cutoff]
    state['pending_unofficial_signals'] = _trim_history(pending)


def _ensure_article_text(item: dict):
    if item.get('article_text'):
        return
    link = item.get('link', '')
    source_kind = item.get('source_kind', '')
    text = fetch_article_text(link, source_kind=source_kind)
    if text:
        item['article_text'] = text

def _minimal_fallback_summary(item: dict) -> str:
    raw = str(item.get('description') or item.get('article_text') or item.get('summary') or '').strip()
    raw = ' '.join(raw.split())
    if len(raw) > 420:
        raw = raw[:420].rstrip() + ' ...'
    if raw:
        return raw
    title = str(item.get('title') or '').strip()
    source = str(item.get('source_name') or 'Kaynak').strip()
    link = str(item.get('link') or '').strip()
    bits = [f'{source}: {title}' if title else source]
    if link:
        bits.append(link)
    return '\n'.join(bits).strip()


def _ensure_usable_summary(item: dict, analysis: dict, origin_label: str) -> bool:
    if choose_best_summary(item, analysis.get('gemini') or analysis):
        return True
    fallback = _minimal_fallback_summary(item)
    if not fallback:
        return False
    analysis['summary_tr'] = fallback
    analysis.setdefault('category', 'mixed')
    analysis.pop('reason_short', None)
    analysis.setdefault('header', f'📢 {origin_label} alarmı')
    return True



def _log_news_event(state: dict, item: dict, candidate: dict, analysis: dict | None = None, *, alert_sent: bool, delivery_mode: str, drop_reason: str | None = None, meta: dict | None = None, metrics: dict[str, int] | None = None):
    analysis = analysis or {}
    summary = choose_best_summary(item, analysis.get('gemini') or analysis) or str(analysis.get('summary_tr', '') or '').strip()
    if not summary:
        summary = str(item.get('translated_text', '') or item.get('description', '') or '').strip()

    policy_context = _notification_context(item, origin_label=(meta or {}).get('origin'))
    merged_meta = dict(meta or {})
    merged_meta.setdefault('notification_policy', policy_context)

    entry = build_log_entry(
        item,
        candidate['hash'],
        alert_sent=alert_sent,
        drop_reason=drop_reason,
        translated_text=summary,
        delivery_mode=delivery_mode,
        score=analysis.get('alarm_score', candidate.get('score')),
        meta=merged_meta,
    )
    append_news_log(state, entry)
    if alert_sent:
        _inc_metric(metrics, 'alert_sent_count')
    if delivery_mode == 'digest':
        _inc_metric(metrics, 'digest_candidate_count')
    if drop_reason:
        _inc_metric(metrics, f'skip_reason_{drop_reason}')
    if drop_reason == 'below_alert_threshold':
        _inc_metric(metrics, 'low_score_digest_count')

def _register_official_signal(state: dict, item: dict, candidate: dict):
    history = state.get('official_signal_history', [])
    history.append({
        'hash': candidate['hash'],
        'source_name': item.get('source_name', ''),
        'title': item.get('title', ''),
        'link': item.get('link', ''),
        'pub_date': item.get('pub_date', ''),
        'description': item.get('description', ''),
        'article_text': item.get('article_text', ''),
        'age_minutes': item.get('age_minutes'),
        'topic_tokens': candidate.get('topic_tokens', []),
        'ts': now_ts(),
    })
    state['official_signal_history'] = _trim_history(history)


def _register_pending_unofficial(state: dict, item: dict, candidate: dict, origin: str):
    pending = state.get('pending_unofficial_signals', [])
    pending.append({
        'hash': candidate['hash'],
        'origin': origin,
        'source_name': item.get('source_name', ''),
        'title': item.get('title', ''),
        'link': item.get('link', ''),
        'pub_date': item.get('pub_date', ''),
        'description': item.get('description', ''),
        'article_text': item.get('article_text', ''),
        'age_minutes': item.get('age_minutes'),
        'topic_tokens': candidate.get('topic_tokens', []),
        'score': candidate.get('score', 0),
        'ts': now_ts(),
    })
    state['pending_unofficial_signals'] = _trim_history(pending)


def _gemini_confirms_match(candidate_item: dict, official_match: dict) -> tuple[bool, str | None]:
    if not ai_client.is_matching_enabled():
        return False, None
    result = ai_client.match_items(candidate_item, official_match)
    if not result:
        return False, None
    same = str(result.get('same_event', '')).strip().lower() in {'true', '1', 'yes', 'evet'}
    note = result.get('overlap_reason') or result.get('reason_short') or ''
    return same, note[:180] if note else None


def _find_best_official_match(candidate: dict, official_candidates: list, state: dict, verification_rules: dict):
    best_match = None
    best_overlap = set()
    best_note = None
    candidate_tokens = set(candidate.get('topic_tokens', []))
    min_overlap = int(verification_rules.get('min_overlap_terms', 2))
    min_hp_overlap = int(verification_rules.get('min_high_priority_overlap_terms', 1))
    high_priority_terms = set(term.lower() for term in verification_rules.get('high_priority_terms', []))

    official_pool = []
    for off in official_candidates:
        official_pool.append({
            'hash': off['hash'],
            'source_name': off['item'].get('source_name', ''),
            'title': off['item'].get('title', ''),
            'link': off['item'].get('link', ''),
            'pub_date': off['item'].get('pub_date', ''),
            'description': off['item'].get('description', ''),
            'article_text': off['item'].get('article_text', ''),
            'topic_tokens': off.get('topic_tokens', []),
        })
    official_pool.extend(state.get('official_signal_history', []))

    for off in official_pool:
        overlap = topic_overlap(candidate_tokens, set(off.get('topic_tokens', [])))
        if not overlap:
            continue
        hp_overlap = overlap & high_priority_terms
        passes_rule = len(overlap) >= min_overlap or len(hp_overlap) >= min_hp_overlap
        if not passes_rule:
            continue
        same_ai, note = _gemini_confirms_match(candidate['item'], off)
        if ai_client.is_matching_enabled() and not same_ai:
            continue
        if len(overlap) > len(best_overlap):
            best_overlap = overlap
            best_match = off
            best_note = note
    return best_match, best_overlap, best_note


def _process_official_confirmations(state: dict, official_candidates: list, verification_rules: dict, metrics: dict[str, int] | None = None):
    for official_candidate in official_candidates:
        official_item = official_candidate['item']
        official_tokens = set(official_candidate.get('topic_tokens', []))
        if not official_tokens:
            continue
        remaining_pending = []
        for signal in state.get('pending_unofficial_signals', []):
            overlap = topic_overlap(official_tokens, set(signal.get('topic_tokens', [])))
            if not overlap:
                remaining_pending.append(signal)
                continue
            min_overlap = int(verification_rules.get('min_overlap_terms', 2))
            high_priority_terms = set(term.lower() for term in verification_rules.get('high_priority_terms', []))
            hp_overlap = overlap & high_priority_terms
            if len(overlap) < min_overlap and not hp_overlap:
                remaining_pending.append(signal)
                continue
            same_ai, note = _gemini_confirms_match(signal, official_item)
            if ai_client.is_matching_enabled() and not same_ai:
                remaining_pending.append(signal)
                continue
            confirm_key = f"VERIFY_{signal['hash']}_{official_candidate['hash']}"
            if should_send_alert(state, confirm_key, settings.news_cooldown_seconds):
                try:
                    telegram_client.send_message(build_official_confirmation_message(signal, official_item, overlap, note))
                    mark_alert_sent(state, confirm_key)
                    _inc_metric(metrics, 'alert_sent_count')
                    logger.info('Gayriresmî sinyal için resmî teyit gönderildi: %s', confirm_key)
                except Exception as exc:
                    logger.warning('Telegram resmî teyit alarm hatası: %s', exc)
                    remaining_pending.append(signal)
            else:
                _inc_metric(metrics, 'cooldown_drop_count')
                _inc_metric(metrics, 'skip_reason_cooldown')
                remaining_pending.append(signal)
        state['pending_unofficial_signals'] = _trim_history(remaining_pending)


def _process_official_candidates(state: dict, official_candidates: list, seen_hashes: set[str], sent_count: int, metrics: dict[str, int] | None = None):
    for candidate in official_candidates:
        if sent_count >= settings.max_news_alerts_per_scan:
            break
        item = candidate['item']
        item['score'] = candidate.get('score', item.get('score', ''))
        if not _is_strict_official_item(item):
            continue
        _ensure_article_text(item)
        alert_key = f"NEWS_{_alert_identity(candidate)}"
        if not should_send_alert(state, alert_key, settings.news_cooldown_seconds):
            _inc_metric(metrics, 'cooldown_drop_count')
            _inc_metric(metrics, 'skip_reason_cooldown')
            _log_notification_decision('drop', item, reason='cooldown', origin_label='Resmî/Kurumsal', alert_key=alert_key)
            continue
        analysis = ai_client.analyze_item(item, {}, verified=True)
        if item.get('is_official_routine') or analysis.get('category') == 'ignore':
            _log_news_event(state, item, candidate, analysis, alert_sent=False, delivery_mode='none', drop_reason='routine_suppressed', meta={'origin': 'official', 'verified': True}, metrics=metrics)
            _log_notification_decision('drop', item, reason='routine_suppressed', origin_label='Resmî/Kurumsal', alert_key=alert_key)
            continue
        if not _ensure_usable_summary(item, analysis, 'Resmî/Kurumsal'):
            _inc_metric(metrics, 'skip_reason_no_usable_summary')
            _log_notification_decision('drop', item, reason='no_usable_summary', origin_label='Resmî/Kurumsal', alert_key=alert_key)
            continue
        text = build_signal_message(item, candidate['score'], analysis, origin_label='Resmî/Kurumsal', verified=False)
        try:
            telegram_client.send_message(text)
            mark_alert_sent(state, alert_key)
            seen_hashes.add(candidate['hash'])
            _remember_story(state, candidate)
            _register_official_signal(state, item, candidate)
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=True,
                delivery_mode='alert',
                meta={'origin': 'official', 'verified': True},
                metrics=metrics,
            )
            sent_count += 1
            _log_notification_decision('sent', item, origin_label='Resmî/Kurumsal', alert_key=alert_key)
            logger.info('Resmî haber alarmı gönderildi: %s', alert_key)
        except Exception as exc:
            logger.warning('Telegram resmî haber alarm hatası: %s', exc)
    return sent_count

def _process_unofficial_group(state: dict, candidates: list, official_candidates: list, seen_hashes: set[str], sent_count: int, origin_label: str, send_unverified: bool, verification_rules: dict, metrics: dict[str, int] | None = None):
    for candidate in candidates:
        limit_reached = sent_count >= settings.max_news_alerts_per_scan
        item = candidate['item']
        item['score'] = candidate.get('score', item.get('score', ''))
        if origin_label == 'Sosyal':
            item['_send_unverified_social'] = send_unverified
        elif origin_label == 'OSINT':
            item['_send_unverified_osint'] = send_unverified
        _ensure_article_text(item)
        analysis = ai_client.analyze_item(item, verification_rules, verified=False)
        if analysis.get('category') == 'ignore':
            _inc_metric(metrics, 'skip_reason_not_relevant')
            _log_notification_decision('drop', item, reason='not_relevant', origin_label=origin_label)
            continue
        if not _ensure_usable_summary(item, analysis, origin_label):
            _inc_metric(metrics, 'skip_reason_no_usable_summary')
            _log_notification_decision('drop', item, reason='no_usable_summary', origin_label=origin_label)
            continue
        verified_match, overlap, match_note = _find_best_official_match(candidate, official_candidates, state, verification_rules)
        verified = bool(verified_match)

        if not verified and not send_unverified:
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=False,
                delivery_mode='digest',
                drop_reason='unverified_hold',
                meta={'origin': origin_label.lower(), 'verified': False},
                metrics=metrics,
            )
            _log_notification_decision('digest_only', item, reason='unverified_hold', origin_label=origin_label)
            continue

        if not verified and not analysis.get('should_notify'):
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=False,
                delivery_mode='digest',
                drop_reason='below_alert_threshold',
                meta={'origin': origin_label.lower(), 'verified': False},
                metrics=metrics,
            )
            _log_notification_decision('digest_only', item, reason='below_alert_threshold', origin_label=origin_label)
            continue

        if limit_reached:
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=False,
                delivery_mode='digest',
                drop_reason='scan_limit_reached',
                meta={'origin': origin_label.lower(), 'verified': verified},
                metrics=metrics,
            )
            _log_notification_decision('digest_only', item, reason='scan_limit_reached', origin_label=origin_label)
            continue

        alert_key = f"NEWS_{_alert_identity(candidate)}"
        if not should_send_alert(state, alert_key, settings.news_cooldown_seconds):
            _inc_metric(metrics, 'cooldown_drop_count')
            _inc_metric(metrics, 'skip_reason_cooldown')
            _log_notification_decision('drop', item, reason='cooldown', origin_label=origin_label, alert_key=alert_key)
            continue

        text = build_signal_message(item, candidate['score'], analysis, origin_label=origin_label, verified=verified, official_match=verified_match, overlap=overlap)
        try:
            telegram_client.send_message(text)
            mark_alert_sent(state, alert_key)
            seen_hashes.add(candidate['hash'])
            _remember_story(state, candidate)
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=True,
                delivery_mode='alert',
                meta={'origin': origin_label.lower(), 'verified': verified},
                metrics=metrics,
            )
            sent_count += 1
            if verified:
                _log_notification_decision('sent', item, origin_label=origin_label, alert_key=alert_key)
                logger.info('%s çift doğrulamalı alarm gönderildi: %s', origin_label, alert_key)
            else:
                _register_pending_unofficial(state, item, candidate, origin_label)
                _log_notification_decision('sent', item, origin_label=origin_label, alert_key=alert_key)
                logger.info('%s erken sinyal gönderildi: %s', origin_label, alert_key)
        except Exception as exc:
            logger.warning('Telegram %s alarm hatası: %s', origin_label, exc)
    return sent_count

def _process_analysis_group(state: dict, candidates: list, seen_hashes: set[str], sent_count: int, verification_rules: dict, metrics: dict[str, int] | None = None):
    for candidate in candidates:
        limit_reached = sent_count >= settings.max_news_alerts_per_scan
        item = candidate['item']
        item['score'] = candidate.get('score', item.get('score', ''))
        _ensure_article_text(item)
        analysis = ai_client.analyze_item(item, verification_rules, verified=False)

        if not _ensure_usable_summary(item, analysis, 'Analiz'):
            _inc_metric(metrics, 'skip_reason_no_usable_summary')
            _log_notification_decision('drop', item, reason='no_usable_summary', origin_label='Analiz')
            continue

        if not analysis.get('should_notify') and not analysis.get('priority_hits'):
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=False,
                delivery_mode='digest',
                drop_reason='below_alert_threshold',
                meta={'origin': 'analysis', 'verified': False},
                metrics=metrics,
            )
            _log_notification_decision('digest_only', item, reason='below_alert_threshold', origin_label='Analiz')
            continue

        if limit_reached:
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=False,
                delivery_mode='digest',
                drop_reason='scan_limit_reached',
                meta={'origin': 'analysis', 'verified': False},
                metrics=metrics,
            )
            _log_notification_decision('digest_only', item, reason='scan_limit_reached', origin_label='Analiz')
            continue

        alert_key = f"ANALYSIS_{_alert_identity(candidate)}"
        if not should_send_alert(state, alert_key, settings.news_cooldown_seconds):
            _inc_metric(metrics, 'cooldown_drop_count')
            _inc_metric(metrics, 'skip_reason_cooldown')
            _log_notification_decision('drop', item, reason='cooldown', origin_label='Analiz', alert_key=alert_key)
            continue

        text = build_analysis_message(item, candidate['score'], analysis)
        try:
            telegram_client.send_message(text)
            mark_alert_sent(state, alert_key)
            seen_hashes.add(candidate['hash'])
            _remember_story(state, candidate)
            _log_news_event(
                state,
                item,
                candidate,
                analysis,
                alert_sent=True,
                delivery_mode='alert',
                meta={'origin': 'analysis', 'verified': False},
                metrics=metrics,
            )
            sent_count += 1
            _log_notification_decision('sent', item, origin_label='Analiz', alert_key=alert_key)
            logger.info('Analiz/rapor alarmı gönderildi: %s', alert_key)
        except Exception as exc:
            logger.warning('Telegram analiz alarm hatası: %s', exc)
    return sent_count


def _candidate_to_cluster_item(candidate: dict, origin: str) -> dict:
    item = dict(candidate.get('item', {}) or {})
    item['_candidate_hash'] = candidate.get('hash')
    item['_origin'] = origin
    item['score'] = candidate.get('score', item.get('score', 0))
    if not item.get('summary'):
        item['summary'] = item.get('description') or item.get('article_text') or item.get('title') or ''
    if not item.get('url'):
        item['url'] = item.get('link', '')
    return item


def _send_cluster_alerts(state: dict, buckets: list[tuple[str, list]], seen_hashes: set[str], sent_count: int, metrics: dict[str, int] | None = None) -> tuple[int, set[str]]:
    sent_hashes = set()

    cluster_items = []
    for origin, candidates in buckets:
        for candidate in candidates:
            cluster_items.append(_candidate_to_cluster_item(candidate, origin))

    groups = group_items(cluster_items)

    for cluster, items in groups.items():
        if sent_count >= settings.max_news_alerts_per_scan:
            break

        sources = {x.get('source_name') for x in items if x.get('source_name')}
        if len(sources) < 2:
            continue

        if not should_send_cluster(cluster, items):
            for item in items:
                h = item.get('_candidate_hash')
                if h:
                    sent_hashes.add(h)
                    seen_hashes.add(h)
            _inc_metric(metrics, 'cooldown_drop_count', len(items))
            _inc_metric(metrics, 'skip_reason_cooldown', len(items))
            continue

        text = build_alert(cluster, items)

        try:
            telegram_client.send_message(text)
            sent_count += 1
            _inc_metric(metrics, 'alert_sent_count')

            for item in items:
                h = item.get('_candidate_hash')
                if h:
                    sent_hashes.add(h)
                    seen_hashes.add(h)

            logger.info('Birleştirilmiş olay alarmı gönderildi: %s | kaynak=%s | item=%s', cluster, len(sources), len(items))
        except Exception as exc:
            logger.warning('Telegram birleştirilmiş olay alarm hatası: %s', exc)

    return sent_count, sent_hashes


def _drop_sent_cluster_candidates(candidates: list, sent_hashes: set[str]) -> list:
    if not sent_hashes:
        return candidates
    return [c for c in candidates if c.get('hash') not in sent_hashes]


def process_candidates(state: dict, official_candidates: list, social_candidates: list, osint_candidates: list, analysis_candidates: list):
    active_config = load_active_config()
    verification_rules = active_config.get('verification_rules', {})
    overrides = active_config.get('overrides', {})
    send_unverified_social = overrides.get('send_unverified_social_alerts', settings.send_unverified_social_alerts)
    osint_policy = active_config.get('profile_policies', {}).get('osint', {})
    send_unverified_osint = bool(osint_policy.get('allow_unverified', True))
    seen_hashes = set(state.get('seen_news_hashes', []))
    _cleanup_pending(state)
    metrics = {
        'official_candidate_count': len(official_candidates),
        'social_candidate_count': len(social_candidates),
        'osint_candidate_count': len(osint_candidates),
        'analysis_candidate_count': len(analysis_candidates),
        'candidate_count': len(official_candidates) + len(social_candidates) + len(osint_candidates) + len(analysis_candidates),
    }

    strict_official_candidates, primary_news_candidates = _split_primary_feed_candidates(official_candidates)

    sent_count = 0

    # AI'sız olay birleştirme: aynı olayı farklı kaynaklardan yakalarsa tek alarm basar.
    sent_count, cluster_sent_hashes = _send_cluster_alerts(
        state,
        [
            ('Resmî/Kurumsal', strict_official_candidates),
            ('Haber', primary_news_candidates),
            ('Sosyal', social_candidates),
            ('OSINT', osint_candidates),
            ('Analiz', analysis_candidates),
        ],
        seen_hashes,
        sent_count,
        metrics,
    )

    strict_official_candidates = _drop_sent_cluster_candidates(strict_official_candidates, cluster_sent_hashes)
    primary_news_candidates = _drop_sent_cluster_candidates(primary_news_candidates, cluster_sent_hashes)
    social_candidates = _drop_sent_cluster_candidates(social_candidates, cluster_sent_hashes)
    osint_candidates = _drop_sent_cluster_candidates(osint_candidates, cluster_sent_hashes)
    analysis_candidates = _drop_sent_cluster_candidates(analysis_candidates, cluster_sent_hashes)

    sent_count = _process_official_candidates(state, strict_official_candidates, seen_hashes, sent_count, metrics)
    _process_official_confirmations(state, strict_official_candidates, verification_rules, metrics)
    sent_count = _process_unofficial_group(state, primary_news_candidates, strict_official_candidates, seen_hashes, sent_count, 'Haber', True, verification_rules, metrics)
    sent_count = _process_unofficial_group(state, social_candidates, strict_official_candidates, seen_hashes, sent_count, 'Sosyal', send_unverified_social, verification_rules, metrics)
    sent_count = _process_unofficial_group(state, osint_candidates, strict_official_candidates, seen_hashes, sent_count, 'OSINT', send_unverified_osint, verification_rules, metrics)
    sent_count = _process_analysis_group(state, analysis_candidates, seen_hashes, sent_count, verification_rules, metrics)

    state['seen_news_hashes'] = list(seen_hashes)[-5000:]
    state['official_signal_history'] = _trim_history(state.get('official_signal_history', []), limit=400)
    state['pending_unofficial_signals'] = _trim_history(state.get('pending_unofficial_signals', []), limit=400)
    _log_process_metrics(metrics)
