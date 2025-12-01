from typing import Tuple, Optional

def _parse_mode_and_room(s: str) -> Tuple[Optional[str], Optional[str]]:
    """Return the parts before and after the first underscore. """

    if '_' not in s:
        return s, None
    return s.split('_', 1)

