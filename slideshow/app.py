import pygame
import random
import time
from pathlib import Path

from .settings import Settings
from .loader import scan_folders
from .exif import get_month_year_or_folder
from .utils import scale_to_cover
from .transitions import fade_transition
from .ui import UI
from .videos import VideoPlayer
from .input import map_event_to_action
from .cache import ImageCache


class SlideshowApp:
    def __init__(self):
        pygame.init()
        self.settings = Settings('settings.json')
        self.settings.on_change(self._on_settings_changed)
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        self.ui = UI(self.screen, self.settings, on_video_select=self._select_video)
        self.images = []
        self.index = 0
        self.paused = False
        self.last_switch = time.time()
        self.current_surf = None
        self.current_path = None
        self.mode = self.settings.get('mode', 'photos')
        self.video_player = VideoPlayer(self.settings.get('videos') or [])
        self.cache = ImageCache(maxsize=128)
        self._in_menu = False
        self._paused_before_menu = False

    def load_images(self):
        folders = self.settings.get('folders') or ['./images']
        imgs = scan_folders(folders)
        if self.settings.get('randomize', True):
            random.shuffle(imgs)
        self.images = imgs
        # prefetch initial images
        if self.images:
            self.cache.prefetch(self.images[: self.settings.get('prefetch_count', 4)], target_size=self.screen.get_size())

    def load_surface(self, path):
        try:
            surf = pygame.image.load(path)
            surf = surf.convert()
        except Exception:
            # fallback: try via Pillow
            from PIL import Image
            img = Image.open(path)
            img = img.convert('RGBA')
            mode = img.mode
            size = img.size
            data = img.tobytes()
            surf = pygame.image.fromstring(data, size, mode)
        # scale according to settings policy ('cover' or 'fit')
        policy = self.settings.get('scale_policy', 'cover')
        from .utils import scale_image
        surf = scale_image(surf, self.screen.get_size(), policy=policy)
        return surf

    def current_exif_text(self):
        if not self.current_path:
            return ''
        return get_month_year_or_folder(self.current_path)

    def is_in_night(self):
        nm = self.settings.get('night_mode', {})
        if not nm.get('enabled'):
            return False
        start = nm.get('start', '23:00')
        end = nm.get('end', '06:00')
        from datetime import datetime, time as dtime
        now = datetime.now().time()
        sh, sm = map(int, start.split(':'))
        eh, em = map(int, end.split(':'))
        s = dtime(sh, sm)
        e = dtime(eh, em)
        if s <= e:
            return s <= now < e
        else:
            return now >= s or now < e

    def run(self):
        self.settings.start_watching()
        self.load_images()
        # initialize mode resources
        if self.mode == 'photos':
            if not self.images:
                print('No images found in folders:', self.settings.get('folders'))
                return
            self.index = 0
            self.current_path = self.images[self.index]
            self.current_surf = self.load_surface(self.current_path)
        else:
            # videos mode
            if not (self.settings.get('videos') or []):
                print('No videos configured in settings.json')
                return
            self.video_player.load_current_clip()
            policy = str(self.settings.get('scale_policy') or 'cover')
            self.current_surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                action = map_event_to_action(event, settings=self.settings)
                # menu navigation handling (when menu is open)
                if action in ('menu_up', 'menu_down', 'menu_select') and self.ui.menu_open:
                    if action == 'menu_up':
                        self.ui.menu_up()
                        continue
                    if action == 'menu_down':
                        self.ui.menu_down()
                        continue
                    if action == 'menu_select':
                        self.ui.menu_select()
                        # apply settings changes immediately
                        self._on_settings_changed()
                        continue

                if action == 'quit':
                    running = False
                elif action == 'next':
                    if self.mode == 'photos':
                        self.next_image()
                    else:
                        self.video_player.next()
                elif action == 'prev':
                    if self.mode == 'photos':
                        self.prev_image()
                    else:
                        self.video_player.prev()
                elif action == 'pause':
                    self.paused = not self.paused
                elif action == 'menu':
                    self.ui.toggle_menu()
                    # menu toggled; handled below in menu paused state logic
                elif action == 'toggle_mode':
                    # toggle between photos and videos
                    new_mode = 'videos' if self.mode == 'photos' else 'photos'
                    self.mode = new_mode
                    self.settings._data['mode'] = new_mode
                    self.settings.save()
                    # apply immediately
                    self._on_settings_changed()

            # pause slideshow timer while menu is open
            if self.ui.menu_open:
                if not self._in_menu:
                    self._in_menu = True
                    self._paused_before_menu = self.paused
                    self.paused = True
            else:
                if self._in_menu:
                    self._in_menu = False
                    # restore paused state from before menu opened
                    self.paused = self._paused_before_menu

            if self.is_in_night():
                # during night, do not advance images or videos
                self.paused = True

            now = time.time()
            interval = self.settings.get('interval_seconds', 6)
            if not self.paused and self.mode == 'photos' and (now - self.last_switch) >= interval:
                self.next_image()

            # draw current
            self.screen.fill((0, 0, 0))
            if self.mode == 'photos':
                if self.current_surf:
                    rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
                    from .utils import blit_scaled_with_echo
                    blit_scaled_with_echo(self.screen, self.current_surf, rect)
            else:
                surf = None
                if not self.paused:
                    policy = str(self.settings.get('scale_policy') or 'cover')
                    surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)
                if surf:
                    rect = surf.get_rect(center=self.screen.get_rect().center)
                    self.screen.blit(surf, rect.topleft)

            # exif overlay
            self.ui.draw_exif_overlay(self.current_exif_text())
            # menu
            self.ui.draw_menu()

            pygame.display.flip()
            self.clock.tick(60)

        # cleanup
        try:
            self.cache.stop()
        except Exception:
            pass
        pygame.quit()

    def next_image(self):
        if not self.images:
            return
        prev_surf = self.current_surf
        self.index = (self.index + 1) % len(self.images)
        self.current_path = self.images[self.index]
        self.current_surf = self.load_surface(self.current_path)
        self.last_switch = time.time()
        # transition: compute positions so transition matches later centering
        try:
            if prev_surf:
                prev_rect = prev_surf.get_rect(center=self.screen.get_rect().center)
                dst_rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
                fade_transition(
                    self.screen,
                    prev_surf,
                    self.current_surf,
                    self.settings.get('transition_duration', 0.6),
                    src_pos=prev_rect.topleft,
                    dst_pos=dst_rect.topleft,
                )
            else:
                fade_transition(self.screen, self.current_surf, self.current_surf, self.settings.get('transition_duration', 0.6))
        except Exception:
            pass

    def prev_image(self):
        if not self.images:
            return
        prev_surf = self.current_surf
        self.index = (self.index - 1) % len(self.images)
        self.current_path = self.images[self.index]
        self.current_surf = self.load_surface(self.current_path)
        self.last_switch = time.time()
        try:
            if prev_surf:
                prev_rect = prev_surf.get_rect(center=self.screen.get_rect().center)
                dst_rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
                fade_transition(
                    self.screen,
                    prev_surf,
                    self.current_surf,
                    self.settings.get('transition_duration', 0.6),
                    src_pos=prev_rect.topleft,
                    dst_pos=dst_rect.topleft,
                )
            else:
                fade_transition(self.screen, self.current_surf, self.current_surf, self.settings.get('transition_duration', 0.6))
        except Exception:
            pass

    def _on_settings_changed(self):
        new_mode = self.settings.get('mode', 'photos')
        if new_mode == self.mode:
            return
        self.mode = new_mode
        if self.mode == 'videos':
            self.video_player = VideoPlayer(self.settings.get('videos') or [])
            self.video_player.load_current_clip()
            policy = str(self.settings.get('scale_policy') or 'cover')
            self.current_surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)
        else:
            self.load_images()
            if self.images:
                self.index = 0
                self.current_path = self.images[self.index]
                self.current_surf = self.load_surface(self.current_path)

    def _select_video(self, index: int):
        vids = self.settings.get('videos') or []
        if not vids:
            return
        if index < 0 or index >= len(vids):
            return
        # switch to video mode and load the selected clip
        self.settings._data['mode'] = 'videos'
        try:
            self.settings.save()
        except Exception:
            pass
        self.mode = 'videos'
        self.video_player = VideoPlayer(vids)
        self.video_player.index = index
        self.video_player.load_current_clip()
        policy = str(self.settings.get('scale_policy') or 'cover')
        self.current_surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)
