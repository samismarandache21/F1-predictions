from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from f1core.values import Kind, Value, precedence


def _val(kind: Kind, ts: str) -> Value:
    return Value(
        var_id="race.lap",
        kind=kind,
        data=1,
        source="test",
        state_version="s1",
        ts=datetime.fromisoformat(ts).replace(tzinfo=timezone.utc),
    )


def test_precedence_order() -> None:
    assert precedence(Kind.OVERRIDDEN) > precedence(Kind.OBSERVED)
    assert precedence(Kind.OBSERVED) > precedence(Kind.ESTIMATED)
    assert precedence(Kind.ESTIMATED) > precedence(Kind.PREDICTED)
    assert precedence(Kind.PREDICTED) > precedence(Kind.PRIOR)


def test_beats_by_precedence_even_if_older() -> None:
    observed = _val(Kind.OBSERVED, "2026-01-01T00:00:00")
    predicted = _val(Kind.PREDICTED, "2026-01-01T00:01:00")  # newer, but lower kind
    assert observed.beats(predicted)
    assert not predicted.beats(observed)


def test_beats_by_recency_when_precedence_equal() -> None:
    first = _val(Kind.OBSERVED, "2026-01-01T00:00:00")
    corrected = _val(Kind.OBSERVED, "2026-01-01T00:00:05")
    assert corrected.beats(first)
    assert not first.beats(corrected)


def test_reapplying_same_event_is_idempotent() -> None:
    a = _val(Kind.OBSERVED, "2026-01-01T00:00:00")
    b = _val(Kind.OBSERVED, "2026-01-01T00:00:00")
    assert a.beats(b)
    assert b.beats(a)


def test_value_is_frozen() -> None:
    val = _val(Kind.OBSERVED, "2026-01-01T00:00:00")
    with pytest.raises(ValidationError):
        val.data = 2  # type: ignore[misc]
