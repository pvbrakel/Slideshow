import time
from typing import List, Optional
from pyvidplayer2 import Video
import pygame

class VideoPlayer:
    def __init__(self, screen: pygame.Surface, paths: List[str]):
        self.paths = paths or []
        self.index = 0
        self.clip = None
        self.disabled = False
        self.vid: Video = None
        self.screen = screen

    def load_current_clip(self):
        if self.disabled or not self.paths:
            return
        path = self.paths[self.index]
        try:
            self.vid = Video(path)
        except Exception:
            self.vid = None

    def tick(self):
        if self.vid.draw(self.screen, (0, 0), force_draw=False):
            pygame.display.update()
    
    def stop(self):
        if self.vid:
            self.vid.stop()

    def start(self):
        if self.vid:
            self.vid.play()