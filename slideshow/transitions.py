import time
import pygame
from .utils import blit_scaled_with_echo


def fade_transition(screen, src_surf, dst_surf, duration, src_pos=None, dst_pos=None, enable_echo: bool = True):
    """Fade from src_surf to dst_surf over `duration` seconds.

    Render both source and destination into full-screen frames using
    `blit_scaled_with_echo()` so any pillar/letterbox echoes are included,
    then alpha-blend the destination frame over the source frame.
    Positions may be provided as topleft coordinates or left as None to
    center both surfaces on screen.
    """
    clock = pygame.time.Clock()
    start = time.time()
    sw, sh = screen.get_size()

    # compute rects for source and destination (relative to full screen)
    if src_pos is None:
        src_rect = src_surf.get_rect(center=(sw // 2, sh // 2))
    else:
        src_rect = src_surf.get_rect(topleft=src_pos)
    if dst_pos is None:
        dst_rect = dst_surf.get_rect(center=(sw // 2, sh // 2))
    else:
        dst_rect = dst_surf.get_rect(topleft=dst_pos)

    # preallocate full-frame surfaces (alpha-capable)
    frame_src = pygame.Surface((sw, sh), flags=pygame.SRCALPHA)
    frame_dst = pygame.Surface((sw, sh), flags=pygame.SRCALPHA)

    # Pre-render the echoed full frames once and reuse while changing alpha.
    frame_src.fill((0, 0, 0, 0))
    frame_dst.fill((0, 0, 0, 0))
    blit_scaled_with_echo(frame_src, src_surf, src_rect, enable_echo=enable_echo)
    blit_scaled_with_echo(frame_dst, dst_surf, dst_rect, enable_echo=enable_echo)

    while True:
        t = (time.time() - start) / duration
        if t >= 1.0:
            # final: blit destination fully
            screen.blit(frame_dst, (0, 0))
            pygame.display.flip()
            break

        alpha = int(255 * t)

        # blend destination on top with alpha
        tmp = frame_dst.copy()
        tmp.set_alpha(alpha)

        screen.blit(frame_src, (0, 0))
        screen.blit(tmp, (0, 0))
        pygame.display.flip()
        clock.tick(60)
