import pygame


DEFAULT_KEY_MAP = {
    pygame.K_RIGHT: 'next',
    pygame.K_d: 'next',
    pygame.K_LEFT: 'prev',
    pygame.K_a: 'prev',
    pygame.K_SPACE: 'pause',
    pygame.K_m: 'menu',
    pygame.K_ESCAPE: 'menu',
    pygame.K_q: 'quit',
    pygame.K_v: 'toggle_mode',
    pygame.K_UP: 'menu_up',
    pygame.K_DOWN: 'menu_down',
    pygame.K_RETURN: 'menu_select',
}


def map_event_to_action(event, settings=None):
    """Return an action string for a pygame event or None.

    `settings` may provide custom `key_bindings` but by default the app
    uses `DEFAULT_KEY_MAP` which works for keyboard-emulating remotes.
    """
    if event.type != pygame.KEYDOWN:
        return None
    # direct mapping
    action = DEFAULT_KEY_MAP.get(event.key)
    # support custom key_bindings in settings (simple names like 'next','prev')
    if not action and settings:
        kb = settings.get('key_bindings', {})
        for act, keys in kb.items():
            for k in keys:
                try:
                    if getattr(pygame, k) == event.key:
                        return act
                except Exception:
                    continue
    return action
