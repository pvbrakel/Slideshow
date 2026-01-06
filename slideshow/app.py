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

class SlideshowApp:
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False)
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
        self.current_bg = None
        self.mode = self.settings._typed.mode or 'photos'
        self.video_player = VideoPlayer(self.settings._typed.videos or [])
        self._in_menu = False
        self._paused_before_menu = False

    def load_images(self):
        folders = self.settings._typed.folders or ['./images']
        imgs = scan_folders(folders)
        if self.settings._typed.randomize:
            random.shuffle(imgs)
        self.images = imgs

    def load_surface(self, path):
        try:
            surf = pygame.image.load(path)
            surf = surf.convert()
        except Exception:
            # fallback: try via Pillow
            from PIL import Image
            img = Image.open(path)
            img = img.convert('RGBA')
            mode = 'RGBA'
            size = img.size
            data = img.tobytes()
            surf = pygame.image.fromstring(data, size, mode)
        # scale according to settings policy ('cover' or 'fit')
        policy = self.settings._typed.scale_policy or 'cover'
        from .utils import scale_image
        surf = scale_image(surf, self.screen.get_size(), policy=policy)
        # ensure optimal pixel format for fast blitting
        try:
            if surf.get_alpha() is None:
                surf = surf.convert()
            else:
                surf = surf.convert_alpha()
        except Exception:
            pass
        return surf

    def current_exif_text(self):
        if not self.current_path:
            return ''
        return get_month_year_or_folder(self.current_path)

    def is_in_night(self):
        nm = self.settings._typed.night_mode
        if not nm.enabled:
            return False
        start = nm.start or '23:00'
        end = nm.end or '06:00'
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
                print('No images found in folders:', self.settings._typed.folders)
                return
            self.index = 0
            self.current_path = self.images[self.index]
            self.current_surf = self.load_surface(self.current_path)
            # precompute echo background for current image
            try:
                from .utils import make_echo_background
                rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
                self.current_bg = make_echo_background(self.current_surf, self.screen.get_size(), rect, enable_echo=self.settings._typed.enable_echo)
            except Exception:
                self.current_bg = None
        else:
            # videos mode
            if not (self.settings._typed.videos or []):
                print('No videos configured in settings.json')
                return
            self.video_player.load_current_clip()
            policy = str(self.settings._typed.scale_policy or 'cover')
            self.current_surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)
            self.current_bg = None

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
                    # update typed settings and persist
                    self.settings._typed.mode = new_mode
                    try:
                        self.settings.save()
                    except Exception:
                        pass
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
            interval = self.settings._typed.interval_seconds
            if not self.paused and self.mode == 'photos' and (now - self.last_switch) >= interval:
                self.next_image()

            # draw current
            # draw current
            # prefer precomputed background for echoes to avoid per-frame blur work
            if self.mode == 'photos':
                if self.current_surf:
                    rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
                    # blit precomputed background if available
                    if self.current_bg is not None:
                        try:
                            self.screen.blit(self.current_bg, (0, 0))
                        except Exception:
                            self.screen.fill((0, 0, 0))
                    else:
                        self.screen.fill((0, 0, 0))
                    self.screen.blit(self.current_surf, rect.topleft)
            else:
                surf = None
                if not self.paused:
                    policy = str(self.settings._typed.scale_policy or 'cover')
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
                # perform fade only if transitions enabled
                if self.settings._typed.enable_transitions:
                    fade_transition(
                        self.screen,
                        prev_surf,
                        self.current_surf,
                        self.settings._typed.transition_duration,
                        src_pos=prev_rect.topleft,
                        dst_pos=dst_rect.topleft,
                        enable_echo=self.settings._typed.enable_echo,
                    )
            else:
                if self.settings._typed.enable_transitions:
                    fade_transition(self.screen, self.current_surf, self.current_surf, self.settings._typed.transition_duration, enable_echo=self.settings._typed.enable_echo)
        except Exception:
            pass
        try:
            from .utils import make_echo_background
            rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
            self.current_bg = make_echo_background(self.current_surf, self.screen.get_size(), rect, enable_echo=self.settings._typed.enable_echo)
        except Exception:
            self.current_bg = None

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
                if self.settings._typed.enable_transitions:
                    fade_transition(
                        self.screen,
                        prev_surf,
                        self.current_surf,
                        self.settings._typed.transition_duration,
                        src_pos=prev_rect.topleft,
                        dst_pos=dst_rect.topleft,
                        enable_echo=self.settings._typed.enable_echo,
                    )
            else:
                if self.settings._typed.enable_transitions:
                    fade_transition(self.screen, self.current_surf, self.current_surf, self.settings._typed.transition_duration, enable_echo=self.settings._typed.enable_echo)
        except Exception:
            pass
        try:
            from .utils import make_echo_background
            rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
            self.current_bg = make_echo_background(self.current_surf, self.screen.get_size(), rect, enable_echo=self.settings._typed.enable_echo)
        except Exception:
            self.current_bg = None

    def _on_settings_changed(self):
        new_mode = self.settings._typed.mode or 'photos'
        # echo setting is passed explicitly to callers when needed
        if new_mode == self.mode:
            return
        self.mode = new_mode
        if self.mode == 'videos':
            self.video_player = VideoPlayer(self.settings._typed.videos or [])
            self.video_player.load_current_clip()
            policy = str(self.settings._typed.scale_policy or 'cover')
            self.current_surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)
            self.current_bg = None
        else:
            self.load_images()
            if self.images:
                self.index = 0
                self.current_path = self.images[self.index]
                self.current_surf = self.load_surface(self.current_path)
                try:
                    from .utils import make_echo_background
                    rect = self.current_surf.get_rect(center=self.screen.get_rect().center)
                    self.current_bg = make_echo_background(self.current_surf, self.screen.get_size(), rect, enable_echo=self.settings._typed.enable_echo)
                except Exception:
                    self.current_bg = None

    def _select_video(self, index: int):
        vids = self.settings._typed.videos or []
        if not vids:
            return
        if index < 0 or index >= len(vids):
            return
        # switch to video mode and load the selected clip
        self.settings._typed.mode = 'videos'
        try:
            self.settings.save()
        except Exception:
            pass
        self.mode = 'videos'
        self.video_player = VideoPlayer(vids)
        self.video_player.index = index
        self.video_player.load_current_clip()
        policy = str(self.settings._typed.scale_policy or 'cover')
        self.current_surf = self.video_player.get_surface(self.screen.get_size(), policy=policy)
        self.current_bg = None
