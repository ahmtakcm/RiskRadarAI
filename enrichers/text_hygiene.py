# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import re
from typing import Optional

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

_BAD_SUMMARY_PREFIXES = (
    "another plan expected", "read more", "click here",
    "follow us", "subscribe", "advertisement",
)

_INCOMPLETE_ENDINGS = (
    " focuses", " focused", " includes", " including",
    " says", " said", " amid", " after", " before",
    " while", " as", " to", " of", " for", " on", " in", " with",
)

def clean_html_text(text: Optional[str]) -> str:
    if not text:
        return ""
    s = str(text)
    s = _IMG_RE.sub(" ", s)
    s = _BR_RE.sub(" ", s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = html.unescape(html.unescape(s))
    return _WS_RE.sub(" ", s).strip()

def looks_incomplete_summary(text: Optional[str]) -> bool:
    s = clean_html_text(text)
    if not s:
        return True
    low = s.lower()
    if len(s) < 35:
        return True
    if any(low.startswith(p) for p in _BAD_SUMMARY_PREFIXES):
        return True
    if any(low.endswith(e) for e in _INCOMPLETE_ENDINGS):
        return True
    if len(s) < 90 and s[-1] not in ".!?…":
        return True
    return False

def is_probably_english(text: Optional[str]) -> bool:
    s = clean_html_text(text)
    if not s:
        return False
    low = f" {s.lower()} "
    if any(ch in low for ch in "ıüğşöç"):
        return False
    return any(x in low for x in (
        " the ", " and ", " after ", " before ", " amid ",
        " says ", " said ", " will ", " could ", " would ",
        " war", " conflict", " attack", " strike", " talks",
    ))

def turkish_fallback_summary(
    title: Optional[str] = None,
    source: Optional[str] = None,
    topic: Optional[str] = None,
) -> str:
    clean_title = clean_html_text(title)
    clean_source = clean_html_text(source)
    clean_topic = clean_html_text(topic)

    if clean_title:
        if clean_source:
            return f"{clean_source} kaynağı, “{clean_title}” başlığıyla gelişmeyi aktardı."
        return f"“{clean_title}” başlığıyla yeni bir gelişme aktarıldı."

    if clean_topic:
        return f"{clean_topic} başlığı altında yeni bir gelişme tespit edildi."

    return "Gelişmeye ilişkin haber akışında yeni bir kayıt tespit edildi."

def simple_tr_rewrite(text: str) -> str:
    if not text:
        return ""

    replacements = [
        ("United States", "ABD"),
        ("U.S.", "ABD"),
        ("US", "ABD"),
        ("Iranian", "İranlı"),
        ("Iran", "İran"),
        ("Strait of Hormuz", "Hürmüz Boğazı"),
        ("Hormuz", "Hürmüz"),
        ("naval blockade", "deniz ablukası"),
        ("blockade", "abluka"),
        ("shadow fleet", "gölge filo"),
        ("fake flags", "sahte bayraklar"),
        ("dark ships", "takip sistemlerini kapatan gemiler"),
        ("ceasefire", "ateşkes"),
        ("Defense Ministry", "Savunma Bakanlığı"),
        ("lawmakers", "milletvekilleri"),
        ("attacks", "saldırılar"),
        ("killed", "öldürüldü"),
        ("war", "savaş"),
        ("conflict", "çatışma"),
    ]

    out = text
    for en, tr in replacements:
        out = out.replace(en, tr)
    return out

def improve_summary_text(
    summary: Optional[str],
    title: Optional[str] = None,
    source: Optional[str] = None,
    topic: Optional[str] = None,
    force_turkish_fallback_for_english: bool = True,
) -> str:
    cleaned = clean_html_text(summary)

    if looks_incomplete_summary(cleaned):
        return turkish_fallback_summary(title=title, source=source, topic=topic)

    if force_turkish_fallback_for_english and is_probably_english(cleaned):
        rewritten = simple_tr_rewrite(cleaned)
        if rewritten:
            return rewritten
        return turkish_fallback_summary(title=title, source=source, topic=topic)

    return cleaned
