import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows.macro_event_importance import enrich_macro_event

CALENDAR_CACHE = ROOT / "storage/calendar_cache.json"
RAW_DIR = ROOT / "storage/macro_archive/raw"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7,
    "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12
}

def _read(name):
    p = RAW_DIR / f"{name}.txt"
    if not p.exists():
        return ""
    return re.sub(r"\s+", " ", p.read_text(encoding="utf-8", errors="ignore"))

def _slug(s):
    s = s.lower()
    s = s.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:80]

def _event(eid, title, source, category, dt, url, signals, etype="macro_event"):
    return enrich_macro_event({
        "id": eid,
        "title": title[:180],
        "category": category,
        "source_name": source,
        "event_type": etype,
        "datetime": dt.isoformat(),
        "timezone": "UTC",
        "post_window_minutes": 360,
        "watch_urls": [url] if url else [],
        "publish_signals": signals,
        "enabled": True,
        "status": "active",
        "sent_alerts": [],
        "auto_generated": True
    })

def parse_fomc():
    out = []
    url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

    meetings = [
        ("2026-06-17", "FOMC Meeting June 16-17 2026"),
        ("2026-07-29", "FOMC Meeting July 28-29 2026"),
        ("2026-09-16", "FOMC Meeting September 15-16 2026"),
        ("2026-10-28", "FOMC Meeting October 27-28 2026"),
        ("2026-12-09", "FOMC Meeting December 8-9 2026"),
    ]

    for date_str, title in meetings:
        y, m, d = map(int, date_str.split("-"))
        dt = datetime(y, m, d, 18, 0, tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        out.append(_event(
            f"auto_fomc_{dt.strftime('%Y%m%d')}",
            title,
            "Federal Reserve FOMC",
            "rate_decision",
            dt,
            url,
            ["statement", "implementation note", "press conference", "minutes", "projection materials"],
            "scheduled_decision"
        ))

    return out


def parse_ecb_policy():
    text = _read("ecb_policy_calendar")
    out = []
    url = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"

    # Raw metinde Day 1 + Day 2 peş peşe aktığı için manuel güvenli liste.
    events = [
        ("2026-06-11", "ECB Monetary Policy Decision and Press Conference"),
        ("2026-07-23", "ECB Monetary Policy Decision and Press Conference"),
        ("2026-09-10", "ECB Monetary Policy Decision and Press Conference"),
        ("2026-10-29", "ECB Monetary Policy Decision and Press Conference"),
        ("2026-12-17", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-02-04", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-03-18", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-04-29", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-06-10", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-07-22", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-09-09", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-10-28", "ECB Monetary Policy Decision and Press Conference"),
        ("2027-12-16", "ECB Monetary Policy Decision and Press Conference"),
    ]

    # Sayfa ulaşılabiliyorsa listeyi üret; text boşsa üretme.
    if not text:
        return out

    for date_str, title in events:
        y, m, d = map(int, date_str.split("-"))
        dt = datetime(y, m, d, 12, 45, tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        out.append(_event(
            f"auto_ecb_policy_{dt.strftime('%Y%m%d')}",
            f"{title} {dt.strftime('%d.%m.%Y')}",
            "ECB",
            "rate_decision",
            dt,
            url,
            ["monetary policy decisions", "press conference", "monetary policy statement"],
            "scheduled_decision"
        ))

    return out


def parse_boe_policy():
    text = _read("boe_news") + " " + _read("boe_speeches")
    out = []
    url = "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"

    if not text:
        return out

    events = [
        ("2026-06-18", "BOE MPC Rate Decision and Minutes"),
        ("2026-07-30", "BOE MPC Rate Decision, Minutes and Monetary Policy Report"),
        ("2026-09-17", "BOE MPC Rate Decision and Minutes"),
        ("2026-11-05", "BOE MPC Rate Decision, Minutes and Monetary Policy Report"),
        ("2026-12-17", "BOE MPC Rate Decision and Minutes"),
    ]

    for date_str, title in events:
        y, m, d = map(int, date_str.split("-"))
        dt = datetime(y, m, d, 11, 0, tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        out.append(_event(
            f"auto_boe_mpc_{dt.strftime('%Y%m%d')}",
            title,
            "Bank of England",
            "rate_decision_uk",
            dt,
            url,
            ["monetary policy summary", "minutes", "bank rate", "monetary policy report"],
            "scheduled_decision"
        ))

    return out


def parse_boj_policy():
    text = _read("boj_announcements") + " " + _read("boj_speeches")
    out = []
    url = "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"

    if not text:
        return out

    events = [
        ("2026-06-16", "BOJ Monetary Policy Meeting"),
        ("2026-07-31", "BOJ Monetary Policy Meeting and Outlook Report"),
        ("2026-09-18", "BOJ Monetary Policy Meeting"),
        ("2026-10-30", "BOJ Monetary Policy Meeting and Outlook Report"),
        ("2026-12-18", "BOJ Monetary Policy Meeting"),
    ]

    for date_str, title in events:
        y, m, d = map(int, date_str.split("-"))
        dt = datetime(y, m, d, 3, 0, tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        out.append(_event(
            f"auto_boj_mpm_{dt.strftime('%Y%m%d')}",
            title,
            "Bank of Japan",
            "rate_decision_jp",
            dt,
            url,
            ["statement on monetary policy", "outlook report", "summary of opinions", "minutes"],
            "scheduled_decision"
        ))

    return out


def parse_pboc_policy():
    # PBOC için sabit, temiz bir karar takvimi yok.
    # Bu kaynak şimdilik calendar event üretmez; update_macro_sources_cache.py ile
    # raw/archive + değişiklik takibinde kalır.
    return []


def parse_bls():
    text = _read("bls_calendar")
    out = []
    url = "https://www.bls.gov/schedule/news_release/"

    if not text:
        return out

    # Şu an raw April 2026 sayfası geliyor. İleride ay seçici parser eklenir.
    month = 4
    year = 2026

    wanted = [
        ("Consumer Price Index", "CPI"),
        ("Producer Price Index", "PPI"),
        ("Employment Situation", "Employment Situation / NFP"),
        ("Job Openings and Labor Turnover", "JOLTS"),
        ("Employment Cost Index", "Employment Cost Index"),
        ("Unemployment", "Unemployment Rate"),
        ("Real Earnings", "Real Earnings"),
    ]

    for needle, label in wanted:
        # Örnek: 10 Consumer Price Index March 2026 08:30 AM
        pattern = rf"\b(\d{{1,2}})\s+({re.escape(needle)}[^0-9]{{0,120}}?2026)\s+(\d{{2}}:\d{{2}}\s+[AP]M)"
        for m in re.finditer(pattern, text, flags=re.I):
            day = int(m.group(1))
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            time_s = m.group(3)

            hour, minute = map(int, time_s[:-3].split(":"))
            if "PM" in time_s.upper() and hour != 12:
                hour += 12
            if "AM" in time_s.upper() and hour == 12:
                hour = 0

            try:
                dt = datetime(year, month, day, hour + 4, minute, tzinfo=timezone.utc)
            except ValueError:
                continue

            if dt < datetime.now(timezone.utc):
                continue

            out.append(_event(
                f"auto_bls_{_slug(label)}_{dt.strftime('%Y%m%d%H%M')}",
                f"BLS {label}: {title}",
                "BLS",
                "macro_data",
                dt,
                url,
                ["news release", needle.lower(), label.lower()],
                "macro_data_release"
            ))

    return out


def parse_bea():
    text = _read("bea_calendar")
    out = []
    url = "https://www.bea.gov/news/schedule"

    if not text:
        return out

    # Örnek: May 28 8:30 AM N ews GDP (Second Estimate)...
    pattern = r"\b(May|June|July|August|September|October|November|December)\s+(\d{1,2})\s+(\d{1,2}:\d{2}\s+[AP]M)\s+N\s*ews\s+([^\.]{5,180}?)(?=\s+(?:May|June|July|August|September|October|November|December)\s+\d{1,2}\s+\d{1,2}:\d{2}\s+[AP]M\s+N\s*ews|\s+To Be Announced|$)"

    important = (
        "GDP",
        "Gross Domestic Product",
        "Personal Income and Outlays",
        "Personal Consumption",
        "PCE",
        "International Trade",
        "Retail",
        "Corporate Profits",
    )

    for m in re.finditer(pattern, text, flags=re.I):
        month_name, day_s, time_s, title = m.group(1), m.group(2), m.group(3), m.group(4)
        title = re.sub(r"\s+", " ", title).strip()

        if not any(k.lower() in title.lower() for k in important):
            continue

        month = MONTHS[month_name.lower()]
        day = int(day_s)

        hour, minute = map(int, time_s[:-3].split(":"))
        if "PM" in time_s.upper() and hour != 12:
            hour += 12
        if "AM" in time_s.upper() and hour == 12:
            hour = 0

        # BEA Eastern Time; May-Dec için UTC-4 varsayımı
        dt = datetime(2026, month, day, hour + 4, minute, tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        out.append(_event(
            f"auto_bea_{_slug(title)}_{dt.strftime('%Y%m%d%H%M')}",
            f"BEA {title}",
            "BEA",
            "macro_data",
            dt,
            url,
            ["news release", "gdp", "personal income", "outlays", "pce"],
            "macro_data_release"
        ))

    return out


def parse_tcmb_calendar():
    out = []
    url = "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Takvim"

    events = [
        ("2026-05-14", "TCMB Enflasyon Raporu 2026-II", "inflation_report_tr", "scheduled_report", ["enflasyon raporu", "basın bilgilendirme"]),
        ("2026-05-22", "TCMB Finansal İstikrar Raporu", "financial_stability_tr", "scheduled_report", ["finansal istikrar raporu"]),
        ("2026-06-11", "TCMB PPK Faiz Kararı", "rate_decision_tr", "scheduled_decision", ["para politikası kurulu", "faiz", "karar"]),
        ("2026-06-18", "TCMB PPK Toplantı Özeti", "rate_minutes_tr", "minutes_release", ["toplantı özeti", "para politikası kurulu"]),
        ("2026-07-23", "TCMB PPK Faiz Kararı", "rate_decision_tr", "scheduled_decision", ["para politikası kurulu", "faiz", "karar"]),
        ("2026-07-30", "TCMB PPK Toplantı Özeti", "rate_minutes_tr", "minutes_release", ["toplantı özeti", "para politikası kurulu"]),
        ("2026-08-13", "TCMB Enflasyon Raporu 2026-III", "inflation_report_tr", "scheduled_report", ["enflasyon raporu", "basın bilgilendirme"]),
        ("2026-09-10", "TCMB PPK Faiz Kararı", "rate_decision_tr", "scheduled_decision", ["para politikası kurulu", "faiz", "karar"]),
        ("2026-09-17", "TCMB PPK Toplantı Özeti", "rate_minutes_tr", "minutes_release", ["toplantı özeti", "para politikası kurulu"]),
        ("2026-10-22", "TCMB PPK Faiz Kararı", "rate_decision_tr", "scheduled_decision", ["para politikası kurulu", "faiz", "karar"]),
        ("2026-10-30", "TCMB PPK Toplantı Özeti", "rate_minutes_tr", "minutes_release", ["toplantı özeti", "para politikası kurulu"]),
        ("2026-11-12", "TCMB Enflasyon Raporu 2026-IV", "inflation_report_tr", "scheduled_report", ["enflasyon raporu", "basın bilgilendirme"]),
        ("2026-11-27", "TCMB Finansal İstikrar Raporu", "financial_stability_tr", "scheduled_report", ["finansal istikrar raporu"]),
        ("2026-12-10", "TCMB PPK Faiz Kararı", "rate_decision_tr", "scheduled_decision", ["para politikası kurulu", "faiz", "karar"]),
        ("2026-12-17", "TCMB PPK Toplantı Özeti", "rate_minutes_tr", "minutes_release", ["toplantı özeti", "para politikası kurulu"]),
    ]

    for date_str, title, category, etype, signals in events:
        y, m, d = map(int, date_str.split("-"))
        dt = datetime(y, m, d, 7, 0, tzinfo=timezone.utc)
        if dt < datetime.now(timezone.utc):
            continue

        out.append(_event(
            f"auto_tcmb_{_slug(title)}_{dt.strftime('%Y%m%d')}",
            title,
            "TCMB",
            category,
            dt,
            url,
            signals,
            etype
        ))

    return out


def main(apply=False):
    cache = json.loads(CALENDAR_CACHE.read_text(encoding="utf-8")) if CALENDAR_CACHE.exists() else {"events": []}
    existing = {e.get("id") for e in cache.get("events", [])}

    new = []
    for parser in (parse_fomc, parse_ecb_policy, parse_boe_policy, parse_boj_policy, parse_pboc_policy, parse_bls, parse_bea, parse_tcmb_calendar):
        for ev in parser():
            if ev["id"] not in existing:
                new.append(ev)
                existing.add(ev["id"])

    print("NEW_EVENTS:", len(new))
    for ev in new[:50]:
        print("-", ev["datetime"], "|", ev["source_name"], "|", ev["title"])

    if apply and new:
        cache.setdefault("events", []).extend(new)
        CALENDAR_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("APPLIED:", len(new))

if __name__ == "__main__":
    main("--apply" in sys.argv)
