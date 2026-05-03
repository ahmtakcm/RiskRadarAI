import subprocess
from core.logger import get_logger

logger = get_logger("daily_macro_update")


def run_daily_update():
    try:
        logger.info("Makro kaynak güncelleme başlıyor")

        subprocess.run(
            ["python", "scripts/update_macro_sources_cache.py"],
            check=True
        )

        subprocess.run(
            ["python", "scripts/generate_macro_calendar_events.py", "--apply"],
            check=True
        )

        logger.info("Makro kaynak güncelleme tamamlandı")

    except Exception as e:
        logger.warning("Günlük makro update hata: %s", e)
