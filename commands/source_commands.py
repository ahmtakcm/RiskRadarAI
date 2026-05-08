import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

FEEDS_PATH = Path("rules/feeds.json")
PROFILES_DIR = Path("profiles")


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


def _profiles():
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _human_error(reason: str) -> str:
    low = (reason or "").lower()
    if "nameresolutionerror" in low or "failed to resolve" in low:
        return "DNS/alan adı çözümlenemedi."
    if "connecttimeout" in low or "read timed out" in low or "timeout" in low:
        return "Bağlantı zaman aşımına uğradı."
    if "http 404" in low:
        return "HTTP 404: Sayfa/feed bulunamadı."
    if "http 403" in low:
        return "HTTP 403: Kaynak erişimi engelliyor."
    return (reason or "Bilinmeyen hata")[:180]


def _test_url(url, kind):
    url = _normalize_url(url)
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
        return False, str(exc)


def _detect_kind(url: str) -> tuple[bool, str, str]:
    candidates = ("rss", "listing_html", "official_html")
    last_reason = ""
    for kind in candidates:
        ok, reason = _test_url(url, kind)
        if ok:
            return True, kind, reason
        last_reason = reason
    return False, "", _human_error(last_reason)


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


def _source_summary() -> str:
    feeds = _load(FEEDS_PATH, [])
    total = len(feeds)
    active = [f for f in feeds if f.get("enabled", True)]
    passive = [f for f in feeds if not f.get("enabled", True)]
    kinds = Counter(str(f.get("kind", "rss")) for f in feeds)

    lines = [
        "📚 Kaynak özeti",
        f"Toplam: {total}",
        f"Aktif: {len(active)}",
        f"Pasif: {len(passive)}",
        "",
        "Tür dağılımı:",
    ]
    for kind, count in sorted(kinds.items()):
        lines.append(f"- {kind}: {count}")

    if passive:
        lines.append("")
        lines.append("Pasif kaynaklar:")
        for f in passive[:20]:
            lines.append(f"⛔ {f.get('name')}")
    return "\n".join(lines)


def _source_help() -> str:
    return (
        "🧭 Kaynak komutları\n\n"
        "/kaynak\n"
        "/kaynak_ekle <ad> | <url/domain> | <profil>\n"
        "/kaynak_test <ad>\n"
        "/kaynak_sil <ad>\n\n"
        "Örnek:\n"
        "/kaynak_ekle Test Haber | example.com/rss.xml | yerel\n"
        "/kaynak_test IRNA English\n\n"
        + _source_summary()
    )


def handle_source_command(text: str):
    raw = (text or "").strip()

    if raw in ("/kaynak", "/kaynak_yardim"):
        return _source_help()

    if raw.startswith("/kaynak_test"):
        name = raw.replace("/kaynak_test", "", 1).strip()
        if not name:
            return "Kaynak test kullanımı:\n/kaynak_test IRNA English"

        feeds = _load(FEEDS_PATH, [])
        f = next((x for x in feeds if x.get("name", "").lower() == name.lower()), None)
        if not f:
            return f"❌ Kaynak bulunamadı: {name}"

        ok, reason = _test_url(f.get("url"), f.get("kind", "rss"))
        if ok:
            return (
                "✅ Kaynak erişilebilir\n\n"
                f"Ad: {f.get('name')}\n"
                f"Tip: {f.get('kind', 'rss')}\n"
                f"Sonuç: {reason}"
            )
        return (
            "❌ Kaynak erişim hatası\n\n"
            f"Ad: {f.get('name')}\n"
            f"Tip: {f.get('kind', 'rss')}\n"
            f"Sorun: {_human_error(reason)}"
        )

    if raw.startswith("/kaynak_ekle"):
        body = raw.replace("/kaynak_ekle", "", 1).strip()
        parts = [x.strip() for x in body.split("|")]
        if len(parts) < 3:
            return "Kaynak ekleme kullanımı:\n/kaynak_ekle Ad | URL/domain | profil"

        name, url, profile_raw = parts[:3]
        profiles = [x.strip() for x in re.split(r"[, ]+", profile_raw) if x.strip()]
        url = _normalize_url(url)

        ok, kind, reason = _detect_kind(url)
        if not ok:
            return f"❌ Kaynak eklenemedi\nAd: {name}\nSebep: {reason}"

        feed = {
            "name": name,
            "url": url,
            "kind": kind,
            "enabled": True,
            "priority": 5,
            "notes": "Telegram kaynak_ekle ile eklendi.",
        }

        updated = _upsert_feed(feed)
        added_profiles = _add_to_profiles(name, profiles)

        return (
            f"✅ Kaynak {'güncellendi' if updated else 'eklendi'}\n\n"
            f"Ad: {name}\n"
            f"URL: {url}\n"
            f"Algılanan tip: {kind}\n"
            f"Test: {reason}\n"
            f"Profiller: {', '.join(added_profiles) if added_profiles else 'profil eklenmedi'}"
        )

    if raw.startswith("/kaynak_sil"):
        name = raw.replace("/kaynak_sil", "", 1).strip()
        if not name:
            return "Kaynak silme kullanımı:\n/kaynak_sil Iran President"

        feeds = _load(FEEDS_PATH, [])
        before = len(feeds)
        feeds = [f for f in feeds if f.get("name", "").lower() != name.lower()]
        if len(feeds) == before:
            return f"❌ Kaynak bulunamadı: {name}"

        _save(FEEDS_PATH, feeds)
        changed = _remove_from_profiles(name)
        return f"🗑 Kaynak silindi: {name}\nTemizlenen profiller: {', '.join(changed) if changed else 'yok'}"

    return None
