import time

def should_send_alert(state: dict, key: str, cooldown: int) -> bool:
    last_sent = state.get('last_alert_times', {}).get(key)
    if not last_sent:
        return True
    return (time.time() - last_sent) > cooldown


def mark_alert_sent(state: dict, key: str):
    state.setdefault('last_alert_times', {})[key] = time.time()
