"""Cruise checks against asset-management cruise/CruiseInformation.csv.

Every deployment and recovery names a cruise (CUID). The cruise must already
exist in CruiseInformation.csv, and the launch or recovery time must fall
inside that cruise's start/stop window, so a typo in either the cruise ID or
the event time stops the run instead of reaching CI.
"""
from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

CRUISE_CSV = Path('cruise') / 'CruiseInformation.csv'


@dataclass(frozen=True)
class Cruise:
    cuid: str
    ship: str
    start: dt.datetime
    stop: dt.datetime


def parse_time(value: str) -> dt.datetime:
    """Parse an ISO 8601 date-time such as '2026-10-01T15:30:00'.

    Seconds may be omitted. Values are treated as UTC, the convention used
    throughout the asset-management CSVs.
    """
    try:
        return dt.datetime.fromisoformat(value.strip())
    except ValueError:
        raise ValueError(f'Not an ISO 8601 date-time (YYYY-MM-DDTHH:MM:SS): {value!r}') from None


def format_time(value: dt.datetime) -> str:
    return value.strftime('%Y-%m-%dT%H:%M:%S')


def read_cruises(asset_management: str | Path) -> dict[str, Cruise]:
    """Read CruiseInformation.csv, keyed by CUID.

    Parameters
    ----------
    asset_management : str or Path
        Root of the local asset-management clone.

    Returns
    -------
    dict[str, Cruise]
    """
    path = Path(asset_management) / CRUISE_CSV
    with open(path, newline='', encoding='utf-8') as f:
        return {
            row['CUID']: Cruise(
                cuid=row['CUID'],
                ship=row['ShipName'],
                start=parse_time(row['cruiseStartDateTime']),
                stop=parse_time(row['cruiseStopDateTime']),
            )
            for row in csv.DictReader(f)
        }


def check_cruise(asset_management: str | Path, cuid: str, when: str, event: str) -> Cruise:
    """Confirm the cruise exists and `when` falls inside its window.

    Parameters
    ----------
    asset_management : str or Path
        Root of the local asset-management clone.
    cuid : str
        Cruise ID; a leading '#' (not-deployed marker) is ignored.
    when : str
        ISO 8601 event time.
    event : str
        Label for error messages, e.g. 'Launch' or 'Recovery'.

    Returns
    -------
    Cruise

    Raises
    ------
    ValueError
        If the cruise is unknown or `when` is outside its window.
    """
    cuid = cuid.lstrip('#')
    cruise = read_cruises(asset_management).get(cuid)
    if cruise is None:
        raise ValueError(f'Cruise {cuid!r} is not in {CRUISE_CSV.as_posix()}; add it, then re-run.')
    t = parse_time(when)
    if not cruise.start <= t <= cruise.stop:
        raise ValueError(
            f'{event} time {format_time(t)} is outside cruise {cuid} '
            f'({format_time(cruise.start)} to {format_time(cruise.stop)}).')
    return cruise
