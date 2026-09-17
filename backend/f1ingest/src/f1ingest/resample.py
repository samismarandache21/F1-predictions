"""As-of resampling: OpenF1's `position` and `intervals` endpoints are event
streams (a new row only when the value changes), not one row per lap. Getting
the value "as of" a lap boundary needs last-observation-carried-forward, not
an exact-timestamp join. Verified live against api.openf1.org during T4:
a driver's `/position` rows are sparse and irregular, so this is not optional.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import datetime
from typing import Generic, TypeVar

# Kept as Generic[T]/TypeVar rather than PEP 695 `class AsOfSeries[T]` syntax:
# the latter is real grammar (not deferred by `from __future__ import
# annotations`), so it would stop this module from even being importable on
# anything older than 3.12. This project targets 3.12 everywhere, but keeping
# this one pure-stdlib module parseable on older interpreters costs nothing
# and made local verification possible before the real 3.12 toolchain was
# installed (see the T4 summary).
T = TypeVar("T")


class AsOfSeries(Generic[T]):  # noqa: UP046 (see comment above)
    """A time-sorted series of (timestamp, value) samples supporting
    last-observation-carried-forward lookups."""

    def __init__(self, samples: Sequence[tuple[datetime, T]]) -> None:
        ordered = sorted(samples, key=lambda pair: pair[0])
        self._timestamps = [ts for ts, _ in ordered]
        self._values = [value for _, value in ordered]

    def at(self, ts: datetime) -> T | None:
        """The most recent sample at or before `ts`, or None if `ts` is
        before every sample."""
        index = bisect_right(self._timestamps, ts) - 1
        if index < 0:
            return None
        return self._values[index]
