import json
import threading
from pathlib import Path

from config.paths import PROFILES_DIR, USER_INPUTS_DIR
from commands.audit_commands import handle_audit_command
from commands.menu import (
    ALIAS_COMMAND_MAP,
    BUTTON_COMMAND_MAP,
    command_help,
    legacy_command_message,
    menu_text,
)
from commands.manual_scan_commands import handle_manual_scan_command
from commands.source_commands import handle_source_command
from source_selectors.profile_loader import load_config_for_profile
from source_selectors.feed_selector import select_feeds
from source_selectors.profile_policy import canonical_profile_name

STATE_PATH = USER_INPUTS_DIR / "profile_state.json"
WATCH_PATH = USER_INPUTS_DIR / "manual_watch.json"
POLICY_OVERRIDE_PATH = USER_INPUTS_DIR / "notification_policy_overrides.json"

# Thread lock for profile state and policy overrides file access.
# These files are read by source_selectors.profile_loader (main loop)
# while written by commands.profile_commands (command worker thread).
_PROFILE_FILE_LOCK = threading.Lock()

# Telegram-visible stable profile IDs
KNOWN_PROFILE_IDS = [
    "resmi_aciklamalar",
    "ekonomi",
    "saglik",
    "dunya",
    "turkiye",
    "yerel",
    "osint",
    "analiz",
    "tum_profiller",
]

PROFILE_LABELS = {
    "resmi_aciklamalar": "🏛 Resmî",
    "dunya": "🌍 Dünya",
    "turkiye": "🇹🇷 Türkiye",
    "yerel": "📍 Yerel",
    "ekonomi": "📈 Ekonomi",
    "osint": "🕵 OSINT",
    "analiz": "🧠 Analiz",
    "saglik": "🏥 Sağlık",
    "tum_profiller": "🧭 Tüm profiller",
}


def _profile_label(profile_id: str) -> str:
    return PROFILE_LABELS.get(profile_id, profile_id)


def _profile_examples() -> str:
    return ", ".join(_profile_label(p) for p in _known_profiles_available())


def _feed_totals() -> tuple[int, int, int]:
    feeds_path = Path("rules/feeds.json")
    data = _load_json(feeds_path, [])
    total = len(data) if isinstance(data, list) else 0
    active = sum(1 for f in data if isinstance(f, dict) and f.get("enabled", True))
    passive = max(total - active, 0)
    return total, active, passive


def _watch_count() -> int:
    data = _load_json(WATCH_PATH, {})
    kws = data.get("keywords", []) if isinstance(data, dict) else []
    return len(kws) if isinstance(kws, list) else 0


def _format_all_policies() -> str:
    profiles = _known_profiles_available()
    lines = ["🧩 Policy özeti", ""]
    for profile_id in profiles:
        cfg = load_config_for_profile(profile_id, active_profile_names=[profile_id])
        policies = cfg.get("profile_policies", {}) or {}
        key = canonical_profile_name(profile_id)
        policy = dict(policies.get(key, {}) or {})
        notify = policy.get("notify_policy", "-")
        unverified = "açık" if policy.get("allow_unverified", True) else "kapalı"
        confirm = (
            "evet" if policy.get("require_official_confirmation", False) else "hayır"
        )
        lines.append(f"{_profile_label(profile_id)}")
        lines.append(f"- policy: {notify}")
        lines.append(f"- teyitsiz: {unverified} | resmî teyit: {confirm}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_runtime_status() -> str:
    profiles = _known_profiles_available()
    state = load_profile_state()
    raw_active = set(state.get("active_profiles", []))
    is_master_active = "tum_profiller" in raw_active
    active = [p for p in profiles if p in raw_active or (is_master_active and p != "tum_profiller")]
    total, active_sources, passive_sources = _feed_totals()
    overrides = _load_policy_overrides().get("profiles", {}) or {}

    lines = ["📡 Profil runtime durum", ""]
    lines.append(f"Aktif profil: {len(active)}")
    for p in active:
        suffix = " (master)" if p == "tum_profiller" else ""
        lines.append(f"✅ {_profile_label(p)}{suffix}")

    lines.append("")
    lines.append("Alarm eşikleri:")
    for p in active:
        key = canonical_profile_name(p)
        cfg = load_config_for_profile(p, active_profile_names=[p])
        policy = (cfg.get("profile_policies", {}) or {}).get(key, {}) or {}
        value = (overrides.get(key, {}) or {}).get(
            "min_score", policy.get("min_score", "-")
        )
        lines.append(f"- {_profile_label(p)}: {value}")

    lines.append("")
    lines.append(f"Watch kelime: {_watch_count()}")
    lines.append(
        f"Kaynak: {active_sources} aktif / {passive_sources} pasif / {total} toplam"
    )
    return "\n".join(lines)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def available_profiles():
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile_state():
    with _PROFILE_FILE_LOCK:
        return _load_profile_state_unsafe()


def _load_profile_state_unsafe():
    profiles = available_profiles()
    state = _load_json(STATE_PATH, {})

    state.setdefault(
        "active_profiles",
        ["tum_profiller"] if "tum_profiller" in profiles else profiles[:1],
    )
    state.setdefault("disabled_profiles", [])
    state["available_profiles"] = profiles
    state["manual_override"] = True

    state["active_profiles"] = [p for p in state["active_profiles"] if p in profiles]
    state["disabled_profiles"] = [
        p for p in state["disabled_profiles"] if p in profiles
    ]

    if not state["active_profiles"] and "tum_profiller" in profiles:
        state["active_profiles"] = ["tum_profiller"]

    _save_json(STATE_PATH, state)
    return state


def save_profile_state(state):
    with _PROFILE_FILE_LOCK:
        _save_json(STATE_PATH, state)


def _load_policy_overrides() -> dict:
    with _PROFILE_FILE_LOCK:
        data = _load_json(POLICY_OVERRIDE_PATH, {})
        if not isinstance(data, dict):
            data = {}
        data.setdefault("profiles", {})
        if not isinstance(data.get("profiles"), dict):
            data["profiles"] = {}
        return data


def _save_policy_overrides(data: dict):
    with _PROFILE_FILE_LOCK:
        _save_json(POLICY_OVERRIDE_PATH, data)


def _known_profiles_available() -> list[str]:
    existing = set(available_profiles())
    return [p for p in KNOWN_PROFILE_IDS if p in existing]


def _profile_not_found(name: str) -> str:
    return f"❌ Profil yok: {name}\n/profiles"


def _format_profile_sources(profile_id: str) -> str:
    cfg = load_config_for_profile(profile_id, active_profile_names=[profile_id])
    official = select_feeds(cfg, mode="official_only")
    social = select_feeds(cfg, mode="social_only")
    osint = select_feeds(cfg, mode="osint_only")
    analysis = select_feeds(cfg, mode="analysis_only")
    all_feeds = select_feeds(cfg, mode="all")

    lines = [
        f"📌 Profil kaynak özeti: {profile_id}",
        f"- Shared official baseline: {len(official)}",
        f"- Social: {len(social)}",
        f"- OSINT: {len(osint)}",
        f"- Analysis: {len(analysis)}",
        f"- Toplam (dedup): {len(all_feeds)}",
        "",
        "Seçilen kaynaklar:",
    ]
    for f in all_feeds[:80]:
        kind = f.get("kind", "rss")
        lines.append(f"- {f.get('name')} [{kind}]")
    if len(all_feeds) > 80:
        lines.append(f"... ({len(all_feeds) - 80} daha)")
    return "\n".join(lines)


def _format_profile_policy(profile_id: str) -> str:
    cfg = load_config_for_profile(profile_id, active_profile_names=[profile_id])
    policies = cfg.get("profile_policies", {}) or {}
    key = canonical_profile_name(profile_id)
    policy = dict(policies.get(key, {}) or {})
    if not policy:
        return f"⚠️ Policy bulunamadı: {profile_id}"

    overrides = _load_policy_overrides().get("profiles", {}).get(key, {}) or {}
    bits = [
        f"🧩 Profil policy: {profile_id}",
        "",
        f"- notify_policy: {policy.get('notify_policy', '')}",
        f"- min_score: {policy.get('min_score', '')}",
        f"- allow_unverified: {policy.get('allow_unverified', True)}",
        f"- require_official_confirmation: {policy.get('require_official_confirmation', False)}",
    ]
    if overrides:
        bits.append("")
        bits.append("Runtime override:")
        for k in ("alarm_enabled", "digest_enabled", "min_score"):
            if k in overrides:
                bits.append(f"- {k}: {overrides.get(k)}")
    return "\n".join(bits)


def handle_profiles_command(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw.startswith("/"):
        return None

    parts = raw.split()
    cmd = parts[0].lower()

    if cmd in (
        "/profiles",
        "/profile_status",
        "/profile_sources",
        "/profile_on",
        "/profile_off",
        "/alarm_esik",
        "/policy",
    ):
        profiles = _known_profiles_available()
        state = load_profile_state()
        active = set(state.get("active_profiles", []))

        if cmd == "/profiles":
            lines = ["📚 Profiller:"]
            is_master_active = "tum_profiller" in active
            for p in profiles:
                suffix = " (master)" if p == "tum_profiller" else ""
                is_active = p in active or (is_master_active and p != "tum_profiller")
                lines.append(
                    f"{'✅' if is_active else '⬜'} {_profile_label(p)}{suffix}"
                )
            return "\n".join(lines)

        if cmd == "/profile_status":
            return _format_runtime_status()

        if cmd == "/profile_sources":
            if len(parts) < 2:
                return f"Kullanım: /profile_sources ekonomi\nProfiller: {_profile_examples()}"
            target = canonical_profile_name(parts[1])
            if target not in profiles:
                return _profile_not_found(target)
            return _format_profile_sources(target)

        if cmd in ("/profile_on", "/profile_off"):
            if len(parts) < 2:
                return f"Kullanım:\n{cmd} ekonomi\n{cmd} yerel\n{cmd} osint\n\nProfiller: {_profile_examples()}"
            target = canonical_profile_name(parts[1])
            if target not in profiles:
                return _profile_not_found(target)
            active_set = set(state.get("active_profiles", []))
            if cmd == "/profile_on":
                active_set.add(target)
                if "tum_profiller" in active_set and target != "tum_profiller":
                    active_set.discard("tum_profiller")
            else:
                active_set.discard(target)
                if not active_set:
                    return "❌ Bu profil kapatılamaz. En az bir profil aktif kalmalı.\nÖnce başka bir profil aç: /profile_on ekonomi"
            state["active_profiles"] = sorted(active_set)
            state["disabled_profiles"] = [
                p for p in profiles if p not in state["active_profiles"]
            ]
            save_profile_state(state)
            return f"{'✅' if cmd == '/profile_on' else '⛔'} Profil {'açıldı' if cmd == '/profile_on' else 'kapatıldı'}: {_profile_label(target)}"

        if cmd == "/policy":
            return _format_all_policies()

        # runtime-only notification policy overrides
        policy_blob = _load_policy_overrides()
        per = policy_blob.setdefault("profiles", {})

        def _ensure_target():
            if len(parts) < 2:
                return None, f"Eksik kullanım. Örn: {cmd} ekonomi"
            t = canonical_profile_name(parts[1])
            if t not in profiles:
                return None, _profile_not_found(t)
            return t, None

        target, err = _ensure_target()
        if err:
            return err
        per.setdefault(target, {})

        if cmd == "/alarm_esik":
            if len(parts) < 3:
                return "Alarm eşik kullanımı:\n/alarm_esik ekonomi 30\n/alarm_esik osint 15"
            try:
                value = int(parts[2])
            except Exception:
                return "Eşik sayısal olmalı. Örn: /alarm_esik ekonomi 30"
            per[target]["min_score"] = value
            _save_policy_overrides(policy_blob)
            return f"✅ Alarm eşiği güncellendi: {_profile_label(target)} → {value}"

    return None


def handle_digest_command(text: str) -> str | None:
    raw = (text or "").strip().lower()
    if raw != "/digest_now":
        return None
    try:
        from workflows.runner import build_digest_now_reply

        return build_digest_now_reply()
    except Exception as exc:
        return f"Digest çalıştırılamadı: {exc}"


def _command_help() -> str:
    return command_help()


def handle_profile_command(text: str) -> str | None:
    raw = (text or "").strip()

    # Strip @BotUsername suffix so /menu@BotName resolves to /menu
    raw = raw.split("@")[0] if "@" in raw else raw

    exact_aliases = {}
    exact_aliases.update(BUTTON_COMMAND_MAP)
    exact_aliases.update(ALIAS_COMMAND_MAP)
    raw = exact_aliases.get(raw, raw)

    if raw in {"/menu", "menu"}:
        return menu_text()

    if not raw:
        return None

    legacy_msg = legacy_command_message(raw)
    if legacy_msg:
        return legacy_msg

    for name, handler in (
        ("source", handle_source_command),
        ("audit", handle_audit_command),
        ("manual_scan", handle_manual_scan_command),
        ("digest", handle_digest_command),
        ("profiles", handle_profiles_command),
    ):
        try:
            reply = handler(raw)
        except Exception as exc:
            return f"Komut çalıştırılamadı ({name}): {exc}"
        if reply:
            return reply

    if raw.startswith("/"):
        return "Bilinmeyen komut.\n" + _command_help()
    return None


def main(argv: list[str] | None = None) -> int:
    import sys

    args = sys.argv[1:] if argv is None else argv
    text = " ".join(args).strip()
    print(handle_profile_command(text) or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
