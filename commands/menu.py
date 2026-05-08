COMMAND_HELP_LINES = [
    "Komutlar:",
    "",
    "Sağlık:",
    "/health",
    "/source_health",
    "/kaynak_saglik",
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
    "/profile_policy",
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
    "/kaynak_yardim",
    "/kaynak_ekle <ad> | <url/domain> | <profil>",
    "/kaynak_test <ad>",
    "/kaynak_sil <ad>",
    "",
    "Kontrol:",
    "/feed_kontrol",
    "",
    "Menü:",
    "/menu",
    "/komutlar",
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


ALIAS_COMMAND_MAP = {
    "/komutlar": "/menu",
    "komutlar": "/menu",
    "/yardim": "/menu",
    "/yardım": "/menu",
    "yardim": "/menu",
    "yardım": "/menu",
    "/profile_policy": "/policy",
    "/profil_policy": "/policy",
    "/profil_durum": "/profile_status",
    "/profil_liste": "/profiles",
    "/kaynak_saglik": "/source_health",
    "/kaynak_sağlık": "/source_health",
    "/source_health": "/source_health",
    "/kaynak_yardim": "/kaynak",
    "/kaynak_yardım": "/kaynak",
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
    if raw in BUTTON_COMMAND_MAP:
        return BUTTON_COMMAND_MAP[raw]
    if raw in ALIAS_COMMAND_MAP:
        return ALIAS_COMMAND_MAP[raw]

    lowered = raw.lower()
    if "sağlık" in lowered or "saglik" in lowered:
        return "/health"
    if "audit" in lowered:
        return "/audit"
    if "profil" in lowered:
        return "/profiles"
    if "kaynak" in lowered:
        return "/kaynak"
    if "watch" in lowered:
        return "/watch"
    if "tara" in lowered:
        return "/tara"
    if "menü" in lowered or "menu" in lowered or "komut" in lowered:
        return "/menu"

    return raw
