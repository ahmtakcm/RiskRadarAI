from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommandDef:
    """Single source of truth for a Telegram command.

    Fields:
        command:      Canonical name (without leading /), e.g. "menu".
        description:  Short description for Telegram Bot API /setMyCommands.
        admin_only:   If True, visible only in admin private chat scope.
        visible_in_menu: If True, appears in the /menu output.
        aliases:      Alternative names that route to this command (no /).
        legacy_redirects: Old command names that show a "removed" warning.
    """

    command: str
    description: str
    admin_only: bool = False
    visible_in_menu: bool = True
    aliases: list[str] = field(default_factory=list)
    legacy_redirects: list[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# SINGLE SOURCE OF TRUTH
# Every command the bot understands lives here.
# Add new commands here, not in separate hardcoded lists.
# ──────────────────────────────────────────────
REGISTRY: list[CommandDef] = [
    # --- Menu / navigation ---
    CommandDef("menu", "Ana menü", aliases=["start", "help", "komutlar", "yardim"]),

    # --- Profile management (public) ---
    CommandDef(
        "profiles",
        "Profil listesi",
        aliases=["profil_liste"],
        legacy_redirects=[
            "profil_tum",
            "profil_resmi",
            "profil_haber",
            "profil_ekonomi",
            "profil_osint",
            "profil_saglik",
            "profil",
        ],
    ),
    CommandDef("profile_status", "Aktif profil ve eşik özeti", aliases=["profil_durum"]),
    CommandDef("profile_sources", "Profil kaynak özeti: /profile_sources <id>"),
    CommandDef("profile_on", "Profil aç: /profile_on <id>", aliases=["profil_on"]),
    CommandDef("profile_off", "Profil kapat: /profile_off <id>", aliases=["profil_off"]),
    CommandDef("alarm_esik", "Alarm eşiği: /alarm_esik <id> <sayı>"),
    CommandDef("policy", "Policy özeti", aliases=["modes"]),

    # --- Search / scan (public) ---
    CommandDef("ara", "Hızlı arama: /ara <profil?> <sorgu>"),
    CommandDef("tara", "Manuel tarama: /tara <profil?> <24s|sorgu>"),

    # --- Health / audit (public) ---
    CommandDef("health", "Sistem sağlık özeti"),
    CommandDef("source_health", "Kaynak sorun özeti", aliases=["kaynak_saglik"]),
    CommandDef("audit", "Bildirim politikası denetimi"),

    # --- Source management (public) ---
    CommandDef("kaynak", "Kaynak komutları"),
    CommandDef("kaynak_test", "Kaynak test et"),
    CommandDef("kaynak_ekle", "Yeni kaynak ekle"),
    CommandDef("kaynak_sil", "Kaynak sil"),

    # --- Admin-only ---
    CommandDef("digest_now", "Özet bildirimi gönder", admin_only=True),
]


# ──────────────────────────────────────────────
# Derived maps — generated at import time.
# These replace the hardcoded dicts in menu.py.
# ──────────────────────────────────────────────

ALIAS_MAP: dict[str, str] = {}
"""Maps alias name (no /) → canonical command name (no /).

Example: "start" → "menu", "profil_liste" → "profiles"
"""

LEGACY_REDIRECT_MAP: dict[str, str] = {}
"""Maps legacy command name (no /) → canonical command name (no /).

Example: "profil_tum" → "profiles"
"""

ADMIN_COMMANDS: set[str] = set()
"""Set of admin-only canonical command names (no /).

Example: {"digest_now"}
"""

MENU_COMMANDS: list[tuple[str, str]] = []
"""Ordered list of (command_with_slash, description) for /menu display.

Includes only commands with visible_in_menu=True and admin_only=False.
"""

for cmd in REGISTRY:
    name = cmd.command
    if cmd.admin_only:
        ADMIN_COMMANDS.add(name)
    for alias in cmd.aliases:
        ALIAS_MAP[alias] = name
    for legacy in cmd.legacy_redirects:
        LEGACY_REDIRECT_MAP[legacy] = name
    if cmd.visible_in_menu and not cmd.admin_only:
        MENU_COMMANDS.append((f"/{name}", cmd.description))


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def public_payload() -> list[dict[str, str]]:
    """Build the list of dicts for setMyCommands default scope.

    Returns only non-admin commands.
    """
    return [
        {"command": c.command, "description": c.description}
        for c in REGISTRY
        if not c.admin_only
    ]


def admin_payload() -> list[dict[str, str]]:
    """Build the list of dicts for admin chat scope.

    Includes all commands (public + admin-only).
    """
    return [
        {"command": c.command, "description": c.description}
        for c in REGISTRY
    ]


def build_menu_text() -> str:
    """Generate the /menu help text from MENU_COMMANDS."""
    lines = ["RiskRadarAI komut menüsü", ""]
    for cmd, desc in MENU_COMMANDS:
        lines.append(f"{cmd} - {desc}")
    return "\n".join(lines)


def build_alias_map() -> dict[str, str]:
    """Return ALIAS_MAP — maps alias name (no /) → canonical command name (no /)."""
    return dict(ALIAS_MAP)


def build_legacy_redirect_map() -> dict[str, str]:
    """Return LEGACY_REDIRECT_MAP — maps legacy name (no /) → canonical name (no /)."""
    return dict(LEGACY_REDIRECT_MAP)