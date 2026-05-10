MENU_TEXT = """RiskRadarAI komut menüsü

/health - Sistem ve kaynak sağlık özeti
/audit - Bildirim politikası denetimi
/source_health - Kaynak sorun özeti
/profiles - Profil listesi
/profile_status - Aktif profil ve eşik özeti
/profile_sources <profil> - Profil kaynak özeti
/profile_on <profil> - Profil aç
/profile_off <profil> - Profil kapat
/ara <profil/konu> - Hızlı arama
/tara <profil/konu> [süre] - Manuel tarama
"""

LEGACY_COMMAND_REDIRECTS = {
    "/profil": "/profiles",
    "/profil_tum": "/profiles",
    "/profil_on": "/profile_on",
    "/profil_off": "/profile_off",
    "/policy": "/audit",
    "/modes": "/profiles",
}

ALIAS_COMMAND_MAP = {
    "/start": "/menu",
    "/help": "/menu",
    "/menu": "/menu",
    "/profiles": "/profiles",
    "/profile_status": "/profile_status",
    "/profile_sources": "/profile_sources",
    "/profile_on": "/profile_on",
    "/profile_off": "/profile_off",
    "/audit": "/audit",
    "/health": "/health",
    "/source_health": "/source_health",
    "/ara": "/ara",
    "/tara": "/tara",
}

BUTTON_COMMAND_MAP = {
    "✅ Sağlık": "/health",
    "🧾 Audit": "/audit",
    "📚 Profiller": "/profiles",
    "🔎 Ara": "/ara",
    "🔎 Tara": "/tara",
}


def legacy_command_message(command: str) -> str | None:
    mapped = LEGACY_COMMAND_REDIRECTS.get(str(command or "").strip().split()[0].lower())
    if not mapped:
        return None
    return f"⚠️ Bu komut kaldırıldı. Yeni komut: {mapped}\n\n{MENU_TEXT}"


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
