from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    ISTANBUL_TZ = ZoneInfo("Europe/Istanbul") if ZoneInfo else timezone(timedelta(hours=3))
except Exception:
    ISTANBUL_TZ = timezone(timedelta(hours=3))


def parse_datetime(value: str):
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        dt = parsedate_to_datetime(text)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass

    try:
        text2 = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    return None


def age_minutes(value: str, now=None):
    dt = parse_datetime(value)
    if dt is None:
        return None

    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    diff = now_dt - dt.astimezone(timezone.utc)
    return max(0, int(diff.total_seconds() // 60))


def format_age(value: str, now=None):
    minutes = age_minutes(value, now=now)
    if minutes is None:
        return None

    if minutes < 60:
        return f"{minutes} dk"

    hours = minutes // 60
    rem = minutes % 60

    if hours < 24:
        if rem == 0:
            return f"{hours} sa"
        return f"{hours} sa {rem} dk"

    days = hours // 24
    rem_hours = hours % 24

    if rem_hours == 0:
        return f"{days} gün"
    return f"{days} gün {rem_hours} sa"


def format_local_time(value: str):
    dt = parse_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(ISTANBUL_TZ).strftime("%d.%m.%Y %H:%M (İstanbul)")


def format_istanbul_datetime(value: str):
    return format_local_time(value)
