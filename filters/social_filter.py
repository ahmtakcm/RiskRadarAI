from filters.scoring import news_text


def is_social_relevant(item, rule: dict) -> bool:
    text = news_text(item)
    required_any = rule.get('required_any', [])
    blocked_terms = rule.get('blocked_terms', [])
    minimum_hits = int(rule.get('minimum_term_hits', 2))
    term_pool = set(required_any + rule.get('extra_terms', []))

    if any(term in text for term in blocked_terms):
        return False
    if required_any and not any(term in text for term in required_any):
        return False

    hits = sum(1 for term in term_pool if term in text)
    return hits >= minimum_hits
