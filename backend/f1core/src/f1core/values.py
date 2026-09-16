"""Value kinds and precedence. See docs/f1-strategy-foundation.md §4.2.

Precedence: overridden > observed > estimated > predicted > prior.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Kind(str, Enum):
    OVERRIDDEN = "overridden"
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    PREDICTED = "predicted"
    PRIOR = "prior"


_PRECEDENCE: dict[Kind, int] = {
    Kind.OVERRIDDEN: 4,
    Kind.OBSERVED: 3,
    Kind.ESTIMATED: 2,
    Kind.PREDICTED: 1,
    Kind.PRIOR: 0,
}


def precedence(kind: Kind) -> int:
    return _PRECEDENCE[kind]


class Value(BaseModel):
    """A single, immutable stored value for one variable at one scope key.

    `scope_id` disambiguates the variable's scope target: empty string for
    race/season/circuit-scoped variables, a driver number (as a string) for
    car/car_lap/car_stint-scoped variables.
    """

    model_config = ConfigDict(frozen=True)

    var_id: str
    scope_id: str = ""
    kind: Kind
    data: Any
    source: str
    model_version: str = "n/a"
    state_version: str
    ts: datetime
    uncertainty: float | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.var_id, self.scope_id)

    def beats(self, other: Value) -> bool:
        """True if this value should replace `other` as the resolved value.

        Higher precedence always wins. Equal precedence resolves by recency
        (newer-or-equal timestamp wins), which makes re-applying the same
        event idempotent per CLAUDE.md rule 8.
        """
        self_p, other_p = precedence(self.kind), precedence(other.kind)
        if self_p != other_p:
            return self_p > other_p
        return self.ts >= other.ts
