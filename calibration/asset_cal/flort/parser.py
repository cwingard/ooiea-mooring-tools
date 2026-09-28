"""Calibration parser for the FLORT instrument class (WET Labs ECO BBFL2W).

Ported from tools/matlab/Endurance_cal_scripts/flort/write_flort_dev_to_csv.m.

D, J, and K share identical source format (WET Labs dev file) and
coefficient set -- they only differ in which series letter lands in
the output filename, and J additionally gets a "BBFL2W-" prefix on
the serial column (the other two series do not) -- so this is one
FlortParser class, registered under "FLORT-D", "FLORT-J", and
"FLORT-K" with the series fixed at construction time, same pattern
as DostaParser/CtdbpParser. No serial-number-to-series lookup: same
reasoning as every other multi-series class so far, and the archive
again confirmed the Matlab hardcoded lists are missing a large
fraction of real production serials.

parse() is a fairly precisely-specified port of the dev-file reading
logic and is tested against the sample dev file embedded in the
Matlab source's header comment (serial 1030, caldate 12/06/16,
lambda/chl/cdom channel rows) -- same confidence level as PARAD-J
and PHSEN-D, unlike DOSTA/CTDBP where no sample was available.

Archived notes are often far more detailed than what the
current Matlab script produces (e.g. "Measured signal output of
fluormeter in clean water..." instead of the script's blank notes)
-- same drift pattern seen in every class so far, at a larger scale
here. This port uses the current script's literal (sparser) notes,
not the archive's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_CALDATE_PROVENANCE = "date in filename comes from dev file"
_ANGULAR_RESOLUTION_NOTE = (
    "Erroneously named constant; this coefficient scales the "
    "particulate scattering at 124 degrees to total backscatter "
    "from particles"
)

_CALDATE_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2})")
_TOKEN_SPLIT = re.compile(r"[ \t]+")


@dataclass(frozen=True)
class FlortCal:
    """Calibration coefficients parsed from a FLORT dev file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, parsed from the "BBFL2-<n>" or
        "BBFL2W-<n>" token on the dev file's first line.
    series : str
        "D", "J", or "K", as supplied by the caller -- not derived
        from the serial number.
    caldate : str
        Calibration date as YYYYMMDD, parsed from the "Created on:"
        line (MM/DD/YY, same assumption as PARAD-J).
    dark_counts_cdom, scale_factor_cdom : str
    dark_counts_chlorophyll_a, scale_factor_chlorophyll_a : str
    dark_counts_volume_scatter, scale_factor_volume_scatter : str
        The six per-channel coefficients, exact strings as read
        from the "Lambda=", "Chl=", and "CDOM=" rows.
    """

    serial_number: int
    series: str
    caldate: str
    dark_counts_cdom: str
    scale_factor_cdom: str
    dark_counts_chlorophyll_a: str
    scale_factor_chlorophyll_a: str
    dark_counts_volume_scatter: str
    scale_factor_volume_scatter: str


class FlortParser(SeriesParser[FlortCal]):
    """Parses FLORT (WET Labs ECO BBFL2W) dev files for a fixed series."""

    class_code: ClassVar[str] = "FLORT"

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path) -> FlortCal:
        """Parse a FLORT dev file into a FlortCal.

        Raises
        ------
        ValueError
            If the serial number, caldate, or any channel row
            cannot be found.
        """
        lines = source_path.read_text(encoding="ascii").splitlines()
        if not lines:
            raise ValueError("Dev file is empty.")

        serial_number = _find_serial_number(lines)
        caldate = _find_caldate(lines)

        scale_lambda, dark_lambda = _find_channel_values(lines, "lambda")
        scale_chl, dark_chl = _find_channel_values(lines, "chl")
        scale_cdom, dark_cdom = _find_channel_values(lines, "cdom")

        return FlortCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            dark_counts_cdom=dark_cdom,
            scale_factor_cdom=scale_cdom,
            dark_counts_chlorophyll_a=dark_chl,
            scale_factor_chlorophyll_a=scale_chl,
            dark_counts_volume_scatter=dark_lambda,
            scale_factor_volume_scatter=scale_lambda,
        )

    def write_csv(
        self, cal: FlortCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a FLORT calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/FLORT<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; FLORT calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_str = f"{cal.serial_number:05d}"
        filename = f"CGINS-{self.class_code}{self.series}-{sn_str}__{cal.caldate}.csv"
        output_path = output_dir / filename

        serial_column = f"BBFL2W-{cal.serial_number}" if self.series.upper() == "J" else str(cal.serial_number)

        values: dict[str, tuple[str, str]] = {
            "angular_resolution": ("1.076", _ANGULAR_RESOLUTION_NOTE),
            "dark_counts_cdom": (cal.dark_counts_cdom, _CALDATE_PROVENANCE),
            "dark_counts_chlorophyll_a": (cal.dark_counts_chlorophyll_a, ""),
            "dark_counts_volume_scatter": (cal.dark_counts_volume_scatter, ""),
            "depolarization_ratio": ("0.039", "Constant"),
            "measurement_wavelength": ("700", "Constant"),
            "scale_factor_cdom": (cal.scale_factor_cdom, ""),
            "scale_factor_chlorophyll_a": (cal.scale_factor_chlorophyll_a, ""),
            "scale_factor_volume_scatter": (cal.scale_factor_volume_scatter, ""),
            "scattering_angle": ("124", "Constant"),
        }
        coefficients = [CalCoefficient(f"CC_{name}", value, note) for name, (value, note) in sorted(values.items())]

        return write_cal_csv(output_path, serial_column, coefficients)


def _get_tokens(line: str) -> list[str]:
    return [t for t in _TOKEN_SPLIT.split(line.strip()) if t]


def _find_serial_number(lines: list[str]) -> int:
    first_line_concat = "".join(_get_tokens(lines[0])).upper().replace("W", "")
    idx = first_line_concat.find("BBFL2-")
    if idx == -1:
        raise ValueError("Cannot parse serial number from within infile (no 'BBFL2-' token found).")
    suffix = first_line_concat[idx + len("BBFL2-"):]
    match = re.match(r"\d+", suffix)
    if not match:
        raise ValueError(f"Could not parse numeric serial number from: {suffix!r}")
    return int(match.group())


def _find_caldate(lines: list[str]) -> str:
    for line in lines:
        if "created" in line.lower():
            match = _CALDATE_PATTERN.search(line)
            if match:
                mm, dd, yy = match.groups()
                return f"20{yy}{int(mm):02d}{int(dd):02d}"
    raise ValueError("Could not find 'Created on:' date in dev file.")


def _find_channel_values(lines: list[str], channel: str) -> tuple[str, str]:
    """Returns (scale_factor, dark_counts) for a channel row."""
    for line in lines:
        tokens = _get_tokens(line)
        if tokens and channel in tokens[0].lower():
            if len(tokens) < 3:
                raise ValueError(f"Could not parse channel {channel!r} row: {line!r}")
            return tokens[1], tokens[2]
    raise ValueError(f"Could not find channel {channel!r} row in dev file.")
