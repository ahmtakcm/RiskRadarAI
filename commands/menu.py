MENU_TEXT = """RiskRadarAI menü

✅ /health       - Sistem/kaynak sağlık özeti
🧾 /audit        - Bildirim politikası denetimi
📚 /profiles     - Profil listesi/durumu
📡 /sources      - Kaynak yönetimi
👁 /watch        - İzlenen kelimeler
🔎 /ara          - Resmî/profil arama
🛰 /tara         - Manuel tüm kaynak tarama
🧩 /policy       - Profil bildirim politikaları
⚙️ /alarm_esik   - Profil alarm eşiği ayarla
📰 /digest_now   - Sessiz digest şimdi

Örnekler:
- /profiles
- /profile_on ekonomi
- /profile_off osint
- /alarm_esik ekonomi 30
- /ara ekonomi faiz
- /tara osint 24s
"""

ALIAS_COMMAND_MAP = {
    "/start": "/menu",
    "/help": "/menu",
    "/menu": "/menu",

    "/profiles": "/profiles",
    "/profile": "/profiles",
    "/profile_status": "/profile_status",
    "/profile_on": "/profile_on",
    "/profile_off": "/profile_off",

    "/policy": "/policy",
    "/alarm_esik": "/alarm_esik",

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
