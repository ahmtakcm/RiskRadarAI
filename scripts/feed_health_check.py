import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

import json
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import settings
from clients.telegram_client import telegram_client

FEEDS_PATH = Path("rules/feeds.json")
OUT_PATH = Path("storage/feed_health_report.json")
FAIL_STATE_PATH = Path("storage/feed_fail_state.json")

TIMEOUT = 7
MAX_WORKERS = 8
AUTO_DISABLE_AFTER = 3

# 401/403 genelde bot koruması olabilir; direkt kapatma.
SOFT_STATUSES = {401, 403}
HARD_STATUSES = {404, 410, 500, 502, 503, 504}


KNOWN_FIXES = {
    "Reuters World": {
        "url": "https://www.reuters.com/world/",
        "kind": "listing_html",
    },
    "EEAS Newsroom": {
        "url": "https://www.eeas.europa.eu/_en",
        "kind": "listing_html",
    },
    "TCMB Enflasyon Raporu 2026": {
        "url": "https://tcmb.gov.tr/wps/wcm/connect/tr/tcmb+tr/main+menu/yayinlar/raporlar/enflasyon+raporu/2026/enflasyon+raporu+2026+-+i",
        "kind": "listing_html",
    },
    "Defense RSS Releases": {
        "url": "https://www.war.gov/News/Releases/",
        "kind": "listing_html",
    },
    "Defense RSS News": {
        "url": "https://www.war.gov/News/",
        "kind": "listing_html",
    },
}


def send_telegram(text: str):
    telegram_client.send_message(text)


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify_problem(status, error):
    e = (error or "").lower()

    if status in SOFT_STATUSES:
        return "soft_block", "Site erişimi kısıtlıyor olabilir; otomatik kapatılmadı."

    if status in HARD_STATUSES:
        return "hard_error", f"HTTP {status}; kaynak URL sorunlu olabilir."

    if "name or service not known" in e or "failed to resolve" in e or "no address associated" in e:
        return "dns_error", "DNS çözümlenemedi."

    if "timed out" in e or "timeout" in e:
        return "timeout", "Zaman aşımı."

    if "connection reset" in e or "connection aborted" in e:
        return "connection_reset", "Bağlantı kesildi/resetlendi."

    if status is None:
        return "network_error", "Ağ/erişim hatası."

    return "unknown", "Bilinmeyen kaynak erişim sorunu."


def should_count_failure(problem_type):
    # 401/403 gibi soft block durumlarını fail sayma.
    return problem_type not in {"soft_block"}


def should_disable(problem_type, fail_count):
    if problem_type in {"soft_block"}:
        return False
    return fail_count >= AUTO_DISABLE_AFTER


def check_one(feed):
    name = feed.get("name")
    url = feed.get("url")

    if not name or not url:
        return {
            "name": name or "NO_NAME",
            "url": url,
            "ok": False,
            "status": None,
            "error": "missing name/url",
        }

    try:
        r = requests.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android) AppleWebKit/537.36 Chrome/120 Safari/537.36 RiskRadarAI/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
            },
        )

        return {
            "name": name,
            "url": url,
            "ok": 200 <= r.status_code < 400,
            "status": r.status_code,
            "error": None if 200 <= r.status_code < 400 else "",
        }

    except Exception as exc:
        return {
            "name": name,
            "url": url,
            "ok": False,
            "status": None,
            "error": str(exc)[:220],
        }


def apply_known_fixes(feeds):
    fixed = []

    for f in feeds:
        name = f.get("name")
        if name in KNOWN_FIXES:
            changed = False
            for k, v in KNOWN_FIXES[name].items():
                if f.get(k) != v:
                    f[k] = v
                    changed = True
            if changed:
                f["enabled"] = True
                f["auto_fixed_at"] = datetime.now().isoformat(timespec="seconds")
                fixed.append(name)

    return fixed


def main():
    feeds = load_json(FEEDS_PATH, [])
    fail_state = load_json(FAIL_STATE_PATH, {})

    fixed = apply_known_fixes(feeds)

    active = [f for f in feeds if f.get("enabled", True) and f.get("url")]
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(check_one, f) for f in active]
        for fut in as_completed(futures):
            results.append(fut.result())

    ok = []
    bad = []
    soft = []
    disabled_now = []

    feed_by_name = {f.get("name"): f for f in feeds}

    for r in results:
        name = r["name"]

        if r["ok"]:
            ok.append(name)
            fail_state[name] = 0
            continue

        problem_type, explanation = classify_problem(r.get("status"), r.get("error"))
        r["problem_type"] = problem_type
        r["explanation"] = explanation

        if should_count_failure(problem_type):
            fail_state[name] = fail_state.get(name, 0) + 1
        else:
            fail_state[name] = fail_state.get(name, 0)

        r["fail_count"] = fail_state[name]

        if problem_type == "soft_block":
            soft.append(r)
        else:
            bad.append(r)

        if should_disable(problem_type, fail_state[name]):
            f = feed_by_name.get(name)
            if f and f.get("enabled", True):
                f["enabled"] = False
                f["disabled_reason"] = f"auto disabled: {problem_type} {fail_state[name]}x"
                f["disabled_at"] = datetime.now().isoformat(timespec="seconds")
                disabled_now.append(name)

    report = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "active_checked": len(active),
        "ok_count": len(ok),
        "soft_block_count": len(soft),
        "bad_count": len(bad),
        "auto_fixed": fixed,
        "soft_block": sorted(soft, key=lambda x: x["name"]),
        "bad": sorted(bad, key=lambda x: x["name"]),
        "disabled": disabled_now,
    }

    save_json(FAIL_STATE_PATH, fail_state)
    save_json(OUT_PATH, report)
    save_json(FEEDS_PATH, feeds)

    lines = ["🩺 RiskRadarAI Kaynak Sağlık Raporu", ""]
    lines.append(f"✅ Sağlıklı: {len(ok)}")
    lines.append(f"⚠️ Erişim kısıtı/soft: {len(soft)}")
    lines.append(f"❌ Sorunlu: {len(bad)}")

    if fixed:
        lines.append("")
        lines.append("🔧 Otomatik düzeltme uygulandı:")
        for n in fixed[:8]:
            lines.append(f"🛠 {n}")

    if soft:
        lines.append("")
        lines.append("⚠️ Erişim kısıtı olabilir, kapatılmadı:")
        for x in soft[:8]:
            lines.append(f"• {x['name']} | HTTP {x['status']}")

    if bad:
        lines.append("")
        lines.append("❌ Teknik sorunlu kaynaklar:")
        for x in bad[:10]:
            lines.append(f"• {x['name']} | {x['problem_type']} | {x['fail_count']}x")

    if disabled_now:
        lines.append("")
        lines.append("⛔ Otomatik kapatılanlar:")
        for n in disabled_now:
            lines.append(f"🚫 {n}")

    if not fixed and not soft and not bad and not disabled_now:
        lines.append("")
        lines.append("Tüm aktif kaynaklar temiz görünüyor.")

    send_telegram("\n".join(lines))
    print("OK:", len(ok), "SOFT:", len(soft), "BAD:", len(bad), "DISABLED:", len(disabled_now))


if __name__ == "__main__":
    main()
