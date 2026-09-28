"""Calibration parsers for the PARAD instrument class.

PARAD's series don't share a source format or coefficient set, so
each series gets its own SeriesParser subclass and its own
calibration-record dataclass, all living in this one module:

- ParadJParser / ParadJCal: factory dev file, CC_Im/CC_a0/CC_a1.
  Ported from
  tools/matlab/Endurance_cal_scripts/parad/write_parad_dev_to_csv.m.
- ParadKParser / ParadKCal (not yet built): PDF calibration
  certificate, CC_dark_offset/CC_scale_wet. No Matlab source exists
  for this series -- needs a sample cert before it can be written.

Other instrument classes may not need this split at all: where a
class's series is purely a serial-number lookup against an
otherwise identical source format and coefficient set (the
CTDBP/DOSTA/FLORT/PRESF/OPTAA pattern), one class in that module's
parser.py can serve every series -- see common/series_parser.py.

Coefficient values in ParadJCal are carried through as the exact
strings found in the dev file, not round-tripped through float, so
that formatting (trailing zeros, significant figures) matches the
source document exactly -- the Matlab source does the same; it
never converts these fields to numeric type before writing them
back out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_CALDATE_PROVENANCE = "date in filename comes from factory devfile"

_SERIAL_PATTERN = re.compile(r"PARS-(\d+)")
_CALDATE_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2})")


@dataclass(frozen=True)
class ParadJCal:
    """Calibration coefficients parsed from a PARAD-J dev file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, parsed from the "PARS-nnn" token.
    series : str
        Always "J" for this parser.
    caldate : str
        Calibration date as YYYYMMDD, parsed from the "Created on:"
        line. Two-digit years are assumed to be 20xx.
    im : str
        Immersion coefficient, exact string as read from the file.
    a0 : str
        Dark offset coefficient, exact string as read from the file.
    a1 : str
        Scaling coefficient, exact string as read from the file.
    """

    serial_number: int
    series: str
    caldate: str
    im: str
    a0: str
    a1: str


class ParadJParser(SeriesParser[ParadJCal]):
    """Parses PARAD-J factory dev files."""

    class_code: ClassVar[str] = "PARAD"
    series: ClassVar[str] = "J"

    def parse(self, source_path: Path) -> ParadJCal:
        """Parse a PARAD-J factory dev file into a ParadJCal.

        Raises
        ------
        ValueError
            If the serial number, cal date, or any coefficient
            cannot be found in the file.
        """
        lines = source_path.read_text(encoding="ascii").splitlines()

        serial_number = _find_serial_number(lines)
        caldate = _find_caldate(lines)
        im = _find_coefficient(lines, "im=")
        a1 = _find_coefficient(lines, "a1=")
        a0 = _find_coefficient(lines, "a0=")

        return ParadJCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            im=im,
            a0=a0,
            a1=a1,
        )

    def write_csv(
        self, cal: ParadJCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a PARAD-J calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/PARADJ does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; PARAD-J calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_str = f"{cal.serial_number:05d}"
        filename = f"CGINS-{self.class_code}{self.series}-{sn_str}__{cal.caldate}.csv"
        output_path = output_dir / filename

        coefficients = [
            CalCoefficient("CC_Im", cal.im, _CALDATE_PROVENANCE),
            CalCoefficient("CC_a0", cal.a0, "digital"),
            CalCoefficient("CC_a1", cal.a1, "digital"),
        ]
        return write_cal_csv(output_path, str(cal.serial_number), coefficients)


def _find_serial_number(lines: list[str]) -> int:
    for line in lines:
        match = _SERIAL_PATTERN.search(line)
        if match:
            return int(match.group(1))
    raise ValueError("Could not find 'PARS-<serial>' token in dev file.")


def _find_caldate(lines: list[str]) -> str:
    for line in lines:
        if "created" in line.lower():
            match = _CALDATE_PATTERN.search(line)
            if match:
                mm, dd, yy = match.groups()
                return f"20{yy}{int(mm):02d}{int(dd):02d}"
    raise ValueError("Could not find 'Created on:' date in dev file.")


def _find_coefficient(lines: list[str], label: str) -> str:
    for line in lines:
        fields = line.split("\t")
        if fields and fields[0].strip() == label:
            for field in fields[1:]:
                field = field.strip()
                if field:
                    float(field)  # validate it is actually numeric
                    return field
    raise ValueError(f"Could not find coefficient labeled '{label}' in dev file.")
