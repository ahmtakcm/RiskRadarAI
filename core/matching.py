import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

STOPWORDS = {
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'into', 'over', 'under', 'about',
    'official', 'statement', 'news', 'update', 'press', 'release', 'releases', 'briefing',
    'minister', 'president', 'government', 'announces', 'announced', 'says', 'will', 'after',
    'amid', 'world', 'global', 'international', 'today', 'new', 'report', 'reports', 'event',
    'iran', 'russia', 'ukraine', 'israel', 'gaza', 'turkiye', 'turkish', 'middle', 'east'
}


def now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def parse_time_to_ts(value: str) -> float | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass
    try:
        value = value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def tokenize_text(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9çğıöşüÇĞİÖŞÜ-]{3,}", (text or '').lower())
    tokens = set()
    for word in words:
        clean = word.strip('-')
        if not clean or clean in STOPWORDS:
            continue
        if clean.isdigit():
            continue
        tokens.add(clean)
    return tokens


def build_topic_tokens(item: dict, tracked_terms: Iterable[str] | None = None) -> set[str]:
    text = ' '.join([item.get('title', ''), item.get('description', '')])
    tokens = tokenize_text(text)
    if tracked_terms:
        lower_text = text.lower()
        for term in tracked_terms:
            term = term.strip().lower()
            if term and term in lower_text:
                tokens.add(term)
    return tokens


def topic_overlap(left: set[str], right: set[str]) -> set[str]:
    return left & right
