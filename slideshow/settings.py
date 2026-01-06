import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class NightMode:
    enabled: bool = True
    start: str = "23:00"
    end: str = "06:00"


@dataclass
class SettingsSchema:
    folders: List[str] = field(default_factory=lambda: ["./images"])
    interval_seconds: int = 6
    prefetch_count: int = 4
    transition_duration: float = 0.6
    night_mode: NightMode = field(default_factory=NightMode)
    show_exif: bool = True
    randomize: bool = True
    scale_policy: str = "cover"
    mode: Optional[str] = None
    videos: List[str] = field(default_factory=list)
    key_bindings: Dict[str, List[str]] = field(default_factory=dict)


DEFAULTS = asdict(SettingsSchema())


class Settings:
    """Typed settings wrapper.

    Internally maintains a `SettingsSchema` instance for strong typing and
    validation, but preserves the older dict-like `_data` API for compatibility
    with the rest of the codebase (e.g. `get`, direct `_data` edits in UI).
    """

    def __init__(self, path: str = 'settings.json'):
        self.path = Path(path)
        self._typed = SettingsSchema()
        self._data: Dict[str, Any] = DEFAULTS.copy()
        self._mtime = 0
        self._watch_thread = None
        self._callbacks = []
        # track which file was actually loaded (may be host-specific)
        self._active_file: Path = self.path
        self.load()

    def _coerce(self, raw: Dict[str, Any]) -> SettingsSchema:
        """Coerce raw dict into SettingsSchema, applying basic type conversions."""
        # start from defaults
        merged = DEFAULTS.copy()
        merged.update(raw or {})
        # night_mode may be a dict
        nm = merged.get('night_mode') or {}
        if not isinstance(nm, dict):
            nm = {}
        night = NightMode(
            enabled=bool(nm.get('enabled', True)),
            start=str(nm.get('start', '23:00')),
            end=str(nm.get('end', '06:00')),
        )
        try:
            folders = list(merged.get('folders') or DEFAULTS['folders'])
        except Exception:
            folders = DEFAULTS['folders']
        try:
            videos = list(merged.get('videos') or [])
        except Exception:
            videos = []
        try:
            interval = int(merged.get('interval_seconds') or DEFAULTS['interval_seconds'])
        except Exception:
            interval = DEFAULTS['interval_seconds']
        try:
            prefetch = int(merged.get('prefetch_count') or DEFAULTS['prefetch_count'])
        except Exception:
            prefetch = DEFAULTS['prefetch_count']
        try:
            trans = float(merged.get('transition_duration') or DEFAULTS['transition_duration'])
        except Exception:
            trans = DEFAULTS['transition_duration']
        return SettingsSchema(
            folders=folders,
            interval_seconds=interval,
            prefetch_count=prefetch,
            transition_duration=trans,
            night_mode=night,
            show_exif=bool(merged.get('show_exif', DEFAULTS['show_exif'])),
            randomize=bool(merged.get('randomize', DEFAULTS['randomize'])),
            scale_policy=str(merged.get('scale_policy', DEFAULTS['scale_policy'])),
            mode=merged.get('mode'),
            videos=videos,
            key_bindings=merged.get('key_bindings') or {},
        )

    def load(self):
        # Support host-specific overrides: if a file named like
        # settings.<hostname>.json exists next to the configured path, prefer
        # that when loading. This lets machines override settings locally.
        import socket
        try:
            hostname = socket.gethostname()
        except Exception:
            hostname = None

        target = self.path
        if hostname:
            hostfile = self.path.with_name(f"{self.path.stem}.{hostname}{self.path.suffix}")
            if hostfile.exists():
                target = hostfile

        if not target.exists():
            return False
        try:
            mtime = target.stat().st_mtime
            if mtime == self._mtime:
                return False
            with target.open('r', encoding='utf-8') as f:
                raw = json.load(f)
            self._typed = self._coerce(raw)
            # keep a dict copy for compatibility
            self._data = asdict(self._typed)
            # nested dataclass turned to dict
            self._data['night_mode'] = asdict(self._typed.night_mode)
            self._mtime = mtime
            # remember which file we loaded so saves go to the same file
            self._active_file = target
            return True
        except Exception:
            # on any parse error, keep existing typed settings
            return False

    def get(self, key, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def start_watching(self, interval=2.0):
        if self._watch_thread:
            return

        def watch():
            while True:
                try:
                    changed = False
                    try:
                        changed = self.load()
                    except Exception:
                        # fallback: attempt to load but don't crash watcher
                        try:
                            self.load()
                            changed = True
                        except Exception:
                            changed = False
                    if changed:
                        for cb in self._callbacks:
                            try:
                                cb()
                            except Exception:
                                pass
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
            # persist the typed settings only
            to_dump = asdict(self._typed)
            # write to the active file (host-specific if that was loaded)
            try:
                write_target = getattr(self, '_active_file', self.path) or self.path
            except Exception:
                write_target = self.path
            with write_target.open('w', encoding='utf-8') as f:
                json.dump(to_dump, f, indent=2)
            self._mtime = write_target.stat().st_mtime
        except Exception:
            pass
