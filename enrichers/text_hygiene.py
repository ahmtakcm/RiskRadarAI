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

_ENGLISH_TITLE_HINT_RE = re.compile(
    r"\b(?:"
    r"the|and|after|before|amid|says|said|will|could|would|"
    r"attack|attacks|strike|strikes|war|conflict|talks|published|"
    r"comments|update|release|releases|launch|launches|decision|rate|"
    r"blockade|warning|statement|minister|president|footage|tunnel|"
    r"infrastructure|security|maritime|traffic|shipping|oil|routes|near"
    r")\b",
    re.IGNORECASE,
)

_GENERIC_SUMMARY_RE = re.compile(
    r"(?:iran|dünya|hürmüz hattı) gündemine ilişkin (?:resmi )?açıklama yaptı",
    re.IGNORECASE,
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
        " of ", " in ", " releases ", " footage", " infrastructure",
        " war", " conflict", " attack", " strike", " talks",
    ))


def looks_like_raw_english_title(text: Optional[str]) -> bool:
    s = clean_html_text(text)
    if not s:
        return False
    if is_probably_english(s):
        return True
    if any(ch in s for ch in "çğıöşüÇĞİÖŞÜ"):
        return False
    words = re.findall(r"[A-Za-z']+", s)
    if len(words) < 2:
        return False
    return bool(_ENGLISH_TITLE_HINT_RE.search(s))


def _official_subject(source: str) -> str:
    low = source.lower()
    compact = re.sub(r"[^a-z0-9]+", "", low)
    if "statedept" in compact or ("state" in low and "dept" in low):
        return "ABD Dışişleri"
    if "whitehouse" in compact or "white house" in low:
        return "Beyaz Saray"
    if "centcom" in compact:
        return "CENTCOM"
    if "nato" in compact:
        return "NATO"
    if "idf" in compact or "israel defense" in low:
        return "IDF"
    if "russia" in low and ("mfa" in low or "foreign" in low):
        return "Rusya Dışişleri"
    if "treasury" in low:
        return "ABD Hazine Bakanlığı"
    if "federalreserve" in compact or compact == "fed" or "federal reserve" in low:
        return "Fed"
    if "ecb" in compact or "european central bank" in low:
        return "ECB"
    if "tcmb" in compact:
        return "TCMB"
    if "presidency" in low or "cumhurbaskan" in low:
        return "Cumhurbaşkanlığı"
    return source.strip()


def _concise_official_fallback(title: str, source: str, topic: str = "") -> str:
    subject = _official_subject(source) or "Resmi kaynak"
    text = clean_html_text(title)
    low = f" {text.lower()} "

    if "nato" in subject.lower() and any(x in low for x in (" exercise", " drill", " submarine", " anti-submarine")):
        if any(x in low for x in (" north", " northern", " arctic", " baltic")) and "submarine" in low:
            return "NATO, kuzey bölgelerinde denizaltı savaşı tatbikatı başlattı."
        return "NATO, askeri tatbikata ilişkin resmi açıklama yaptı."

    if subject == "IDF" and any(x in low for x in ("hezbollah", "hizbullah")):
        if any(x in low for x in (" tunnel", " infrastructure", " footage", " video", " image")):
            return "IDF Güney Lübnan’daki Hizbullah altyapısına ilişkin görüntü paylaştı."
        return "IDF, Hizbullah bağlantılı güvenlik gelişmesine ilişkin açıklama yaptı."

    if subject == "Rusya Dışişleri" and any(x in low for x in (" kiev", " kyiv")):
        if any(x in low for x in (" strike", " attack", " military")):
            return "Rusya Dışişleri, Kiev’e yönelik yeni askeri adımlar konusunda açıklama yaptı."
        return "Rusya Dışişleri, Kiev gündemine ilişkin resmi açıklama yaptı."

    topic_phrase = ""
    if "hormuz" in low:
        topic_phrase = "Hürmüz hattı"
    elif "iran" in low:
        topic_phrase = "İran"
    elif "gaza" in low:
        topic_phrase = "Gazze"
    elif "hezbollah" in low or "hizbullah" in low:
        topic_phrase = "Hizbullah"
    elif "ukraine" in low:
        topic_phrase = "Ukrayna"
    elif "kiev" in low or "kyiv" in low:
        topic_phrase = "Kiev"
    elif "sanction" in low:
        topic_phrase = "yaptırımlar"
    elif "ceasefire" in low:
        topic_phrase = "ateşkes"
    elif "fomc" in low or " rate" in low:
        topic_phrase = "faiz kararı"
    elif topic:
        topic_phrase = clean_html_text(topic)

    if "sanction" in low:
        return f"{subject}, yaptırımlara ilişkin yeni karar açıkladı."
    if "blockade" in low and topic_phrase:
        return f"{subject}, {topic_phrase} konusunda uyarı yaptı."
    if any(x in low for x in (" exercise", " drill")):
        return f"{subject}, askeri tatbikata ilişkin resmi açıklama yaptı."
    if any(x in low for x in (" talk", " talks", " meeting", " negotiation")) and topic_phrase:
        return f"{subject} {topic_phrase} görüşmelerine ilişkin açıklama yaptı."
    if any(x in low for x in (" warn", " warning", " alert")) and topic_phrase:
        return f"{subject}, {topic_phrase} konusunda uyarı yaptı."
    if any(x in low for x in (" confirm", " confirmed")) and topic_phrase:
        return f"{subject}, {topic_phrase} başlığındaki gelişmeyi doğruladı."
    if any(x in low for x in (" footage", " video", " image", " photo")) and topic_phrase:
        return f"{subject}, {topic_phrase} başlığına ilişkin görüntü paylaştı."
    if topic_phrase:
        return f"{subject}, {topic_phrase} gündemine ilişkin resmi açıklama yaptı."
    return f"{subject}, resmi gündeme ilişkin kısa açıklama yaptı."


def turkish_fallback_summary(
    title: Optional[str] = None,
    source: Optional[str] = None,
    topic: Optional[str] = None,
) -> str:
    clean_title = clean_html_text(title)
    clean_source = clean_html_text(source)
    clean_topic = clean_html_text(topic)

    if clean_title and looks_like_raw_english_title(clean_title):
        return _concise_official_fallback(clean_title, clean_source, clean_topic)

    if clean_title:
        if clean_source:
            return f"{clean_source} kaynağı, “{clean_title}” başlığıyla gelişmeyi aktardı."
        return f"“{clean_title}” başlığıyla yeni bir gelişme aktarıldı."

    if clean_source:
        subject = _official_subject(clean_source)
        return f"{subject}, resmi gündeme ilişkin kısa açıklama yaptı."

    if clean_topic:
        return f"{clean_topic} başlığı altında yeni bir gelişme tespit edildi."

    return "Gelişmeye ilişkin haber akışında yeni bir kayıt tespit edildi."

def simple_tr_rewrite(text: str) -> str:
    return text or ""


def is_generic_summary(text: Optional[str]) -> bool:
    cleaned = clean_html_text(text)
    return bool(cleaned and _GENERIC_SUMMARY_RE.search(cleaned))

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
