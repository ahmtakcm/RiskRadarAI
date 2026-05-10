from commands.registry import (
    REGISTRY,
    build_alias_map,
    build_legacy_redirect_map,
    build_menu_text,
)

# ──────────────────────────────────────────────
# Generated maps — driven by commands/registry.py
# ──────────────────────────────────────────────

# ALIAS_COMMAND_MAP: alias (with /) → canonical command (with /)
ALIAS_COMMAND_MAP: dict[str, str] = {
    f"/{k}": f"/{v}" for k, v in build_alias_map().items()
}
# Also include self-mappings for canonical commands
for cmd_entry in REGISTRY:
    name = f"/{cmd_entry.command}"
    if name not in ALIAS_COMMAND_MAP:
        ALIAS_COMMAND_MAP[name] = name

# LEGACY_COMMAND_REDIRECTS: legacy command (with /) → canonical command (with /)
LEGACY_COMMAND_REDIRECTS: dict[str, str] = {
    f"/{k}": f"/{v}" for k, v in build_legacy_redirect_map().items()
}

# BUTTON_COMMAND_MAP: Turkish keyboard button → canonical command (with /)
BUTTON_COMMAND_MAP: dict[str, str] = {
    "✅ Sağlık": "/health",
    "🧾 Audit": "/audit",
    "📚 Profiller": "/profiles",
    "📡 Kaynaklar": "/kaynak",
    "👁 Watch": "/profile_status",
    "🔎 Ara": "/ara",
    "🔎 Tara": "/tara",
    "📋 Menü": "/menu",
}

# MENU_TEXT: generated from registry
MENU_TEXT = build_menu_text()


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