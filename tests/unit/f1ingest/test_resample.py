from datetime import datetime, timedelta, timezone

from f1ingest.resample import AsOfSeries

_T0 = datetime(2025, 9, 7, 13, 0, 0, tzinfo=timezone.utc)


def _t(offset_s: float) -> datetime:
    return _T0 + timedelta(seconds=offset_s)


def test_returns_most_recent_sample_at_or_before_query() -> None:
    series = AsOfSeries([(_t(0), 1), (_t(10), 2), (_t(20), 3)])
    assert series.at(_t(0)) == 1
    assert series.at(_t(5)) == 1
    assert series.at(_t(10)) == 2
    assert series.at(_t(19.9)) == 2
    assert series.at(_t(100)) == 3


def test_returns_none_before_first_sample() -> None:
    series = AsOfSeries([(_t(10), "x")])
    assert series.at(_t(0)) is None


def test_out_of_order_input_is_sorted() -> None:
    series = AsOfSeries([(_t(20), "late"), (_t(0), "early")])
    assert series.at(_t(5)) == "early"
    assert series.at(_t(25)) == "late"
