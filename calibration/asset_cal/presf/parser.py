"""Calibration parser for the PRESF instrument class (Sea-Bird SBE26+).

Ported from tools/matlab/Endurance_cal_scripts/presf/write_presf_qct_to_csv.m
and .../presf/rad_read_presf_cap.m.

A, B, and C share identical source format (QCT "cap" text file) and
coefficient set -- they only differ in which series letter lands in
the output filename -- so this is one PresfParser class, registered
under "PRESF-A", "PRESF-B", and "PRESF-C" with the series fixed at
construction time, same pattern as CTDBP/FLORT. No serial-number
lookup: PRESFA's real archive happens to match the Matlab seriesA
list exactly (the first class where that's been true), but PRESFB
does not (more real serials than the hardcoded list, same pattern
as every other class), so the explicit CLASS-SERIES design still
applies uniformly.

parse() is a direct port of rad_read_presf_cap.m's "NAME = value"
line matching (using Matlab's `contains`, not an exact-prefix match
-- unlike CTDBP's `strncmp`, so ported that way here too) plus
write_presf_qct_to_csv.m's parse_date() subroutine, which handles
three different observed date formats ("9-nov-16", "09-nov-2016",
"11-09-2016"). UNVERIFIED against a real cap file -- none was
available, and unlike FLORT/PARAD-J/PHSEN-D, no sample is embedded
in the Matlab source's comments either. _parse_presf_date is tested
against the three formats the Matlab comment documents as a
self-consistency check, not against a real file.

write_csv() is not subject to that caveat -- confirmed directly
against calibration/PRESFA/CGINS-PRESFA-01328__20120330.csv and a
2025 refresh of the same instrument. Notable:

- The serial column is "26P-<sernum>", an SBE26+ model-prefix
  convention (parallel to CTDBP's "16-<sernum>").
- Two coefficients are NOT read from the file at all:
  offset_correction_factor and slope_correction_factor are always
  written as the literal constants "0" and "1". The cap file's
  actual OFFSET reading becomes a differently-named coefficient,
  pressure_offset_calibration_coefficient.
- The cap file's four temperature coefficients (TA0-3) are read by
  rad_read_presf_cap but never used in the csv output -- the Matlab
  source's own comment says so ("the temperature coefficients are
  not used"), so this port never even reads them.
- Output is alphabetical by CC_ name (same convention confirmed for
  CTDBP and FLORT). The provenance note lands on whichever
  coefficient sorts first -- CC_b, given this class's fixed set of
  names -- which is itself a quirk of the Matlab source attaching
  the note post-reorder rather than to a specific semantic field.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_CALDATE_PROVENANCE = "date in filename comes from latest sensor caldate read from file captured from relevant QCT"

# Cap-file label -> output coefficient name. TA0-3 (temperature
# coefficients) are deliberately excluded -- read by the cap file
# but never used in csv output, per the Matlab source.
_CAP_TO_OUTPUT_NAME = {
    "C1": "c1", "C2": "c2", "C3": "c3",
    "D1": "d1", "D2": "d2",
    "OFFSET": "pressure_offset_calibration_coefficient",
    "T1": "t1", "T2": "t2", "T3": "t3", "T4": "t4",
    "U0": "u0",
    "Y1": "y1", "Y2": "y2", "Y3": "y3",
    "B": "b", "M": "m",
}

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")


@dataclass(frozen=True)
class PresfCal:
    """Calibration coefficients parsed from a PRESF QCT cap file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, parsed from the "SN" line.
    series : str
        "A", "B", or "C", as supplied by the caller -- not derived
        from the serial number.
    caldate : str
        Calibration date as YYYYMMDD -- the latest of the pressure
        and temperature sensor caldates found in the cap file.
    coefficients : dict[str, str]
        The 16 calibration coefficients actually used in output
        (c1, c2, c3, d1, d2, pressure_offset_calibration_coefficient,
        t1..t4, u0, y1..y3, b, m), exact strings as read from the
        file.
    """

    serial_number: int
    series: str
    caldate: str
    coefficients: dict[str, str] = field(default_factory=dict)


class PresfParser(SeriesParser[PresfCal]):
    """Parses PRESF QCT cap files for a fixed series (A, B, or C)."""

    class_code: ClassVar[str] = "PRESF"

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path) -> PresfCal:
        """Parse a PRESF QCT cap file into a PresfCal.

        UNVERIFIED -- see module docstring.

        Raises
        ------
        ValueError
            If the serial number, either sensor caldate, or any
            coefficient cannot be found or parsed.
        """
        lines = [line.strip() for line in source_path.read_text(encoding="ascii").splitlines()]

        serial_number = _find_serial_number(lines)
        pressure_caldate = _find_sensor_caldate(lines, "Pressure coefficients:")
        temperature_caldate = _find_sensor_caldate(lines, "Temperature coefficients:")
        caldate = max(_parse_presf_date(pressure_caldate), _parse_presf_date(temperature_caldate))

        coefficients = {
            output_name: _find_coefficient(lines, cap_label)
            for cap_label, output_name in _CAP_TO_OUTPUT_NAME.items()
        }

        return PresfCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            coefficients=coefficients,
        )

    def write_csv(
        self, cal: PresfCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a PRESF calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/PRESF<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; PRESF calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_str = f"{cal.serial_number:05d}"
        filename = f"CGINS-{self.class_code}{self.series}-{sn_str}__{cal.caldate}.csv"
        output_path = output_dir / filename

        serial_column = f"26P-{cal.serial_number}"

        values = dict(cal.coefficients)
        values["offset_correction_factor"] = "0"
        values["slope_correction_factor"] = "1"

        coefficients = [CalCoefficient(f"CC_{name}", values[name]) for name in sorted(values)]
        # Matlab attaches the provenance note post-reorder to whatever
        # sorts first, which is always CC_b given this class's fixed
        # set of coefficient names -- not because b is semantically
        # special.
        first = coefficients[0]
        coefficients[0] = CalCoefficient(first.name, first.value, _CALDATE_PROVENANCE)

        return write_cal_csv(output_path, serial_column, coefficients)


def _find_serial_number(lines: list[str]) -> int:
    """UNVERIFIED -- see module docstring."""
    for line in lines:
        if "SN" in line:
            after = line.split("SN", 1)[1]
            match = re.match(r"\s*[:=]?\s*(\d+)", after)
            if match:
                return int(match.group(1))
            raise ValueError(f"Could not parse serial number from line: {line!r}")
    raise ValueError("Could not find 'SN' line in cap file.")


def _find_sensor_caldate(lines: list[str], match: str) -> str:
    """UNVERIFIED -- see module docstring."""
    for line in lines:
        if match in line:
            return line.split(":", 1)[1].strip()
    raise ValueError(f"Could not find sensor caldate line matching {match!r}.")


def _find_coefficient(lines: list[str], cap_label: str) -> str:
    """UNVERIFIED -- see module docstring. Uses `in` (Matlab's
    `contains`), not an exact-prefix match, and the LAST matching
    line if a coefficient is listed twice."""
    label_pattern = f"{cap_label} = "
    matches = [line for line in lines if label_pattern in line]
    if not matches:
        raise ValueError(f"Could not find coefficient labeled {cap_label!r} in cap file.")
    line = matches[-1]
    idx = line.find("=")
    return line[idx + 2:].strip()


def _parse_presf_date(date_str: str) -> str:
    """Convert a PRESF sensor caldate to YYYYMMDD.

    Handles three formats confirmed by the Matlab source's own
    comment: "9-nov-16", "09-nov-2016", "11-09-2016" (all of which
    are documented there as converting to "20161109").
    """
    if "-" not in date_str:
        raise ValueError(f"PRESF sensor date does not contain a hyphen: {date_str!r}")

    parts = [p.strip() for p in date_str.split("-")]
    if len(parts) != 3:
        raise ValueError(f"Unparseable PRESF sensor caldate: {date_str!r}")
    part1, mid, part3 = parts

    if mid.isalpha():
        month_abbr = mid.lower()
        if month_abbr not in _MONTHS:
            raise ValueError(f"Unrecognized month abbreviation in caldate: {date_str!r}")
        mm = f"{_MONTHS.index(month_abbr) + 1:02d}"
        day = part1
        if len(day) == 1:
            day = "0" + day
        elif len(day) != 2:
            raise ValueError(f"Unparseable PRESF sensor caldate: {date_str!r}")
        dd = day
    elif mid.isdigit() and part1.isdigit():
        mm = f"{int(part1):02d}"
        dd = f"{int(mid):02d}"
    else:
        raise ValueError(f"Unparseable PRESF sensor caldate: {date_str!r}")

    year = part3
    if len(year) == 2:
        yyyy = "20" + year
    elif len(year) == 4:
        yyyy = year
    else:
        raise ValueError(f"Unparseable PRESF sensor caldate: {date_str!r}")

    return f"{yyyy}{mm}{dd}"
