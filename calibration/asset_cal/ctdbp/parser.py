"""Calibration parser for the CTDBP instrument class (Sea-Bird SBE16+).

Ported from tools/matlab/Endurance_cal_scripts/ctdbp/write_ctdbp_qct_to_csv.m
and .../ctdbp/rad_read_ctdbp_cap.m.

C and E share identical source format (QCT "cap" text file) and
coefficient set -- they only differ in which series letter lands in
the output filename -- so this is one CtdbpParser class, registered
under both "CTDBP-C" and "CTDBP-E" with the series fixed at
construction time, same pattern as DostaParser. There is no
serial-number-to-series lookup: the Matlab script's hardcoded
seriesC/seriesE lists were checked against the real
calibration/CTDBPC archive and, like DOSTAD before it, found to be
missing a large fraction of real production serials -- confirming
the explicit CLASS-SERIES design decision was the right call, not
just for DOSTA.

parse() is a direct, fairly precisely-specified port of
rad_read_ctdbp_cap.m (each coefficient line has an unambiguous
"NAME = value" format, unlike DOSTA's QCT, which is more
tab-position-dependent). Still UNVERIFIED against a real cap file --
none was available -- but the format itself is less ambiguous to
port than DOSTA's.

write_csv() is not subject to that caveat -- confirmed directly
against the real calibration/CTDBPC archive. Two things worth
knowing:

- Every row's first (serial) column is "16-<sernum>", not the bare
  serial number -- an SBE16+ model-prefix convention specific to
  this instrument class.
- Coefficients are written in alphabetical order by their CC_ name
  (the Matlab source does this explicitly "to match what is already
  on github"), not in cap-file read order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_CALDATE_PROVENANCE = "date in filename comes from latest sensor caldate within QCT cap file"

# Cap-file label -> output coefficient name. The cap file's first 4
# temperature coefficients are labeled TA0..TA3; every other label
# is identical on both sides.
_CAP_TO_OUTPUT_NAME = {
    "TA0": "A0", "TA1": "A1", "TA2": "A2", "TA3": "A3",
    "PTEMPA0": "PTEMPA0", "PTEMPA1": "PTEMPA1", "PTEMPA2": "PTEMPA2",
    "PTCA0": "PTCA0", "PTCA1": "PTCA1", "PTCA2": "PTCA2",
    "PTCB0": "PTCB0", "PTCB1": "PTCB1", "PTCB2": "PTCB2",
    "PA0": "PA0", "PA1": "PA1", "PA2": "PA2",
    "G": "G", "H": "H", "I": "I", "J": "J", "CPCOR": "CPCOR", "CTCOR": "CTCOR",
}
_OUTPUT_ORDER = sorted(_CAP_TO_OUTPUT_NAME.values())

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


@dataclass(frozen=True)
class CtdbpCal:
    """Calibration coefficients parsed from a CTDBP QCT cap file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, parsed from the "SERIAL NO."
        line.
    series : str
        "C" or "E", as supplied by the caller -- not derived from
        the serial number.
    caldate : str
        Calibration date as YYYYMMDD -- the latest of the
        temperature, conductivity, and pressure sensor caldates
        found in the cap file.
    coefficients : dict[str, str]
        The 22 calibration coefficients, keyed by their output name
        (A0..A3, PTEMPA0..2, PTCA0..2, PTCB0..2, PA0..2, G, H, I, J,
        CPCOR, CTCOR), exact strings as read from the file.
    """

    serial_number: int
    series: str
    caldate: str
    coefficients: dict[str, str] = field(default_factory=dict)


class CtdbpParser(SeriesParser[CtdbpCal]):
    """Parses CTDBP QCT cap files for a fixed series (C or E)."""

    class_code: ClassVar[str] = "CTDBP"

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path) -> CtdbpCal:
        """Parse a CTDBP QCT cap file into a CtdbpCal.

        UNVERIFIED -- see module docstring.

        Raises
        ------
        ValueError
            If the serial number, any sensor caldate, or any
            coefficient cannot be found.
        """
        lines = source_path.read_text(encoding="ascii").splitlines()

        serial_number = _find_serial_number(lines)
        caldate = _find_latest_caldate(lines)
        coefficients = {
            output_name: _find_coefficient(lines, cap_label)
            for cap_label, output_name in _CAP_TO_OUTPUT_NAME.items()
        }

        return CtdbpCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            coefficients=coefficients,
        )

    def write_csv(
        self, cal: CtdbpCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a CTDBP calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/CTDBP<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; CTDBP calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_str = f"{cal.serial_number:05d}"
        filename = f"CGINS-{self.class_code}{self.series}-{sn_str}__{cal.caldate}.csv"
        output_path = output_dir / filename

        serial_column = f"16-{cal.serial_number}"
        coefficients = [CalCoefficient(f"CC_{name.lower()}", cal.coefficients[name]) for name in _OUTPUT_ORDER]
        first = coefficients[0]
        coefficients[0] = CalCoefficient(first.name, first.value, _CALDATE_PROVENANCE)

        return write_cal_csv(output_path, serial_column, coefficients)


def _find_serial_number(lines: list[str]) -> int:
    """UNVERIFIED -- see module docstring."""
    for line in lines:
        if "SERIAL NO." in line:
            after = line.split("SERIAL NO.", 1)[1]
            match = re.match(r"\s*(\d+)", after)
            if match:
                return int(match.group(1))
            raise ValueError(f"Could not parse serial number from line: {line!r}")
    raise ValueError("Could not find 'SERIAL NO.' line in cap file.")


def _find_latest_caldate(lines: list[str]) -> str:
    """UNVERIFIED -- see module docstring."""
    caldates = [
        _find_sensor_caldate(lines, "temperature:"),
        _find_sensor_caldate(lines, "conductivity:"),
        _find_sensor_caldate(lines, "pressure S/N ="),
    ]
    return max(_normalize_caldate(d) for d in caldates)


def _find_sensor_caldate(lines: list[str], match: str) -> str:
    for line in lines:
        if match in line:
            return line.split(":", 1)[1].strip()
    raise ValueError(f"Could not find sensor caldate line matching {match!r}.")


def _normalize_caldate(date_str: str) -> str:
    """Convert a "dd-mmm-yy" caldate (e.g. "13-dec-12") to YYYYMMDD."""
    if len(date_str) < 9:
        raise ValueError(f"Unexpected caldate format: {date_str!r}")
    day = date_str[0:2]
    month_abbr = date_str[3:6].lower()
    year_suffix = date_str[7:9]
    if month_abbr not in _MONTHS:
        raise ValueError(f"Unrecognized month abbreviation in caldate: {date_str!r}")
    month_num = _MONTHS.index(month_abbr) + 1
    return f"20{year_suffix}{month_num:02d}{day}"


def _find_coefficient(lines: list[str], cap_label: str) -> str:
    """UNVERIFIED -- see module docstring. Uses the LAST matching
    line if a coefficient is listed twice, matching the Matlab
    source's own handling of cap files with duplicate entries."""
    label_pattern = f"{cap_label} = "
    matches = [line.strip() for line in lines if line.strip().startswith(label_pattern)]
    if not matches:
        raise ValueError(f"Could not find coefficient labeled {cap_label!r} in cap file.")
    return matches[-1][len(label_pattern):].strip()
