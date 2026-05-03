from core.matching import tokenize_text

HIGH_SECURITY_TERMS = {
    'nuclear', 'uranium', 'missile', 'asat', 'mobilization', 'mobilisation', 'intikal',
    'meb', 'eez', 'ambargo', 'embargo', 'blockade', 'boğaz', 'closure', 'cross-border',
    'sınır', 'operation', 'strike', 'airstrike', 'drone', 'siha', 'mine clearance', 'centcom',
    'attack', 'saldırı', 'saldiri', 'shipping disruption', 'maritime traffic', 'hormuz'
}
HIGH_MARKET_TERMS = {
    'oil', 'brent', 'gas', 'lng', 'gold', 'usdtry', 'usd/try', 'tariff', 'sanction',
    'sanctions', 'swift', 'opec', 'fomc', 'federal', 'reserve', 'ecb', 'tcmb', 'imf',
    'liquidity', 'rate', 'inflation', 'bond', 'yield', 'dollar', 'hormuz', 'port', 'ports',
    'wti', 'closure', 'shipping disruption'
}
LOW_VALUE_TERMS = {
    'congratulations', 'birthday', 'ceremony', 'visit', 'meeting', 'speech', 'interview',
    'opinion', 'commentary', 'podcast', 'anniversary', 'greeting', 'protocol', 'courtesy',
    'etkinlik', 'ziyaret', 'tören', 'nezaket', 'makam ziyareti', 'liman ziyareti'
}
ROUTINE_TERMS = {
    'visit', 'ziyaret', 'courtesy', 'protocol', 'protokol', 'ceremony', 'tören',
    'event', 'etkinlik', 'hosted', 'received', 'meeting', 'görüşme', 'makam ziyareti',
    'liman ziyareti', 'nezaket', 'karşılama', 'welcome', 'port visit'
}
CRITICAL_OFFICIAL_TERMS = {
    'blockade', 'abluka', 'strike', 'strikes', 'attack', 'missile', 'sanction',
    'sanctions', 'centcom', 'hormuz', 'strait of hormuz', 'shipping disruption',
    'port closure', 'maritime traffic', 'closure', 'iranian ports'
}


def _clamp_score(score: int, pre_class: str) -> int:
    caps = {
        'suppress': 24,
        'info_war_watch': 39,
        'digest': 59,
        'core_alert': 100,
    }
    return max(0, min(int(score), caps.get(pre_class, 100)))


def _level_label(score: int) -> str:
    if score <= 24:
        return 'Bilgi'
    if score <= 49:
        return 'İzleme'
    if score <= 69:
        return 'Önemli'
    if score <= 84:
        return 'Yüksek'
    return 'Kritik'


def _header_for(confirmation_class: str, pre_class: str) -> str:
    if confirmation_class == 'official_confirmed':
        return '🚨 RESMÎ ALARM'
    if confirmation_class == 'official_parallel':
        return '⚠️ RESMÎ PARALEL'
    if confirmation_class == 'media_verified':
        return '📰 GÜÇLÜ MEDYA'
    if pre_class == 'suppress':
        return 'ℹ️ BİLGİ'
    if pre_class == 'info_war_watch':
        return '🧭 İZLEME'
    if pre_class == 'digest':
        return '🗞️ ÖNEMLİ GELİŞME'
    return '🚨 ALARM'


def analyze_signal(item: dict, verification_rules: dict | None = None) -> dict:
    verification_rules = verification_rules or {}
    text = ' '.join([
        item.get('title', ''),
        item.get('description', ''),
        item.get('article_text', '')
    ]).lower()

    tokens = set(tokenize_text(text))
    high_priority_terms = set(t.lower() for t in verification_rules.get('high_priority_terms', []))

    security_hits = {t for t in HIGH_SECURITY_TERMS if t in text or t in tokens}
    market_hits = {t for t in HIGH_MARKET_TERMS if t in text or t in tokens}
    priority_hits = {t for t in high_priority_terms if t and t in text}
    low_value_hits = {t for t in LOW_VALUE_TERMS if t in text}
    routine_hits = set(item.get('routine_hits', []) or []) | {t for t in ROUTINE_TERMS if t in text}

    official_keyword_hits = set(item.get('official_keyword_hits', []) or [])
    official_entity_hits = set(item.get('official_entity_hits', []) or [])
    official_hits = official_keyword_hits | official_entity_hits

    official_source = bool(item.get('is_official_source'))
    official_red_alert = bool(item.get('official_red_alert_source'))
    trusted_media_source = bool(item.get('trusted_media_source'))
    is_official_routine = bool(item.get('is_official_routine'))

    source_kind = str(item.get('source_kind', '') or '').lower()

    high_signal = bool(
        priority_hits
        or len(security_hits) >= 2
        or len(market_hits) >= 3
        or (official_hits & CRITICAL_OFFICIAL_TERMS)
    )

    if official_red_alert and not is_official_routine and (official_hits or security_hits or priority_hits):
        confirmation_class = 'official_confirmed'
    elif official_source and not is_official_routine and (official_hits or security_hits or market_hits or priority_hits):
        confirmation_class = 'official_parallel'
    elif trusted_media_source and (security_hits or market_hits or priority_hits or official_hits):
        confirmation_class = 'media_verified'
    else:
        confirmation_class = 'analysis_inferred'

    if is_official_routine or (routine_hits and not high_signal and not official_hits):
        pre_class = 'suppress'
    elif confirmation_class == 'official_confirmed':
        pre_class = 'core_alert'
    elif confirmation_class == 'official_parallel':
        pre_class = 'core_alert' if high_signal or official_hits else 'digest'
    elif confirmation_class == 'media_verified':
        pre_class = 'digest'
    else:
        if source_kind == 'analysis' or low_value_hits:
            pre_class = 'info_war_watch'
        elif high_signal or security_hits or market_hits:
            pre_class = 'digest'
        else:
            pre_class = 'info_war_watch'

    score = 0
    if confirmation_class == 'official_confirmed':
        score += 78
    elif confirmation_class == 'official_parallel':
        score += 58
    elif confirmation_class == 'media_verified':
        score += 44
    else:
        score += 26

    score += min(12, len(priority_hits) * 6)
    score += min(12, len(security_hits) * 4)
    score += min(10, len(market_hits) * 3)
    score += min(12, len(official_hits) * 6)

    if trusted_media_source:
        score += 4
    if official_source and not is_official_routine:
        score += 6
    if low_value_hits:
        score -= 8
    if routine_hits:
        score -= 18
    if source_kind == 'analysis' and confirmation_class == 'analysis_inferred':
        score -= 4

    alarm_score = _clamp_score(score, pre_class)
    level_label = _level_label(alarm_score)
    confidence = max(0.10, min(0.99, alarm_score / 100.0))

    if pre_class == 'suppress':
        category = 'ignore'
        should_notify = False
    elif pre_class == 'core_alert':
        category = 'verified_alert' if confirmation_class == 'official_confirmed' else 'early_signal'
        should_notify = True
    else:
        category = 'watch'
        should_notify = alarm_score >= 25 or confirmation_class in {'official_parallel', 'media_verified'}

    market_impact = 'Düşük/Belirsiz'
    if {'oil', 'brent', 'wti', 'hormuz', 'swift'} & (market_hits | official_hits):
        market_impact = 'Yüksek' if pre_class == 'core_alert' else 'Orta'
    elif market_hits:
        market_impact = 'Orta'

    security_impact = 'Düşük/Belirsiz'
    if {'blockade', 'strike', 'attack', 'missile', 'centcom', 'hormuz'} & (security_hits | official_hits | priority_hits):
        security_impact = 'Yüksek' if pre_class == 'core_alert' else 'Orta'
    elif security_hits or official_entity_hits:
        security_impact = 'Orta'

    return {
        'category': category,
        'pre_class': pre_class,
        'confirmation_class': confirmation_class,
        'header': _header_for(confirmation_class, pre_class),
        'should_notify': should_notify,
        'confidence': confidence,
        'alarm_score': alarm_score,
        'level_label': level_label,
        'market_impact': market_impact,
        'security_impact': security_impact,
        'security_hits': sorted(security_hits | priority_hits | official_keyword_hits | official_entity_hits),
        'market_hits': sorted(market_hits | official_keyword_hits),
        'priority_hits': sorted(priority_hits | official_keyword_hits | official_entity_hits),
        'official_red_alert': official_red_alert,
        'is_routine': bool(routine_hits) or is_official_routine,
        'routine_hits': sorted(routine_hits),
    }
