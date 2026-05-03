import json
from pathlib import Path
from config.paths import STORAGE_DIR

class StateStore:
    def __init__(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.runtime_path = STORAGE_DIR / 'runtime_state.json'
        self.source_health_path = STORAGE_DIR / 'source_health.json'

    def load_runtime_state(self):
        if not self.runtime_path.exists():
            return {}
        try:
            return json.loads(self.runtime_path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save_runtime_state(self, state):
        self.runtime_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    def load_source_health(self):
        if not self.source_health_path.exists():
            return {}
        try:
            return json.loads(self.source_health_path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def save_source_health(self, health):
        self.source_health_path.write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding='utf-8')
