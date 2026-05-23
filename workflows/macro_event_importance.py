LEVEL_SUPPRESS = 0
LEVEL_CRITICAL = 1
LEVEL_HIGH = 2
LEVEL_WATCH = 3

DEFAULT_PRE_ALERTS = [1440, 180, 60, 30]
HIGH_PRE_ALERTS = [1440, 180]
WATCH_PRE_ALERTS = []

CENTRAL_BANK_SOURCES = {
    "federal reserve",
    "federal reserve fomc",
    "fomc",
    "ecb",
    "bank of england",
    "bank of japan",
    "tcmb",
}

CRITICAL_EVENT_TERMS = {
    "rate decision",
    "policy decision",
    "monetary policy decision",
    "fomc meeting",
    "mpc rate decision",
    "ppk faiz",
    "faiz karari",
    "faiz kararı",
}

CRITICAL_DATA_TERMS = {
    "cpi",
    "consumer price index",
    "pce",
    "personal consumption",
    "employment situation",
    "nonfarm",
    "nfp",
}

HIGH_DATA_TERMS = {
    "gdp",
    "gross domestic product",
    "unemployment",
    "pmi",
    "retail sales",
    "industrial production",
    "housing",
    "building permits",
    "jolts",
    "employment cost index",
}

PERSONNEL_TERMS = {
    "chair",
    "governor",
    "president",
    "nomination",
    "nominee",
    "appointed",
    "resigns",
    "resignation",
    "steps down",
}

SYSTEMIC_TERMS = {
    "systemic risk",
    "financial stability",
    "debt crisis",
    "emergency",
    "sanctions",
    "capital controls",
    "liquidity",
}


def _to_float(value) -> float | None:
    if value is None:
        return None
    cleaned = str(value).strip().replace("%", "").replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _blob(event: dict) -> str:
    return " ".join(
        str(event.get(key) or "")
        for key in ("title", "summary", "description", "category", "event_type", "source_name")
    ).lower()


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def classify_macro_event(event: dict) -> dict:
    text = _blob(event)
    source = str(event.get("source_name") or "").lower()
    category = str(event.get("category") or "").lower()
    event_type = str(event.get("event_type") or "").lower()

    is_central_bank = source in CENTRAL_BANK_SOURCES or "central_bank" in category
    is_scheduled_central_bank = is_central_bank and event_type in {
        "scheduled_decision",
        "scheduled_report",
        "minutes_release",
    }
    is_rate_decision = event_type == "scheduled_decision" or _has_any(text, CRITICAL_EVENT_TERMS)
    is_personnel = is_central_bank and _has_any(text, PERSONNEL_TERMS)
    is_critical_data = _has_any(text, CRITICAL_DATA_TERMS)
    is_high_data = _has_any(text, HIGH_DATA_TERMS)
    is_systemic = _has_any(text, SYSTEMIC_TERMS)

    if is_scheduled_central_bank or is_rate_decision or is_personnel or is_systemic or is_critical_data:
        return {
            "importance_level": LEVEL_CRITICAL,
            "importance_score": 90,
            "importance_reason": "kritik makro olay",
            "notification_strategy": "full_countdown",
            "recommended_pre_alerts_minutes": DEFAULT_PRE_ALERTS,
        }
    if is_high_data:
        return {
            "importance_level": LEVEL_HIGH,
            "importance_score": 75,
            "importance_reason": "yüksek etkili makro veri",
            "notification_strategy": "heads_up_and_published",
            "recommended_pre_alerts_minutes": HIGH_PRE_ALERTS,
        }
    if "macro_data" in category or "speech" in category or "minutes" in event_type:
        return {
            "importance_level": LEVEL_WATCH,
            "importance_score": 50,
            "importance_reason": "izleme düzeyi makro olay",
            "notification_strategy": "digest_or_published",
            "recommended_pre_alerts_minutes": WATCH_PRE_ALERTS,
        }

    return {
        "importance_level": LEVEL_WATCH,
        "importance_score": 45,
        "importance_reason": "genel makro olay",
        "notification_strategy": "digest_or_published",
        "recommended_pre_alerts_minutes": WATCH_PRE_ALERTS,
    }


def calculate_surprise(event: dict) -> dict:
    actual = _to_float(event.get("actual"))
    forecast = _to_float(event.get("forecast"))
    if actual is None or forecast is None:
        return {"surprise_score": 0, "surprise_direction": "none"}

    diff = actual - forecast
    if forecast:
        relative = abs(diff) / abs(forecast) * 100
    else:
        relative = abs(diff) * 100

    score = min(100, int(round(relative * 10)))
    if diff > 0:
        direction = "above_forecast"
    elif diff < 0:
        direction = "below_forecast"
    else:
        direction = "in_line"

    return {
        "surprise_score": score,
        "surprise_direction": direction,
        "surprise_value": diff,
    }


def enrich_macro_event(event: dict) -> dict:
    metadata = classify_macro_event(event)
    surprise = calculate_surprise(event)
    surprise_score = surprise["surprise_score"]

    if surprise_score >= 75:
        metadata = {
            **metadata,
            "importance_level": LEVEL_CRITICAL,
            "importance_score": max(metadata["importance_score"], 95),
            "importance_reason": "kritik makro sapma",
            "notification_strategy": "full_countdown",
            "recommended_pre_alerts_minutes": DEFAULT_PRE_ALERTS,
        }
    elif surprise_score >= 30 and metadata["importance_level"] == LEVEL_WATCH:
        metadata = {
            **metadata,
            "importance_level": LEVEL_HIGH,
            "importance_score": max(metadata["importance_score"], 75),
            "importance_reason": "yüksek etkili makro sapma",
            "notification_strategy": "heads_up_and_published",
            "recommended_pre_alerts_minutes": HIGH_PRE_ALERTS,
        }

    current_score = _to_float(event.get("importance_score")) or 0
    if metadata["importance_score"] > current_score:
        event["importance_level"] = metadata["importance_level"]
        event["importance_score"] = metadata["importance_score"]
        event["importance_reason"] = metadata["importance_reason"]
        event["notification_strategy"] = metadata["notification_strategy"]
        event["pre_alerts_minutes"] = metadata["recommended_pre_alerts_minutes"]
    else:
        event.setdefault("importance_level", metadata["importance_level"])
        event.setdefault("importance_score", metadata["importance_score"])
        event.setdefault("importance_reason", metadata["importance_reason"])
        event.setdefault("notification_strategy", metadata["notification_strategy"])
        event.setdefault("pre_alerts_minutes", metadata["recommended_pre_alerts_minutes"])

    event["surprise_score"] = surprise_score
    event["surprise_direction"] = surprise["surprise_direction"]
    if "surprise_value" in surprise:
        event["surprise_value"] = surprise["surprise_value"]
    else:
        event.pop("surprise_value", None)
    return event
