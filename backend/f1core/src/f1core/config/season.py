"""Season config loader: teams, drivers (with mid-season entries per round
range), points table and rules. See docs/f1-strategy-foundation.md §2/§7 and
docs/plan/phase-1.md T2.

CLAUDE.md rule: "Grid size is 22, from config, never hard-coded 20." This
module never assumes a grid size; it validates whatever `grid_size` the
config declares.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, model_validator


class TeamConfig(BaseModel):
    id: str
    name: str
    colour: str
    note: str | None = None


class DriverEntry(BaseModel):
    team: str
    rounds: Annotated[tuple[int, int], Field(description="Inclusive [start, end] round range")]

    @model_validator(mode="after")
    def _rounds_ordered(self) -> DriverEntry:
        if self.rounds[0] > self.rounds[1]:
            raise ValueError(f"entry round range {self.rounds} has start > end")
        return self

    def covers(self, round_no: int) -> bool:
        return self.rounds[0] <= round_no <= self.rounds[1]


class DriverConfig(BaseModel):
    id: str
    number: int
    code: str
    name: str
    entries: list[DriverEntry]
    note: str | None = None

    def team_for_round(self, round_no: int) -> str | None:
        for entry in self.entries:
            if entry.covers(round_no):
                return entry.team
        return None


class CompoundRules(BaseModel):
    dry_compounds: list[str]
    nominated_per_event: int
    two_compound_rule: bool
    wet_compounds: list[str]
    monaco_mandatory_two_stop: bool = False


class SeasonConfig(BaseModel):
    season: int
    grid_size: int
    rounds: int
    overtake_aid: str
    points_table: list[int]
    fastest_lap_point: bool
    min_green_flag_laps_for_points: int
    compound_rules: CompoundRules
    teams: list[TeamConfig]
    drivers: list[DriverConfig]

    @model_validator(mode="after")
    def _validate_grid_every_round(self) -> SeasonConfig:
        team_ids = {t.id for t in self.teams}
        for driver in self.drivers:
            for entry in driver.entries:
                if entry.team not in team_ids:
                    raise ValueError(
                        f"driver {driver.id!r} entry references unknown team {entry.team!r}"
                    )

        for round_no in range(1, self.rounds + 1):
            active = self.drivers_for_round(round_no)
            if len(active) != self.grid_size:
                active_ids = sorted(d.id for d in active)
                raise ValueError(
                    f"round {round_no}: expected {self.grid_size} active drivers, "
                    f"got {len(active)}: {active_ids}"
                )
        return self

    def drivers_for_round(self, round_no: int) -> list[DriverConfig]:
        return [d for d in self.drivers if d.team_for_round(round_no) is not None]

    def entry_list(self, round_no: int) -> dict[str, str]:
        """driver_id -> team_id for the given round."""
        return {
            driver.id: team
            for driver in self.drivers
            if (team := driver.team_for_round(round_no)) is not None
        }

    def team_by_driver_number(self, round_no: int) -> dict[int, str]:
        """car number -> team_id for the given round. Team affiliation is
        config (prior), not something that needs to flow through the domain
        event stream — f1state's RaceStateBuilder (T6) uses this directly
        rather than needing a dedicated roster event type."""
        return {
            driver.number: team
            for driver in self.drivers
            if (team := driver.team_for_round(round_no)) is not None
        }

    def team(self, team_id: str) -> TeamConfig:
        for team in self.teams:
            if team.id == team_id:
                return team
        raise KeyError(f"unknown team id {team_id!r}")


def load_season(path: Path) -> SeasonConfig:
    raw = yaml.safe_load(path.read_text())
    return SeasonConfig.model_validate(raw)
