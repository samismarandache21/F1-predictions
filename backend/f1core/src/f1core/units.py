"""Unit tags used in variable definitions and, per CLAUDE.md rule 5, in variable
and field names (`_s`, `_m`, `_laps`, `_c`). This module is intentionally small:
it exists so a unit string in a `config/variables/*.yaml` file can be validated
against a known set rather than being a free-form typo-prone string.
"""

from __future__ import annotations

from enum import StrEnum


class Unit(StrEnum):
    SECONDS = "_s"
    METRES = "_m"
    CELSIUS = "_c"
    LAPS = "laps"
    PERCENT = "pct"
    NONE = "none"
