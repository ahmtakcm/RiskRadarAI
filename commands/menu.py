COMMAND_HELP_LINES = [
    "Komutlar:",
    "",
    "Sağlık:",
    "/health",
    "/source_health",
    "",
    "Audit:",
    "/audit",
    "/audit_sources",
    "/audit_policy",
    "",
    "Profil:",
    "/profiles",
    "/profile_status",
    "/policy",
    "/profile_on <profil>",
    "/profile_off <profil>",
    "/alarm_esik <profil> <puan>",
    "",
    "Arama:",
    "/ara <sorgu>",
    "/tara <sorgu>",
    "",
    "Watch:",
    "/watch",
    "/watch_ekle <kelime>",
    "/watch_sil <kelime>",
    "",
    "Kaynak:",
    "/kaynak",
    "/kaynak_ekle <ad> | <url/domain> | <profil>",
    "/kaynak_test <ad>",
    "/kaynak_sil <ad>",
    "",
    "Menü:",
    "/menu",
]


BUTTON_COMMAND_MAP = {
    "✅ Sağlık": "/health",
    "🧾 Audit": "/audit",
    "📚 Profiller": "/profiles",
    "📡 Kaynaklar": "/kaynak",
    "👁 Watch": "/watch",
    "🔎 Tara": "/tara",
    "📋 Menü": "/menu",
}


def command_help() -> str:
    return "\n".join(COMMAND_HELP_LINES)


def menu_text() -> str:
    return (
        "RiskRadarAI menü\n\n"
        "✅ Sağlık: sistem/kaynak sağlık özeti\n"
        "🧾 Audit: bildirim politikası denetimi\n"
        "📚 Profiller: profil listesi\n"
        "📡 Kaynaklar: kaynak yönetimi\n"
        "👁 Watch: izlenen kelimeler\n"
        "🔎 Tara: manuel tarama"
    )


def normalize_command_text(text: str) -> str:
    raw = str(text or "").strip()
    return BUTTON_COMMAND_MAP.get(raw, raw)
