import subprocess
import sys
from core.logger import get_logger

logger = get_logger("daily_macro_update")


def run_daily_update():
    current_step = ""
    try:
        logger.info("Makro kaynak güncelleme başlıyor")

        steps = [
            ("update_macro_sources_cache", [sys.executable, "scripts/update_macro_sources_cache.py"]),
            ("generate_macro_calendar_events", [sys.executable, "scripts/generate_macro_calendar_events.py", "--apply"]),
        ]
        for current_step, command in steps:
            subprocess.run(command, check=True, timeout=300)

        logger.info("Makro kaynak güncelleme tamamlandı")

    except Exception as e:
        logger.warning("Günlük makro update hata | step=%s | hata=%s", current_step or "unknown", e)
