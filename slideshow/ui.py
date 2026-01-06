import pygame
from typing import Tuple


class UI:
    def __init__(self, screen: pygame.Surface, settings, on_video_select=None):
        self.screen = screen
        self.settings = settings
        self.font = pygame.font.SysFont(None, 36)
        self.menu_open = False
        self.menu_items = [
            {"action": "toggle_mode"},
            {"action": "toggle_exif"},
            {"action": "close"},
        ]
        self.selected = 0
        self.on_video_select = on_video_select

    def toggle_menu(self):
        self.menu_open = not self.menu_open
        if self.menu_open:
            self.selected = 0

    def menu_up(self):
        if not self.menu_open:
            return
        total = len(self.menu_items) + len(self.settings._typed.videos or [])
        self.selected = (self.selected - 1) % total

    def menu_down(self):
        if not self.menu_open:
            return
        total = len(self.menu_items) + len(self.settings._typed.videos or [])
        self.selected = (self.selected + 1) % total

    def menu_select(self):
        if not self.menu_open:
            return
        vids = self.settings._typed.videos or []
        core_count = len(self.menu_items)
        if self.selected < core_count:
            act = self.menu_items[self.selected]['action']
            if act == 'toggle_mode':
                cur = self.settings._typed.mode or 'photos'
                new = 'videos' if cur == 'photos' else 'photos'
                self.settings._typed.mode = new
                try:
                    self.settings.save()
                except Exception:
                    pass
            elif act == 'toggle_exif':
                cur = bool(self.settings._typed.show_exif)
                self.settings._typed.show_exif = (not cur)
                try:
                    self.settings.save()
                except Exception:
                    pass
            elif act == 'close':
                self.menu_open = False
        else:
            # selected a video entry
            vid_index = self.selected - core_count
            if 0 <= vid_index < len(vids):
                # set mode to videos and call callback
                self.settings._typed.mode = 'videos'
                try:
                    self.settings.save()
                except Exception:
                    pass
                if self.on_video_select:
                    try:
                        self.on_video_select(vid_index)
                    except Exception:
                        pass
                # close menu after selecting video
                self.menu_open = False

    def draw_exif_overlay(self, text: str):
        if not self.settings._typed.show_exif:
            return
        surf = self.font.render(text, True, (255, 255, 255))
        w, h = surf.get_size()
        pad = 8
        rect = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
        rect.fill((0, 0, 0, 150))
        rect.blit(surf, (pad, pad))
        self.screen.blit(rect, (10, self.screen.get_height() - h - 20))

    def draw_menu(self):
        if not self.menu_open:
            return
        w, h = self.screen.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        title = self.font.render('Menu (Press M to close)', True, (255, 255, 255))
        self.screen.blit(title, (50, 50))
        # show current mode and instructions
        mode = self.settings._typed.mode or 'photos'
        mtxt = self.font.render(f'Mode: {mode} (press V to toggle)', True, (255, 255, 255))
        self.screen.blit(mtxt, (50, 100))
        # render menu items and highlight selected
        base_y = 160
        vids = self.settings._typed.videos or []
        total_items = self.menu_items + [{"action": "select_video", "path": v} for v in vids]
        for i, item in enumerate(total_items):
            label = ''
            if item.get('action') == 'toggle_mode':
                label = f"Mode: {mode}"
            elif item.get('action') == 'toggle_exif':
                label = f"Show EXIF: {bool(self.settings._typed.show_exif)}"
            elif item.get('action') == 'close':
                label = 'Close Menu'
            elif item.get('action') == 'select_video':
                # display only basename for readability
                import os
                label = os.path.basename(item.get('path'))
            color = (255, 255, 0) if i == self.selected else (200, 200, 200)
            txt = self.font.render(label, True, color)
            self.screen.blit(txt, (70, base_y + i * 40))
