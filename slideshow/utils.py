import pygame
from typing import Tuple, Optional, Any
try:
    from PIL import Image, ImageFilter
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False
if not _PIL_AVAILABLE:
    Image: Any = None
    ImageFilter: Any = None


def scale_image(surf: pygame.Surface, target_size: Tuple[int, int], policy: str = 'cover') -> pygame.Surface:
    """Scale `surf` to target_size. policy: 'cover' (crop) or 'fit' (contain).

    - 'cover': scale so the surface fills target (may crop edges)
    - 'fit': scale so the whole surface is visible (may letterbox)
    """
    sw, sh = surf.get_size()
    tw, th = target_size
    if sw == 0 or sh == 0:
        return surf
    if policy == 'fit':
        scale = min(tw / sw, th / sh)
    else:
        scale = max(tw / sw, th / sh)
    new_size = (max(1, int(sw * scale)), max(1, int(sh * scale)))
    scaled = pygame.transform.smoothscale(surf, new_size)
    return scaled


def scale_to_cover(surf: pygame.Surface, target_size: Tuple[int, int]) -> pygame.Surface:
    """Backward-compatible wrapper for cover behavior."""
    return scale_image(surf, target_size, policy='cover')


def blit_scaled_with_echo(screen: pygame.Surface, scaled_surf: pygame.Surface, dst_rect: Optional[pygame.Rect] = None):
    """Blit an already-scaled surface centered at dst_rect (or center of screen).

    If there are pillar/letterbox bars, render a mirrored "echo" of the image
    into those bars to avoid plain black borders.
    """
    sw, sh = screen.get_size()
    if dst_rect is None:
        dst_rect = scaled_surf.get_rect(center=(sw // 2, sh // 2))

    # compute bars
    left = dst_rect.left
    right = sw - dst_rect.right
    top = dst_rect.top
    bottom = sh - dst_rect.bottom

    # helper to create mirrored strip
    def make_echo_strip(src_rect, out_size, flip_x=False, flip_y=False):
        try:
            strip = scaled_surf.subsurface(src_rect).copy()
            echo = pygame.transform.smoothscale(strip, out_size)
            if flip_x or flip_y:
                echo = pygame.transform.flip(echo, flip_x, flip_y)

            # Apply a strong blur to the echo area. Prefer Pillow GaussianBlur;
            # fallback to a repeated downscale/upscale box-blur when Pillow
            # isn't available.
            def _apply_blur(surface: pygame.Surface, radius: int = 24) -> pygame.Surface:
                if _PIL_AVAILABLE:
                    try:
                        data = pygame.image.tostring(surface, 'RGBA')
                        img = Image.frombytes('RGBA', surface.get_size(), data)
                        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
                        out_data = img.tobytes()
                        return pygame.image.fromstring(out_data, img.size, 'RGBA')
                    except Exception:
                        pass
                # Pillow not available or failed: cheap box-blur via downscale/upscale
                w, h = surface.get_size()
                # strong blur -> scale down aggressively then back up
                down_w = max(1, w // 12)
                down_h = max(1, h // 12)
                try:
                    small = pygame.transform.smoothscale(surface, (down_w, down_h))
                    blurred = pygame.transform.smoothscale(small, (w, h))
                    # repeat once for stronger effect
                    small = pygame.transform.smoothscale(blurred, (max(1, down_w // 2), max(1, down_h // 2)))
                    blurred = pygame.transform.smoothscale(small, (w, h))
                    return blurred
                except Exception:
                    return surface

            echo = _apply_blur(echo, radius=28)
            return echo
        except Exception:
            return None

    # vertical bars (left/right)
    if left > 0:
        src_w = max(1, min(8, scaled_surf.get_width()))
        src_rect = pygame.Rect(0, 0, src_w, scaled_surf.get_height())
        echo = make_echo_strip(src_rect, (left, dst_rect.height), flip_x=True)
        if echo:
            screen.blit(echo, (0, dst_rect.top))
    if right > 0:
        src_w = max(1, min(8, scaled_surf.get_width()))
        src_rect = pygame.Rect(scaled_surf.get_width() - src_w, 0, src_w, scaled_surf.get_height())
        echo = make_echo_strip(src_rect, (right, dst_rect.height), flip_x=True)
        if echo:
            screen.blit(echo, (dst_rect.right, dst_rect.top))

    # horizontal bars (top/bottom)
    if top > 0:
        src_h = max(1, min(8, scaled_surf.get_height()))
        src_rect = pygame.Rect(0, 0, scaled_surf.get_width(), src_h)
        echo = make_echo_strip(src_rect, (dst_rect.width, top), flip_y=True)
        if echo:
            screen.blit(echo, (dst_rect.left, 0))
    if bottom > 0:
        src_h = max(1, min(8, scaled_surf.get_height()))
        src_rect = pygame.Rect(0, scaled_surf.get_height() - src_h, scaled_surf.get_width(), src_h)
        echo = make_echo_strip(src_rect, (dst_rect.width, bottom), flip_y=True)
        if echo:
            screen.blit(echo, (dst_rect.left, dst_rect.bottom))

    # finally blit the scaled image
    screen.blit(scaled_surf, dst_rect.topleft)
