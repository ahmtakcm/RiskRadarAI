# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import re
from typing import Optional

_A_TAG_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*(?:[\"']([^\"']+)[\"']|([^>\s]+))[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(?:script|style|iframe)\b[^>]*>.*?</(?:script|style|iframe)>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"\s+")
_LINE_WS_RE = re.compile(r"[ \t]+")
_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLOCKQUOTE_RE = re.compile(r"<blockquote\b[^>]*>.*?</blockquote>", re.IGNORECASE | re.DOTALL)
_HR_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
_BLOCK_TAG_RE = re.compile(r"</?(?:p|div|li|ul|ol|section|article|h[1-6])\b[^>]*>", re.IGNORECASE)

_BAD_SUMMARY_PREFIXES = (
    "another plan expected", "read more", "click here",
    "follow us", "subscribe", "advertisement",
)

_URL_TOKEN_RE = re.compile(r"\b(?:https?://|www\.)\S+|\b\S+\.(?:jpg|jpeg|png|gif|webp)(?:\?\S*)?", re.IGNORECASE)
_IMAGE_URL_TOKEN_RE = re.compile(r"\b(?:https?://|www\.)\S+\.(?:jpg|jpeg|png|gif|webp)(?:\?\S*)?", re.IGNORECASE)
_HTML_NOISE_WORD_RE = re.compile(
    r"\b(?:img|src|style|twimg|pbs|jpg|jpeg|png|gif|webp|blockquote|width|height|px)\b",
    re.IGNORECASE,
)

_INCOMPLETE_ENDINGS = (
    " focuses", " focused", " includes", " including",
    " says", " said", " amid", " after", " before",
    " while", " as", " to", " of", " for", " on", " in", " with",
)

def clean_html_text(text: Optional[str]) -> str:
    if not text:
        return ""
    s = html.unescape(html.unescape(str(text)))
    s = _SCRIPT_STYLE_RE.sub(" ", s)
    s = _IMG_RE.sub(" ", s)
    s = _BR_RE.sub(" ", s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = html.unescape(html.unescape(s))
    s = _HTML_TAG_RE.sub(" ", s)
    s = _URL_TOKEN_RE.sub(" ", s)
    s = _HTML_NOISE_WORD_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def _readable_anchor(match: re.Match) -> str:
    url = html.unescape(match.group(1) or match.group(2) or "").strip()
    label = clean_html_text(match.group(3))
    if not url:
        return label
    if not label or label == url:
        return url
    return f"{label} ({url})"


def clean_telegram_text(text: Optional[str]) -> str:
    """Return user-visible plain text that is safe to place in Telegram messages."""
    if not text:
        return ""
    s = html.unescape(html.unescape(str(text)))
    s = _BLOCKQUOTE_RE.sub(" ", s)
    s = _SCRIPT_STYLE_RE.sub(" ", s)
    s = _BLOCKQUOTE_RE.sub(" ", s)
    s = _IMG_RE.sub(" ", s)
    s = _HR_RE.sub("\n", s)
    s = _BR_RE.sub("\n", s)
    s = _BLOCK_TAG_RE.sub("\n", s)
    s = _A_TAG_RE.sub(_readable_anchor, s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = html.unescape(html.unescape(s))
    s = _SCRIPT_STYLE_RE.sub(" ", s)
    s = _BLOCKQUOTE_RE.sub(" ", s)
    s = _IMG_RE.sub(" ", s)
    s = _A_TAG_RE.sub(_readable_anchor, s)
    s = _HTML_TAG_RE.sub(" ", s)
    s = _IMAGE_URL_TOKEN_RE.sub(" ", s)
    s = _HTML_NOISE_WORD_RE.sub(" ", s)
    lines = [_LINE_WS_RE.sub(" ", line).strip() for line in s.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()

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
    return text or ""

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
        return turkish_fallback_summary(title=title, source=source, topic=topic)

    return cleaned
