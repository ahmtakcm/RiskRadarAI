import json
import os
import threading
from pathlib import Path
from config.paths import STORAGE_DIR


class StateStore:
    def __init__(self):
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.runtime_path = STORAGE_DIR / 'runtime_state.json'
        self.source_health_path = STORAGE_DIR / 'source_health.json'
        self._lock = threading.RLock()

    def _load_json(self, path: Path):
        if not path.exists():
            return {}
        try:
            with self._lock:
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {}

    def _save_json(self, path: Path, data):
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        tmp_path = path.with_name(f'.{path.name}.tmp')
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(payload, encoding='utf-8')
            with tmp_path.open('r+', encoding='utf-8') as fh:
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)

    def load_runtime_state(self):
        return self._load_json(self.runtime_path)

    def save_runtime_state(self, state):
        self._save_json(self.runtime_path, state)

    def load_source_health(self):
        return self._load_json(self.source_health_path)

    def save_source_health(self, health):
        self._save_json(self.source_health_path, health)
