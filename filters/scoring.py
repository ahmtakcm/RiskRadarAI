def news_text(item):
    return f"{item.get('title', '')} {item.get('description', '')}".lower()


def get_risk_score(item, keywords: dict):
    text = news_text(item)
    primary = keywords.get('primary_terms', [])
    secondary = keywords.get('secondary_terms', [])
    patterns = keywords.get('high_risk_patterns', [])
    primary_hits = sum(1 for term in primary if term in text)
    secondary_hits = sum(1 for term in secondary if term in text)
    pattern_hits = sum(1 for pattern in patterns if all(p in text for p in pattern))
    score = (primary_hits * 3) + secondary_hits + (pattern_hits * 5)
    return score, primary_hits, secondary_hits, pattern_hits
