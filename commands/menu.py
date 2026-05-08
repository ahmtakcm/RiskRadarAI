MENU_TEXT = """RiskRadarAI men?

? /health   - Sistem/kaynak sa?l?k ?zeti
?? /audit    - Bildirim politikas? denetimi
?? /profiles - Profil listesi/durumu
?? /sources  - Kaynak y?netimi
?? /watch    - ?zlenen kelimeler
?? /ara      - Resm?/profil arama
?? /tara     - Manuel t?m kaynak tarama
?? /digest_now - Sessiz digest ?imdi
"""

ALIAS_COMMAND_MAP = {
    "/start": "/menu",
    "/help": "/menu",
    "/menu": "/menu",

    "/profiles": "/profiles",
    "/profile": "/profiles",

    "/audit": "/audit",
    "/audit_json": "/audit_json",

    "/sources": "/sources",
    "/source": "/sources",

    "/watch": "/watch",

    "/scan": "/tara",
    "/ara": "/ara",
    "/tara": "/tara",

    "/health": "/health",
    "/health_json": "/health_json",
    "/source_health": "/source_health",
    "/kaynak_saglik": "/kaynak_saglik",
    "/digest_now": "/digest_now",
}

BUTTON_COMMAND_MAP = {
    "✅ Sağlık": "/health",
    "🧾 Audit": "/audit",
    "📚 Profiller": "/profiles",
    "📡 Kaynaklar": "/sources",
    "👁 Watch": "/watch",
    "🔎 Tara": "/scan",
}


def normalize_command_text(text: str) -> str:
    if not text:
        return ""
    stripped = text.strip()
    parts = stripped.split(maxsplit=1)
    cmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""
    mapped = ALIAS_COMMAND_MAP.get(cmd, cmd)
    return f"{mapped} {rest}".strip()


def menu_text() -> str:
    return MENU_TEXT


def render_menu() -> str:
    return MENU_TEXT


def command_help() -> str:
    return MENU_TEXT
