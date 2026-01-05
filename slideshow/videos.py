import time
import threading
from typing import List, Optional

import pygame


class VideoPlayer:
    def __init__(self, paths: List[str]):
        self.paths = paths or []
        self.index = 0
        self.clip = None
        self.disabled = False
        self._last_surface = None
        self._last_time = 0.0
        self._fps = 24.0
        try:
            import moviepy.editor as mpy
            self.mpy = mpy
        except Exception:
            self.mpy = None
            self.disabled = True

    def load_current_clip(self):
        if self.disabled or not self.paths:
            return
        path = self.paths[self.index]
        try:
            self.clip = self.mpy.VideoFileClip(path)
            self._fps = getattr(self.clip, 'fps', 24.0) or 24.0
            self._start_time = time.time()
        except Exception:
            self.clip = None

    def next(self):
        if not self.paths:
            return
        self.index = (self.index + 1) % len(self.paths)
        self.load_current_clip()

    def prev(self):
        if not self.paths:
            return
        self.index = (self.index - 1) % len(self.paths)
        self.load_current_clip()

    def get_surface(self, target_size, policy: str = 'cover') -> Optional[pygame.Surface]:
        if self.disabled:
            return None
        if not self.clip:
            self.load_current_clip()
            if not self.clip:
                return None
        # compute frame time
        t = (time.time() - self._start_time) % max(0.001, self.clip.duration)
        # throttle frame decoding to fps
        if (time.time() - self._last_time) < (1.0 / self._fps):
            return self._last_surface
        try:
            frame = self.clip.get_frame(t)  # numpy array HxWx3 RGB
            import numpy as np
            arr = np.array(frame)
            # convert to pygame surface (swap axes to WxH)
            surf = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
            surf = surf.convert()
            # scale according to provided policy (default to cover)
            from .utils import scale_image
            surf = scale_image(surf, target_size, policy=policy)
            self._last_surface = surf
            self._last_time = time.time()
            return surf
        except Exception:
            return self._last_surface
