from filters.scoring import get_risk_score
from filters.social_filter import is_social_relevant


def is_relevant_news(item, keywords: dict, social_rule: dict, min_score: int) -> bool:
    score, primary_hits, secondary_hits, pattern_hits = get_risk_score(item, keywords)
    if item.get('source_kind') == 'rss_social':
        return is_social_relevant(item, social_rule)
    if primary_hits < 1:
        return False
    if pattern_hits >= 1:
        return True
    return primary_hits >= 2 and secondary_hits >= 2 and score >= min_score
