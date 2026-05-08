import json
from pathlib import Path
from collections import Counter

from config.paths import PROFILES_DIR, USER_INPUTS_DIR
from commands.audit_commands import handle_audit_command
from commands.menu import command_help, menu_text
from commands.manual_scan_commands import handle_manual_scan_command
from commands.source_commands import handle_source_command
from source_selectors.profile_loader import load_config_for_profile
from source_selectors.feed_selector import select_feeds
from source_selectors.profile_policy import canonical_profile_name

STATE_PATH = USER_INPUTS_DIR / "profile_state.json"
WATCH_PATH = USER_INPUTS_DIR / "manual_watch.json"
POLICY_OVERRIDE_PATH = USER_INPUTS_DIR / "notification_policy_overrides.json"

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
    overrides_blob = _load_policy_overrides().get("profiles", {}) or {}
    lines = ["🧩 Policy özeti", ""]
    for profile_id in profiles:
        cfg = load_config_for_profile(profile_id, active_profile_names=[profile_id])
        policies = cfg.get("profile_policies", {}) or {}
        key = canonical_profile_name(profile_id)
        policy = dict(policies.get(key, {}) or {})
        override = overrides_blob.get(key, {}) or {}
        min_score = override.get("min_score", policy.get("min_score", "-"))
        notify = policy.get("notify_policy", "-")
        unverified = "açık" if policy.get("allow_unverified", True) else "kapalı"
        confirm = "evet" if policy.get("require_official_confirmation", False) else "hayır"
        extra = " runtime" if override else ""
        lines.append(f"{_profile_label(profile_id)}")
        lines.append(f"- policy: {notify}")
        lines.append(f"- min skor: {min_score}{extra}")
        lines.append(f"- teyitsiz: {unverified} | resmî teyit: {confirm}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_runtime_status() -> str:
    profiles = _known_profiles_available()
    state = load_profile_state()
    active = [p for p in profiles if p in set(state.get("active_profiles", []))]
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
        value = (overrides.get(key, {}) or {}).get("min_score", policy.get("min_score", "-"))
        lines.append(f"- {_profile_label(p)}: {value}")

    lines.append("")
    lines.append(f"Watch kelime: {_watch_count()}")
    lines.append(f"Kaynak: {active_sources} aktif / {passive_sources} pasif / {total} toplam")
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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def available_profiles():
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile_state():
    profiles = available_profiles()
    state = _load_json(STATE_PATH, {})

    state.setdefault("active_profiles", ["tum_profiller"] if "tum_profiller" in profiles else profiles[:1])
    state.setdefault("disabled_profiles", [])
    state["available_profiles"] = profiles
    state["manual_override"] = True

    state["active_profiles"] = [p for p in state["active_profiles"] if p in profiles]
    state["disabled_profiles"] = [p for p in state["disabled_profiles"] if p in profiles]

    if not state["active_profiles"] and "tum_profiller" in profiles:
        state["active_profiles"] = ["tum_profiller"]

    _save_json(STATE_PATH, state)
    return state


def save_profile_state(state):
    _save_json(STATE_PATH, state)


def _load_policy_overrides() -> dict:
    data = _load_json(POLICY_OVERRIDE_PATH, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("profiles", {})
    if not isinstance(data.get("profiles"), dict):
        data["profiles"] = {}
    return data


def _save_policy_overrides(data: dict):
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

    if cmd in ("/profiles", "/profile_status", "/profile_on", "/profile_off", "/policy", "/alarm_esik"):
        profiles = _known_profiles_available()
        state = load_profile_state()
        active = set(state.get("active_profiles", []))

        if cmd == "/profiles":
            lines = ["📚 Profiller:"]
            for p in profiles:
                suffix = " (master)" if p == "tum_profiller" else ""
                lines.append(f"{'✅' if p in active else '⬜'} {_profile_label(p)}{suffix}")
            return "\n".join(lines)

        if cmd == "/profile_status":
            return _format_runtime_status()

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
            state["disabled_profiles"] = [p for p in profiles if p not in state["active_profiles"]]
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


def _command_help() -> str:
    return command_help()


def handle_profile_command(text: str) -> str | None:
    raw = (text or "").strip()
    if raw in {"/menu", "menu"}:
        return menu_text()

    if not raw:
        return None

    for name, handler in (
        ("audit", handle_audit_command),
        ("manual_scan", handle_manual_scan_command),
        ("profiles", handle_profiles_command),
    ):
        try:
            reply = handler(raw)
        except Exception as exc:
            return f"Komut çalıştırılamadı ({name}): {exc}"
        if reply:
            return reply

    aliases = {
        "/profil_liste": "/profil liste",
        "/profil_durum": "/profil durum",
        "/profil_tum": "/profil aktif tum_profiller",
        "/profil_resmi": "/profil aktif resmi_aciklamalar",
        "/profil_haber": "/profil aktif dunya",
        "/profil_ekonomi": "/profil aktif ekonomi",
        "/profil_osint": "/profil aktif osint",
        "/profil_saglik": "/profil aktif saglik",
        "/profil_dunya": "/profil aktif dunya",
        "/profil_turkiye": "/profil aktif turkiye",
        "/profil_yerel": "/profil aktif yerel",
        "/profil_analiz": "/profil aktif analiz",
    }

    raw = aliases.get(raw, raw)

    if not (raw == "/profil" or raw.startswith("/profil ")):
        for name, handler in (
            ("watch", handle_watch_command),
                ("source", handle_source_command),
        ):
            try:
                reply = handler(raw)
            except Exception as exc:
                return f"Komut çalıştırılamadı ({name}): {exc}"
            if reply:
                return reply
        if raw.startswith('/'):
            return "Bilinmeyen komut.\n" + _command_help()
        return None

    parts = raw.split()
    state = load_profile_state()
    profiles = available_profiles()

    if len(parts) == 1 or parts[1] in ("yardim", "help"):
        return (
            "🧭 Profil komutları\n\n"
            "/profil_liste\n"
            "/profil_durum\n"
            "/profil_tum\n"
            "/profil_resmi\n"
            "/profil_haber\n"
            "/profil_dunya\n"
            "/profil_turkiye\n"
            "/profil_yerel\n"
            "/profil_analiz\n"
            "/profil_ekonomi\n"
            "/profil_osint\n"
            "/profil_saglik\n\n"
            "Manuel takip:\n"
            "/watch_liste\n"
            "/watch_ekle Mersin\n"
            "/watch_sil Mersin\n\n"
            "Manuel arama:\n"
            "/ara hormuz\n"
            "/tara hormuz\n\n"
            "Feed kontrol:\n"
            "/feed_kontrol\n\n"
            "Gelişmiş:\n"
            "/profil ac ekonomi\n"
            "/profil kapat dunya"
        )

    cmd = parts[1].lower()

    if cmd in ("liste", "list"):
        active = set(state.get("active_profiles", []))
        lines = ["📚 Profil listesi:"]
        for p in profiles:
            mark = "✅" if p in active else "⬜"
            lines.append(f"{mark} {p}")
        return "\n".join(lines)

    if cmd in ("durum", "status", "aktifler"):
        active = state.get("active_profiles", [])
        if not active:
            return "📌 Aktif profil yok."
        return "📌 Aktif profiller:\n" + "\n".join(f"✅ {p}" for p in active)

    if cmd == "aktif":
        if len(parts) < 3:
            return "Aktif yapılacak profil eksik. Örn: /profil aktif tum_profiller"
        target = parts[2]
        if target not in profiles:
            return f"❌ Profil yok: {target}\n/profil_liste"
        state["active_profiles"] = [target]
        state["disabled_profiles"] = [p for p in profiles if p != target]
        save_profile_state(state)
        return f"✅ Tek aktif profil ayarlandı: {target}"

    if cmd in ("ac", "aç", "enable"):
        if len(parts) < 3:
            return "Açılacak profil eksik. Örn: /profil ac ekonomi"
        target = parts[2]
        if target not in profiles:
            return f"❌ Profil yok: {target}\n/profil_liste"

        active = set(state.get("active_profiles", []))
        active.add(target)

        if "tum_profiller" in active and target != "tum_profiller":
            active.discard("tum_profiller")

        state["active_profiles"] = sorted(active)
        state["disabled_profiles"] = [p for p in profiles if p not in state["active_profiles"]]
        save_profile_state(state)
        return f"✅ Profil açıldı: {target}"

    if cmd in ("kapat", "disable"):
        if len(parts) < 3:
            return "Kapatılacak profil eksik. Örn: /profil kapat haber"
        target = parts[2]
        if target not in profiles:
            return f"❌ Profil yok: {target}\n/profil_liste"

        active = set(state.get("active_profiles", []))
        active.discard(target)

        if not active:
            return "❌ En az bir profil aktif kalmalı."

        state["active_profiles"] = sorted(active)
        state["disabled_profiles"] = [p for p in profiles if p not in state["active_profiles"]]
        save_profile_state(state)
        return f"⛔ Profil kapatıldı: {target}"

    return "Bilinmeyen profil komutu. /profil"


def _load_watch():
    data = _load_json(WATCH_PATH, {})
    data.setdefault("enabled", True)
    data.setdefault("keywords", [])
    data.setdefault("priority", "high")
    return data


def _save_watch(data):
    _save_json(WATCH_PATH, data)


def handle_watch_command(text: str) -> str | None:
    raw = (text or "").strip()

    if raw.startswith("/watch_liste") or raw == "/watch":
        data = _load_watch()
        kws = data.get("keywords", [])
        if not kws:
            return "📌 Manuel takip listesi boş."
        return "📌 Manuel takip kelimeleri:\n" + "\n".join(f"✅ {x}" for x in kws)

    if raw.startswith("/watch_ekle"):
        value = raw.replace("/watch_ekle", "", 1).strip()
        if not value:
            return "Eklenecek kelime eksik. Örn: /watch_ekle Mersin"
        data = _load_watch()
        kws = data.setdefault("keywords", [])
        if value not in kws:
            kws.append(value)
        _save_watch(data)
        return f"✅ Manuel takip eklendi: {value}"

    if raw.startswith("/watch_sil"):
        value = raw.replace("/watch_sil", "", 1).strip()
        if not value:
            return "Silinecek kelime eksik. Örn: /watch_sil Mersin"
        data = _load_watch()
        kws = data.setdefault("keywords", [])
        data["keywords"] = [x for x in kws if x.lower() != value.lower()]
        _save_watch(data)
        return f"🗑 Manuel takip silindi: {value}"

    return None


def handle_feed_command(text: str) -> str | None:
    raw = (text or "").strip()
    if raw == "/feed_kontrol":
        import subprocess
        import sys
        subprocess.Popen([sys.executable, "scripts/feed_log_check.py"])
        return "🔍 Feed log kontrolü başlatıldı..."
    return None



def main(argv: list[str] | None = None) -> int:
    import sys
    args = sys.argv[1:] if argv is None else argv
    text = " ".join(args).strip()
    print(handle_profile_command(text) or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
