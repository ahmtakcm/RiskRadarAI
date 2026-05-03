from __future__ import annotations

import re


def _clean(value: str) -> str:
    text = str(value or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def _extract_sentences(text: str) -> list[str]:
    text = _clean(text)
    if not text:
        return []
    parts = re.split(r'(?<=[.!?])\s+', text)
    out = []
    for part in parts:
        s = part.strip(' -–•')
        if len(s) < 30:
            continue
        out.append(s)
    return out


def build_turkish_summary(item):
    article_text = _clean(item.get('article_text', ''))
    desc = _clean(item.get('description', ''))
    title = _clean(item.get('title', ''))

    for raw in (article_text, desc):
        sentences = _extract_sentences(raw)
        if not sentences:
            continue
        chosen = []
        for sentence in sentences:
            line = sentence
            if title and line.lower().startswith(title.lower()):
                line = line[len(title):].strip(' .:-–—')
            if len(line) < 30:
                continue
            chosen.append(line)
            if len(chosen) >= 2:
                break
        if chosen:
            summary = ' '.join(chosen).strip()
            if any(ch in summary for ch in 'çğıöşüÇĞİÖŞÜ'):
                return summary[:700]
    return ''
