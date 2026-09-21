"""Found on the first live Monza ingest: OpenF1's /intervals returns strings
like "+1 LAP" for lapped cars, which crashed the laps insert (numeric column).
The recorded fixtures only ever had numeric gaps, so nothing caught it."""

from __future__ import annotations

import pytest

from f1ingest.adapters.openf1_hist import _parse_gap_s


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0.543, 0.543),
        (2, 2.0),
        ("1.25", 1.25),
        (" 3.5 ", 3.5),
        ("+1 LAP", None),
        ("+2 LAPS", None),
        ("", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_gap_s(raw: object, expected: float | None) -> None:
    assert _parse_gap_s(raw) == expected
