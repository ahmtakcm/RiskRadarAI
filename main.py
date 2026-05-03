from pathlib import Path

from app import bootstrap
from single_instance import single_instance

BASE_DIR = Path(__file__).resolve().parent


if __name__ == "__main__":
    with single_instance("RiskRadarAI", BASE_DIR / "storage" / "RiskRadarAI.lock"):
        bootstrap.run()
