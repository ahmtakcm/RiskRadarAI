from __future__ import annotations

from typing import Tuple

from enrichers.text_hygiene import normalize_content_item, clean_telegram_text
from services import groq_service, github_models_service, gemini_service


def translate_official_item(item: dict) -> Tuple[str, str]:
    """Unified translation pipeline: normalize then translate to Turkish.

    Tries a consistent provider order (groq -> gemini -> github_models) and
    returns cleaned `title_tr`, `text_tr` strings. This avoids per-source
    branching in callers.
    """
    normalize_content_item(item)

    # Try groq_service first (has explicit translate prompt rules)
    for provider in (groq_service, gemini_service, github_models_service):
        try:
            if hasattr(provider, 'translate_official_item') and provider.is_enabled():
                res = provider.translate_official_item(item)
                if res:
                    title = str(res.get('title_tr', '') or '').strip()
                    text = str(res.get('text_tr', '') or '').strip()
                    if title or text:
                        return clean_telegram_text(title), clean_telegram_text(text)
        except Exception:
            continue

    # Fallback: use existing fields
    raw_text = str(item.get('article_text') or item.get('description') or '').strip()
    return clean_telegram_text(str(item.get('title', '')).strip()), clean_telegram_text(raw_text[:8000])
