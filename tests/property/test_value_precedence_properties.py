from datetime import datetime, timezone

from hypothesis import given
from hypothesis import strategies as st

from f1core.values import Kind, Value, precedence

_kinds = st.sampled_from(list(Kind))
_ts = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _val(kind: Kind) -> Value:
    return Value(var_id="x", kind=kind, data=1, source="t", state_version="s", ts=_ts)


@given(_kinds, _kinds)
def test_beats_agrees_with_precedence_when_kinds_differ(k1: Kind, k2: Kind) -> None:
    if precedence(k1) == precedence(k2):
        return
    v1, v2 = _val(k1), _val(k2)
    assert v1.beats(v2) == (precedence(k1) > precedence(k2))
    assert v2.beats(v1) == (precedence(k2) > precedence(k1))


@given(_kinds)
def test_beats_is_reflexive_at_equal_timestamp(kind: Kind) -> None:
    v1, v2 = _val(kind), _val(kind)
    assert v1.beats(v2)
    assert v2.beats(v1)
