from __future__ import annotations

QUERY_ALIASES = {
    "h?rm?z": ["hormuz", "strait of hormuz"],
    "hurmuz": ["hormuz", "strait of hormuz"],
    "hormuz": ["hormuz", "strait of hormuz"],
    "faiz": ["interest rate", "rate decision", "policy rate", "central bank rate"],
    "petrol": ["oil", "crude", "brent"],
    "tanker": ["tanker", "oil tanker"],
    "abluka": ["blockade"],
    "k?rfez": ["gulf", "gulf of oman", "persian gulf"],
    "korfez": ["gulf", "gulf of oman", "persian gulf"],
    "sava? gemisi": ["warship", "destroyer", "naval vessel"],
    "savas gemisi": ["warship", "destroyer", "naval vessel"],
    "f?ze": ["missile"],
    "fuze": ["missile"],
    "sald?r?": ["attack", "strike"],
    "saldiri": ["attack", "strike"],
    "yapt?r?m": ["sanction", "sanctions"],
    "yaptirim": ["sanction", "sanctions"],
    "merkez bankas?": ["central bank", "monetary policy"],
    "merkez bankasi": ["central bank", "monetary policy"],
    "enflasyon": ["inflation", "cpi"],
}


def expand_query_terms(query: str) -> list[str]:
    text = str(query or "").strip().lower()
    if not text:
        return []
    terms: list[str] = []

    def add(value: str):
        value = str(value or "").strip().lower()
        if value and value not in terms:
            terms.append(value)

    add(text)
    for part in text.split():
        if len(part) >= 3:
            add(part)

    for alias, expansions in QUERY_ALIASES.items():
        if alias == text or alias in text or alias in terms:
            for expansion in expansions:
                add(expansion)

    return terms
