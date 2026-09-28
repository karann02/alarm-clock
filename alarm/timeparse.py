"""Pure time parsing and scheduling helpers.

Nothing in this module reads the real clock or touches the terminal: every
function takes its inputs explicitly, so it can be tested exhaustively.
"""

import math
import re
from datetime import datetime, time, timedelta

_CLOCK_RE = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?$|^(\d{1,2}):(\d{2})$")
_DURATION_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
MAX_DURATION = timedelta(days=7)


def parse_clock_time(text):
    """Parse '07:30', '19:05', '7:30pm', '7pm', '12am' into a datetime.time.

    A bare hour such as '7' is rejected: it could mean 7am or 7pm, and for an
    alarm, failing loudly beats guessing wrong.
    """
    raw = text.strip().lower()
    if re.fullmatch(r"\d{1,2}", raw):
        raise ValueError(
            f"'{text}' is ambiguous - use '{raw}:00' (24-hour) or '{raw}am'/'{raw}pm'"
        )
    match = _CLOCK_RE.match(raw)
    if not match:
        raise ValueError(
            f"invalid time '{text}' - use HH:MM (e.g. 07:30, 19:05) or 7:30pm / 7am"
        )

    if match.group(3):  # 12-hour clock with am/pm
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if not 1 <= hour <= 12:
            raise ValueError(f"invalid hour in '{text}' - with am/pm the hour must be 1-12")
        hour = hour % 12 + (12 if match.group(3) == "p" else 0)
    else:  # 24-hour clock
        hour = int(match.group(4))
        minute = int(match.group(5))
        if not 0 <= hour <= 23:
            raise ValueError(f"invalid hour in '{text}' - hour must be 0-23")

    if not 0 <= minute <= 59:
        raise ValueError(f"invalid minutes in '{text}' - minutes must be 0-59")
    return time(hour, minute)


def parse_duration(text):
    """Parse '25m', '1h30m', '90s', '1h' into a positive timedelta."""
    raw = text.strip().lower().replace(" ", "")
    match = _DURATION_RE.match(raw)
    if not raw or not match:
        raise ValueError(
            f"invalid duration '{text}' - use a number with h/m/s, e.g. 25m, 1h30m, 90s"
        )
    hours, minutes, seconds = (int(g or 0) for g in match.groups())
    # Check the plain integer total first: building a timedelta (or adding it to
    # now) from a huge value raises OverflowError, not ValueError.
    total = hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        raise ValueError(f"duration '{text}' must be greater than zero")
    if total > MAX_DURATION.total_seconds():
        raise ValueError(f"duration '{text}' is too long - the maximum is 7 days")
    return timedelta(seconds=total)


def next_occurrence(target, now):
    """Return the next datetime at clock time `target`, strictly after `now`.

    A time equal to or earlier than now today means tomorrow.
    """
    candidate = datetime.combine(now.date(), target)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def format_remaining(delta):
    """Format a timedelta as HH:MM:SS, rounding partial seconds up, never negative."""
    total = max(0, math.ceil(delta.total_seconds()))
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
