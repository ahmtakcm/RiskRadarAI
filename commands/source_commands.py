import json
import requests
from pathlib import Path
from xml.etree import ElementTree as ET

FEEDS_PATH = Path("rules/feeds.json")
PROFILES_DIR = Path("profiles")
PENDING_PATH = Path("user_inputs/source_pending.json")


def _load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _test_url(url, kind):
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 RiskRadarAI/1.0"},
            timeout=20,
            allow_redirects=True,
        )
        if r.status_code < 200 or r.status_code >= 400:
            return False, f"HTTP {r.status_code}"

        text = r.text.lower()

        if kind in ("rss", "rss_social"):
            if "<rss" in text or "<feed" in text or "<item" in text or "<entry" in text:
                return True, "RSS OK"
            try:
                ET.fromstring(r.content)
                return True, "XML OK"
            except Exception:
                return False, "RSS/XML değil"

        if kind in ("listing_html", "official_html"):
            return (len(r.text) > 300), "HTML OK" if len(r.text) > 300 else "HTML çok kısa"

        return True, "OK"

    except Exception as exc:
        return False, str(exc)[:180]


def _profiles():
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def _add_to_profiles(name, profiles):
    valid = set(_profiles())
    added = []

    for profile in profiles:
        if profile not in valid:
            continue

        p = PROFILES_DIR / f"{profile}.json"
        data = _load(p, {})

        for key in ("sources", "enabled_feeds"):
            arr = data.setdefault(key, [])
            if name not in arr:
                arr.append(name)

        _save(p, data)
        added.append(profile)

    return added


def _remove_from_profiles(name):
    changed = []

    for p in PROFILES_DIR.glob("*.json"):
        data = _load(p, {})
        did = False

        for key in ("sources", "enabled_feeds"):
            if isinstance(data.get(key), list):
                before = list(data[key])
                data[key] = [x for x in data[key] if x.lower() != name.lower()]
                did = did or before != data[key]

        if did:
            _save(p, data)
            changed.append(p.stem)

    return changed


def _upsert_feed(feed):
    feeds = _load(FEEDS_PATH, [])
    found = False

    for f in feeds:
        if f.get("name", "").lower() == feed["name"].lower():
            f.update(feed)
            found = True
            break

    if not found:
        feeds.append(feed)

    _save(FEEDS_PATH, feeds)
    return found


def handle_source_command(text: str):
    raw = (text or "").strip()

    if raw in ("/kaynak", "/kaynak_yardim"):
        return (
            "🧭 Kaynak komutları\n\n"
            "/kaynak_liste\n"
            "/kaynak_teklif Ad | URL | rss | haber,tum_profiller\n"
            "/kaynak_onay Ad\n"
            "/kaynak_red Ad\n"
            "/kaynak_sil Ad\n"
            "/kaynak_test Ad\n"
            "/kaynak_test_url URL | rss\n\n"
            "Not: /kaynak_teklif otomatik eklemez; önce test eder, onay bekletir."
        )

    if raw == "/kaynak_liste":
        feeds = _load(FEEDS_PATH, [])
        lines = ["📚 Kaynak listesi:"]
        for f in feeds:
            mark = "✅" if f.get("enabled", True) else "⛔"
            lines.append(f"{mark} {f.get('name')} [{f.get('kind', 'rss')}]")
        return "\n".join(lines[:120])

    if raw.startswith("/kaynak_test_url"):
        body = raw.replace("/kaynak_test_url", "", 1).strip()
        parts = [x.strip() for x in body.split("|")]
        if not parts or not parts[0]:
            return "Eksik kullanım: /kaynak_test_url https://site.com/rss | rss"
        url = parts[0]
        kind = parts[1] if len(parts) > 1 and parts[1] else "rss"
        ok, reason = _test_url(url, kind)
        return f"{'✅' if ok else '❌'} URL test sonucu\nURL: {url}\nTip: {kind}\nSonuç: {reason}"

    if raw.startswith("/kaynak_test"):
        name = raw.replace("/kaynak_test", "", 1).strip()
        if not name:
            return "Kaynak adı eksik. Örn: /kaynak_test Crisis Group RSS"

        feeds = _load(FEEDS_PATH, [])
        f = next((x for x in feeds if x.get("name", "").lower() == name.lower()), None)
        if not f:
            return f"❌ Kaynak bulunamadı: {name}"

        ok, reason = _test_url(f.get("url"), f.get("kind", "rss"))
        return f"{'✅' if ok else '❌'} Kaynak test sonucu\nAd: {f.get('name')}\nURL: {f.get('url')}\nSonuç: {reason}"

    if raw.startswith("/kaynak_teklif"):
        body = raw.replace("/kaynak_teklif", "", 1).strip()
        parts = [x.strip() for x in body.split("|")]

        if len(parts) < 4:
            return "Eksik kullanım:\n/kaynak_teklif Ad | URL | rss | haber,tum_profiller"

        name, url, kind, profile_raw = parts[:4]
        profiles = [x.strip() for x in profile_raw.split(",") if x.strip()]

        if kind not in ("rss", "rss_social", "listing_html", "official_html"):
            return "❌ Geçersiz tip: rss, rss_social, listing_html, official_html"

        ok, reason = _test_url(url, kind)
        if not ok:
            return f"❌ Kaynak teklif edilmedi\nAd: {name}\nSebep: {reason}"

        pending = _load(PENDING_PATH, {})
        pending[name] = {
            "name": name,
            "url": url,
            "kind": kind,
            "profiles": profiles,
            "enabled": True,
            "priority": 5,
            "notes": "Telegram onayıyla eklendi."
        }
        _save(PENDING_PATH, pending)

        return (
            "🆕 Kaynak adayı hazır\n\n"
            f"Ad: {name}\n"
            f"URL: {url}\n"
            f"Tip: {kind}\n"
            f"Profiller: {', '.join(profiles)}\n"
            f"Test: {reason}\n\n"
            f"Onay: /kaynak_onay {name}\n"
            f"Red: /kaynak_red {name}"
        )

    if raw.startswith("/kaynak_onay"):
        name = raw.replace("/kaynak_onay", "", 1).strip()
        pending = _load(PENDING_PATH, {})

        key = next((k for k in pending if k.lower() == name.lower()), None)
        if not key:
            return f"❌ Bekleyen kaynak bulunamadı: {name}"

        feed = pending.pop(key)
        profiles = feed.pop("profiles", [])

        ok, reason = _test_url(feed["url"], feed["kind"])
        if not ok:
            _save(PENDING_PATH, pending)
            return f"❌ Kaynak onaylanmadı\nAd: {feed['name']}\nSebep: {reason}"

        updated = _upsert_feed(feed)
        added_profiles = _add_to_profiles(feed["name"], profiles)
        _save(PENDING_PATH, pending)

        return (
            f"✅ Kaynak {'güncellendi' if updated else 'eklendi'}\n"
            f"Ad: {feed['name']}\n"
            f"Test: {reason}\n"
            f"Profiller: {', '.join(added_profiles) if added_profiles else 'profil eklenmedi'}"
        )

    if raw.startswith("/kaynak_red"):
        name = raw.replace("/kaynak_red", "", 1).strip()
        pending = _load(PENDING_PATH, {})
        key = next((k for k in pending if k.lower() == name.lower()), None)
        if not key:
            return f"❌ Bekleyen kaynak bulunamadı: {name}"
        pending.pop(key, None)
        _save(PENDING_PATH, pending)
        return f"❌ Kaynak adayı reddedildi: {name}"

    if raw.startswith("/kaynak_sil"):
        name = raw.replace("/kaynak_sil", "", 1).strip()
        if not name:
            return "Silinecek kaynak adı eksik."

        feeds = _load(FEEDS_PATH, [])
        before = len(feeds)
        feeds = [f for f in feeds if f.get("name", "").lower() != name.lower()]
        if len(feeds) == before:
            return f"❌ Kaynak bulunamadı: {name}"

        _save(FEEDS_PATH, feeds)
        changed = _remove_from_profiles(name)
        return f"🗑 Kaynak silindi: {name}\nTemizlenen profiller: {', '.join(changed) if changed else 'yok'}"

    return None
