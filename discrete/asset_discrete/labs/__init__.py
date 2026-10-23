"""Lab result readers.

Each reader turns one lab file into a list of LabResult records, one per
sample. The build joins them to the workbook's drawn samples; readers do no
joining and set no flags.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


class LabError(ValueError):
    """The lab file cannot be used as it is."""


@dataclass
class LabResult:
    """One analysed sample from a lab file."""
    sample_id: str                      # sample number as written on the log, without leading zeros
    values: dict[str, str]              # summary value column -> text as reported by the lab
    cast: int | None = None             # when the lab file names the cast
    niskin: int | None = None           # when the lab file names the Niskin
    station: str | None = None          # lab's station code, checked only
    draw_temp: float | None = None      # oxygen draw temperature [deg C], checked only
    comment: str = ''                   # lab comment, written to the build log
    line: int = 0                       # line number in the lab file


@dataclass
class LabFile:
    """Parsed lab file plus the header facts worth logging."""
    path: Path
    results: list[LabResult]
    header: dict[str, str] = field(default_factory=dict)


def _readers() -> dict[str, Callable[[str | Path], LabFile]]:
    from asset_discrete.labs.oxygen import read_oxygen
    return {'oxygen': read_oxygen}


def read_lab(analysis: str, path: str | Path) -> LabFile:
    """Read a lab file with the reader for `analysis`.

    Raises
    ------
    LabError
        If there is no reader for `analysis` or the file cannot be parsed.
    """
    readers = _readers()
    if analysis not in readers:
        raise LabError(f'no lab reader for {analysis!r}; available: {", ".join(readers)}')
    return readers[analysis](path)
