import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ExifTags

_ORIENT_TAG = {v: k for k, v in ExifTags.TAGS.items()}.get('Orientation')


class ImageCache:
    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self.cache = OrderedDict()  # path -> (pil_image, mtime)
        self.lock = threading.Lock()
        self.queue = deque()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._stop = threading.Event()
        self._thread.start()

    def _load_pil(self, path: str, target_size: Optional[Tuple[int, int]] = None):
        p = Path(path)
        try:
            img = Image.open(p)
            # apply orientation if present
            try:
                exif = img._getexif() or {}
                orient = None
                if _ORIENT_TAG and _ORIENT_TAG in exif:
                    orient = exif[_ORIENT_TAG]
                if orient == 3:
                    img = img.rotate(180, expand=True)
                elif orient == 6:
                    img = img.rotate(270, expand=True)
                elif orient == 8:
                    img = img.rotate(90, expand=True)
            except Exception:
                pass
            if target_size:
                img.thumbnail(target_size, Image.LANCZOS)
            img = img.convert('RGBA')
            return img
        except Exception:
            return None

    def _worker(self):
        while not self._stop.is_set():
            try:
                path, target_size = None, None
                with self.lock:
                    if self.queue:
                        path, target_size = self.queue.popleft()
                if not path:
                    time.sleep(0.1)
                    continue
                pil = self._load_pil(path, target_size)
                if pil is None:
                    continue
                mtime = Path(path).stat().st_mtime
                with self.lock:
                    self.cache[path] = (pil, mtime)
                    self.cache.move_to_end(path)
                    while len(self.cache) > self.maxsize:
                        self.cache.popitem(last=False)
            except Exception:
                time.sleep(0.1)

    def prefetch(self, paths, target_size: Optional[Tuple[int, int]] = None):
        with self.lock:
            for p in paths:
                if p in self.cache:
                    continue
                self.queue.append((p, target_size))

    def get_pil(self, path: str) -> Optional[Image.Image]:
        with self.lock:
            item = self.cache.get(path)
            if not item:
                return None
            pil, _ = item
            # update LRU
            self.cache.move_to_end(path)
            return pil.copy()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)
