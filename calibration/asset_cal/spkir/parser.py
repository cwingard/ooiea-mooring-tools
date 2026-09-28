"""Calibration parser for the SPKIR instrument class (Satlantic OCR-507).

Ported from tools/matlab/Endurance_cal_scripts/spkir/rad_read_spkir_cal.m
and write_spkir_cal_to_csv.m in asset-management.

B and J share the same source format (Satlantic .cal file) and
coefficient set, so this is one SpkirParser registered as "SPKIR-B"
and "SPKIR-J" with the series fixed at construction time -- same
pattern as FlortParser. The Matlab serial-number-to-series lists are
not ported (explicit CLASS-SERIES on the command line instead).

Differences from the Matlab source, all deliberate:

- The serial number is read from the "SN nnnn" line with a regex,
  not from fixed character positions 4-7 of the line after
  "INSTRUMENT", so it does not silently truncate a 5-digit serial.
- The output filename zero-pads the serial to 5 digits instead of
  prepending a literal "00", which only works for 3-digit serials.
- The cal date is the last "# YYYY-MM-DD |" row of the calibration
  history table, found by pattern rather than as "the line before
  the first line without a '#'". Same row for every file checked;
  the pattern form does not depend on header layout.

Coefficient values are carried through as the exact strings in the
.cal file (e.g. "1.96915114139e-007", "1.410"), never round-tripped
through float -- the Matlab source does the same, and the archived
csvs keep Satlantic's formatting (trailing zeros, 3-digit exponents).
Each file must hold exactly 7 "ED" channels.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

N_CHANNELS = 7

_SERIAL_PATTERN = re.compile(r"^SN\s+(\d+)\b")
_HISTORY_DATE_PATTERN = re.compile(r"^#\s*(\d{4})-(\d{2})-(\d{2})\s*\|")
_CHANNEL_PATTERN = re.compile(r"^ED\s+\S+\s+'uW/cm\^2/nm'")


@dataclass(frozen=True)
class SpkirCal:
    """Calibration coefficients parsed from a Satlantic OCR-507 .cal file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, from the "SN nnnn" line.
    series : str
        "B" or "J", as supplied by the caller -- not derived from
        the serial number.
    caldate : str
        Calibration date as YYYYMMDD, from the last row of the
        calibration history table.
    source_name : str
        File name of the .cal file, recorded in the provenance note.
    offset, scale, immersion_factor : tuple[str, ...]
        Per-channel coefficients (7 each, in wavelength order),
        exact strings as read from the file.
    """

    serial_number: int
    series: str
    caldate: str
    source_name: str
    offset: tuple[str, ...]
    scale: tuple[str, ...]
    immersion_factor: tuple[str, ...]


class SpkirParser(SeriesParser[SpkirCal]):
    """Parses SPKIR (Satlantic OCR-507) .cal files for a fixed series."""

    class_code: ClassVar[str] = "SPKIR"

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path) -> SpkirCal:
        """Parse a Satlantic OCR-507 .cal file into a SpkirCal.

        Raises
        ------
        ValueError
            If the serial number, calibration history date, or
            exactly 7 complete ED channel rows cannot be found.
        """
        # latin-1 never fails to decode; the operator names in the
        # history table are free text typed at Satlantic.
        lines = source_path.read_text(encoding="latin-1").splitlines()

        offset, scale, immersion = _find_channels(lines)
        return SpkirCal(
            serial_number=_find_serial_number(lines),
            series=self.series,
            caldate=_find_caldate(lines),
            source_name=source_path.name,
            offset=offset,
            scale=scale,
            immersion_factor=immersion,
        )

    def write_csv(
        self, cal: SpkirCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a SPKIR calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/SPKIR<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; SPKIR calibration csvs "
                "are never written into a directory this script creates itself."
            )

        filename = f"CGINS-{self.class_code}{self.series}-{cal.serial_number:05d}__{cal.caldate}.csv"
        provenance = f"date in filename comes from latest caldate within factory calfile {cal.source_name}"
        coefficients = [
            CalCoefficient("CC_immersion_factor", _json_array(cal.immersion_factor), provenance),
            CalCoefficient("CC_offset", _json_array(cal.offset)),
            CalCoefficient("CC_scale", _json_array(cal.scale)),
        ]
        return write_cal_csv(output_dir / filename, str(cal.serial_number), coefficients)


def _json_array(values: tuple[str, ...]) -> str:
    """Format exact strings as a quoted JSON-style array for the csv."""
    return '"[' + ", ".join(values) + ']"'


def _find_serial_number(lines: list[str]) -> int:
    for line in lines:
        match = _SERIAL_PATTERN.match(line.strip())
        if match:
            return int(match.group(1))
    raise ValueError("Could not find 'SN <serial>' line in cal file.")


def _find_caldate(lines: list[str]) -> str:
    dates = [m.groups() for m in (_HISTORY_DATE_PATTERN.match(line.strip()) for line in lines) if m]
    if not dates:
        raise ValueError("Could not find any '# YYYY-MM-DD |' calibration history rows in cal file.")
    return "".join(dates[-1])


def _find_channels(lines: list[str]) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Returns (offset, scale, immersion_factor) across all ED channels."""
    rows: list[list[str]] = []
    for idx, line in enumerate(lines):
        if _CHANNEL_PATTERN.match(line.strip()):
            tokens = lines[idx + 1].split() if idx + 1 < len(lines) else []
            if len(tokens) != 3:
                raise ValueError(f"Expected 3 coefficients after channel line {line.strip()!r}; got {tokens!r}")
            for token in tokens:
                float(token)  # validate numeric; the string itself is kept
            rows.append(tokens)
    if len(rows) != N_CHANNELS:
        raise ValueError(f"Expected {N_CHANNELS} ED irradiance channels in cal file; found {len(rows)}.")
    offset, scale, immersion = zip(*rows)
    return offset, scale, immersion
