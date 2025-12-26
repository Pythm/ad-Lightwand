from typing import Tuple, Optional

def _parse_mode_and_room(s: str) -> Tuple[Optional[str], Optional[str]]:
    """Return the parts before and after the first underscore. """

    if '_' not in s:
        return s, None
    return s.split('_', 1)

def cancel_timer_handler(ADapi, handler) -> None:
    if handler is not None:
        if ADapi.timer_running(handler):
            try:
                ADapi.cancel_timer(handler)
            except Exception as e:
                return

def cancel_listen_handler(ADapi, handler) -> None:
    if handler is not None:
        try:
            ADapi.cancel_listen_state(handler)
        except Exception as e:
            ADapi.log(
                f"Not able to stop listen handler {handler}. Exception: {e}",
                level = 'DEBUG'
            )