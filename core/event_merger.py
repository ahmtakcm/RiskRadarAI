import json
import os
import re
import threading
import time
from enrichers.text_hygiene import improve_summary_text
from config.paths import STORAGE_DIR

STATE_PATH = STORAGE_DIR / "event_cluster_state.json"
COOLDOWN_SECONDS = 1800
_STATE_LOCK = threading.RLock()


KEYWORDS = {
    "hormuz": ["hormuz", "hürmüz", "strait of hormuz"],
    "iran": ["iran", "tehran", "tahran"],
    "israel": ["israel", "israil", "gaza", "palestine"],
    "russia": ["russia", "russian", "moscow", "kremlin", "mfa"],
    "ukraine": ["ukraine", "ukrainian", "kyiv", "donbas"],
    "starobelsk": ["starobelsk", "starobilsk"],
    "oil": ["oil", "petrol", "brent", "crude", "opec"],
    "defense": ["centcom", "defense", "strike", "missile", "drone", "navy"],
}


def _txt(item):
    return f"{item.get('title','')} {item.get('summary','')} {item.get('content','')}".lower()


def cluster_key(item):
    text = _txt(item)
    hits = []

    for key, words in KEYWORDS.items():
        if any(w in text for w in words):
            hits.append(key)

    if "hormuz" in hits:
        return "hormuz-iran-oil"

    if "iran" in hits and "israel" in hits:
        return "iran-israel"

    if "iran" in hits and "defense" in hits:
        return "iran-defense"

    if "russia" in hits and "starobelsk" in hits:
        return "russia-ukraine-starobelsk"

    if "ukraine" in hits and "starobelsk" in hits:
        return "russia-ukraine-starobelsk"

    if "russia" in hits and "ukraine" in hits:
        return "russia-ukraine"

    if "oil" in hits:
        return "oil-energy"

    if hits:
        return "-".join(hits[:3])

    source = item.get("source_name", "general")
    title = re.sub(r"[^a-z0-9]+", "-", item.get("title", "").lower()).strip("-")
    return f"{source}:{title[:40]}"


def _load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        with _STATE_LOCK:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(data):
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp_path = STATE_PATH.with_name(f".{STATE_PATH.name}.tmp")
    with _STATE_LOCK:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(payload, encoding="utf-8")
        with tmp_path.open("r+", encoding="utf-8") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, STATE_PATH)


def _score_of(item):
    for key in ("score", "risk_score", "alarm_score", "priority"):
        try:
            return int(item.get(key) or 0)
        except Exception:
            pass
    return 0


def should_send_cluster(cluster, items):
    state = _load_state()
    now = int(time.time())

    score = max((_score_of(x) for x in items), default=0)
    prev = state.get(cluster, {})

    last_ts = int(prev.get("ts", 0))
    last_count = int(prev.get("count", 0))
    last_score = int(prev.get("score", 0))

    send = False

    if now - last_ts > COOLDOWN_SECONDS:
        send = True
    elif len(items) > last_count:
        send = True
    elif score > last_score:
        send = True

    if send:
        state[cluster] = {
            "ts": now,
            "count": len(items),
            "score": score,
        }
        _save_state(state)

    return send


def build_alert(cluster, items):
    top = max(items, key=_score_of)
    sources = []
    for x in items:
        s_name = x.get("source_name")
        if s_name and s_name not in sources:
            sources.append(s_name)

    title = top.get("title") or cluster.upper()
    url = top.get("url") or top.get("link") or ""
    raw_summary = top.get("summary") or top.get("content") or title or ""

    summary = improve_summary_text(
        raw_summary,
        title=title,
        source=top.get("source_name") or top.get("source") or "",
        topic=cluster,
    )

    return f"""🔴 KRİTİK ALARM

Konu: {cluster.upper()}
Başlık: {title}

Kaynaklar: {', '.join(sources[:5])}
Teyit: {len(sources)} kaynak

Özet:
{summary[:500]}

Kaynak:
{url}
""".strip()


def group_items(items):
    groups = {}
    for item in items:
        key = cluster_key(item)
        groups.setdefault(key, []).append(item)
    return groups


def build_cluster_alerts(items):
    alerts = []
    for cluster, group in group_items(items).items():
        if len(group) < 2:
            continue
        if should_send_cluster(cluster, group):
            alerts.append(build_alert(cluster, group))
    return alerts
