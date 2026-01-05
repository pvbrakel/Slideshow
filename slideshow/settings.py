import json
import threading
import time
from pathlib import Path

DEFAULTS = {
    "folders": ["./images"],
    "interval_seconds": 6,
    "prefetch_count": 4,
    "transition_duration": 0.6,
    "night_mode": {"enabled": True, "start": "23:00", "end": "06:00"},
    "show_exif": True,
    "randomize": True,
    "scale_policy": "cover",
}


class Settings:
    def __init__(self, path: str = 'settings.json'):
        self.path = Path(path)
        self._data = DEFAULTS.copy()
        self._mtime = 0
        self.load()
        self._watch_thread = None
        self._callbacks = []

    def load(self):
        if self.path.exists():
            try:
                mtime = self.path.stat().st_mtime
                if mtime == self._mtime:
                    return
                with self.path.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                self._data.update(data)
                self._mtime = mtime
            except Exception:
                pass

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def start_watching(self, interval=2.0):
        if self._watch_thread:
            return

        def watch():
            while True:
                try:
                    self.load()
                    for cb in self._callbacks:
                        cb()
                except Exception:
                    pass
                time.sleep(interval)

        t = threading.Thread(target=watch, daemon=True)
        t.start()
        self._watch_thread = t

    def on_change(self, cb):
        self._callbacks.append(cb)

    def save(self):
        try:
            with self.path.open('w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2)
            self._mtime = self.path.stat().st_mtime
        except Exception:
            pass
