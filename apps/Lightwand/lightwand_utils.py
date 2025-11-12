from typing import Tuple, Optional

def split_around_underscore(s: str) -> Tuple[Optional[str], Optional[str]]:
    """Return the parts before and after the first underscore. """

    if '_' not in s:
        return None, None
    return s.split('_', 1)