import json
from pathlib import Path

from config.paths import PROFILES_DIR, USER_INPUTS_DIR

STATE_PATH = USER_INPUTS_DIR / "profile_state.json"
WATCH_PATH = USER_INPUTS_DIR / "manual_watch.json"


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


def handle_profile_command(text: str) -> str | None:
    raw = (text or "").strip()

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

    return "❌ Bilinmeyen profil komutu. /profil"


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
