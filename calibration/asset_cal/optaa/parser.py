"""Calibration parser for the OPTAA instrument class (WET Labs AC-S).

Ported from tools/matlab/Endurance_cal_scripts/optaa/write_optaa_dev_to_csv.m
and .../optaa/rad_read_acs_devfile.m.

C, D, and J share identical source format (WET Labs tab-delimited
devfile) and coefficient set -- they only differ in which series
letter lands in the output filename -- so this is one OptaaParser
class, registered under "OPTAA-C", "OPTAA-D", and "OPTAA-J" with the
series fixed at construction time. No serial-number lookup, same
reasoning as every other multi-series class.

UNLIKE every other class ported so far, this Matlab source does NOT
pass source-file text through verbatim: coefficients are parsed into
floats and re-serialized through fixed-precision sprintf calls
(%.1f for wavelengths and Tcal, %.6f for offsets and temperature
bins). OptaaCal therefore stores floats, not strings, and write_csv
reformats them to match -- the opposite fidelity policy from every
prior class, deliberately, because that IS what the current script
does.

parse() is a structural port of rad_read_acs_devfile.m: fixed header
line positions (serial number as a hex substring on line 2, a
regex-heavy Tcal/Ical/date line on line 4, nwvl/ntbin/tbin on lines
8-10), followed by a tab-delimited wavelength table with
ntbin-dependent column widths. Tested against a real devfile
(ACS-135, offsets saved 2/8/2024): the csv matches the committed
CGINS-OPTAAD-00135__20240208.csv row for row and both side-car files
match value for value. Header values are read with the devfile's
trailing "; description" comments stripped.

write_csv() is tested against calibration/OPTAAD/
CGINS-OPTAAD-00123__20121128.csv and its taarray/tcarray side-car
files. Notable:

- Writes THREE files per call (the main csv plus two "*.ext"
  side-car files holding the temperature-compensation matrices),
  matching the Matlab source's three return values. The
  SeriesParser interface only requires one Path back, so write_csv
  returns the main csv path; the two side-car writes are a
  documented side effect.
- The serial column is "ACS-<sernum>"; the filename's serial
  component is a literal "00" + str(sernum) (NOT a 5-digit
  zero-pad -- confirmed against the archive, which never has a
  4-digit serial to distinguish the two conventions, but the Matlab
  source's string concatenation is unambiguous).
- All files are written with LF line endings on every platform.
- Side-car files are comma-separated values in Matlab csvwrite
  style: Python's str(float), except whole numbers are written
  without ".0" (csvwrite writes 0, not 0.0).
- Rows are written in the Matlab script's order (tcal, awlngth,
  acwo, cwlngth, ccwo, tbins, taarray, tcarray), not alphabetically.
- The provenance note is attached to CC_tcal, as in the Matlab
  source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from dateutil import parser as date_parser

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_CALDATE_PROVENANCE = "date in filename comes from 'offsets saved' date within factory devfile"

_TCAL_RE = re.compile(r"tcal:\s*(-?\d+(?:\.\d+)?)\s*C\b", re.IGNORECASE)
_ICAL_RE = re.compile(r"ical:\s*(-?\d+(?:\.\d+)?)\s*C\b", re.IGNORECASE)
_SAVED_DATE_RE = re.compile(r"(?:saved to this file on|file created on:?)\s+(.+?)[\s.\"']*$", re.IGNORECASE)


@dataclass(frozen=True)
class OptaaCal:
    """Calibration coefficients parsed from an OPTAA (AC-S) devfile.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, parsed from a hex substring on
        the devfile's 2nd line.
    series : str
        "C", "D", or "J", as supplied by the caller.
    caldate : str
        Calibration date as YYYYMMDD, from the "offsets saved" date
        on the devfile's 4th line.
    cwvl, coff : list[float]
        Beam-c wavelengths and pure-water offsets.
    awvl, aoff : list[float]
        Absorption wavelengths and pure-water offsets.
    tcal : float
        Factory cal water temperature.
    tbin : list[float]
        Internal temperature compensation bin values.
    ctbin, atbin : list[list[float]]
        Per-wavelength temperature compensation matrices for the
        beam-c and absorption channels (nwvl rows x ntbin columns),
        written to the CC_tcarray/CC_taarray side-car files.
    """

    serial_number: int
    series: str
    caldate: str
    cwvl: list[float] = field(default_factory=list)
    coff: list[float] = field(default_factory=list)
    awvl: list[float] = field(default_factory=list)
    aoff: list[float] = field(default_factory=list)
    tcal: float = 0.0
    tbin: list[float] = field(default_factory=list)
    ctbin: list[list[float]] = field(default_factory=list)
    atbin: list[list[float]] = field(default_factory=list)


class OptaaParser(SeriesParser[OptaaCal]):
    """Parses OPTAA (WET Labs AC-S) devfiles for a fixed series."""

    class_code: ClassVar[str] = "OPTAA"

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path) -> OptaaCal:
        """Parse an OPTAA devfile into an OptaaCal.


        Raises
        ------
        ValueError
            If the header lines, wavelength table, or any field
            cannot be parsed.
        """
        lines = source_path.read_text(encoding="ascii").splitlines()
        if len(lines) < 10:
            raise ValueError("Dev file has fewer than the expected 10 header lines.")

        serial_number = _find_serial_number(lines[1])
        tcal, _ical, date_str = _parse_offset_save_row(lines[3])
        caldate = date_str[:4] + date_str[5:7] + date_str[8:10]

        nwvl = int(_strip_comment(lines[7]))
        ntbin = int(_strip_comment(lines[8]))
        if ntbin == 0:
            raise ValueError(
                "Devfile has no temperature-correction table (0 temperature bins), so CC_tbins, CC_taarray and "
                "CC_tcarray cannot be written. Use a devfile that includes the temperature correction."
            )
        tbin = [float(v) for v in _strip_comment(lines[9]).split()]
        if len(tbin) != ntbin:
            raise ValueError(f"Expected {ntbin} temperature bin values, found {len(tbin)}.")

        table_lines = lines[10:10 + nwvl]
        if len(table_lines) < nwvl:
            raise ValueError(f"Expected {nwvl} wavelength table rows, found {len(table_lines)}.")

        cwvl, awvl, coff, aoff, ctbin, atbin = _parse_wavelength_table(table_lines, ntbin)

        return OptaaCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            cwvl=cwvl,
            coff=coff,
            awvl=awvl,
            aoff=aoff,
            tcal=tcal,
            tbin=tbin,
            ctbin=ctbin,
            atbin=atbin,
        )

    def write_csv(
        self, cal: OptaaCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write OPTAA's csv plus its taarray/tcarray side-car files.

        Returns the main csv path; the two side-car files are
        written as a documented side effect (see module docstring).

        Raises
        ------
        FileNotFoundError
            If calibration_root/OPTAA<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; OPTAA calibration csvs "
                "are never written into a directory this script creates itself."
            )

        basename = f"CGINS-{self.class_code}{self.series}-00{cal.serial_number}__{cal.caldate}"
        output_path = output_dir / f"{basename}.csv"
        taarray_path = output_dir / f"{basename}__CC_taarray.ext"
        tcarray_path = output_dir / f"{basename}__CC_tcarray.ext"

        serial_column = f"ACS-{cal.serial_number}"
        # Row order follows write_optaa_dev_to_csv.m (template([3 5 6 1 2 4 7 8], :)), the order of every OPTAA
        # file committed to asset-management by that script.
        coefficients = [
            CalCoefficient("CC_tcal", f"{cal.tcal:.1f}", _CALDATE_PROVENANCE),
            CalCoefficient("CC_awlngth", _format_array(cal.awvl, 1)),
            CalCoefficient("CC_acwo", _format_array(cal.aoff, 6)),
            CalCoefficient("CC_cwlngth", _format_array(cal.cwvl, 1)),
            CalCoefficient("CC_ccwo", _format_array(cal.coff, 6)),
            CalCoefficient("CC_tbins", _format_array(cal.tbin, 6)),
            CalCoefficient("CC_taarray", "SheetRef:CC_taarray"),
            CalCoefficient("CC_tcarray", "SheetRef:CC_tcarray"),
        ]
        write_cal_csv(output_path, serial_column, coefficients)

        _write_csvwrite_style(taarray_path, cal.atbin)
        _write_csvwrite_style(tcarray_path, cal.ctbin)

        return output_path


def _format_array(values: list[float], precision: int) -> str:
    formatted = ", ".join(f"{v:.{precision}f}" for v in values)
    return f'"[{formatted}]"'


def _write_csvwrite_style(path: Path, matrix: list[list[float]]) -> None:
    lines = [",".join(_format_ext_value(v) for v in row) for row in matrix]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def _format_ext_value(value: float) -> str:
    """Format like Matlab csvwrite: whole numbers without '.0'."""
    return str(int(value)) if value == int(value) else str(value)


def _strip_comment(line: str) -> str:
    """Drop the devfile's trailing '; description' comment."""
    return line.split(";", 1)[0].strip()


def _find_serial_number(header_line_2: str) -> int:
    hex_str = _strip_comment(header_line_2)[2:8]
    try:
        return int(hex_str, 16)
    except ValueError as exc:
        raise ValueError(f"Could not parse hex serial number from: {header_line_2!r}") from exc


def _parse_offset_save_row(line: str) -> tuple[float, float, str]:
    """Returns (tcal, ical, date) where date is 'YYYY-MM-DD'.

    Accepts 'Tcal: 21.6 C, Ical: 19.9 C.' and the 2026 factory form
    without the comma. The date text after 'saved to this file on' (or
    'File created on:') is handed to dateutil.
    """
    tcal_match = _TCAL_RE.search(line)
    if tcal_match is None:
        raise ValueError(f"Could not parse Tcal acs devfile value: {line!r}")
    ical_match = _ICAL_RE.search(line)
    if ical_match is None:
        raise ValueError(f"Could not parse Ical acs devfile value: {line!r}")

    date_match = _SAVED_DATE_RE.search(line)
    if date_match is None:
        raise ValueError(f"Could not find 'offset save' date in devfile: {line!r}")
    try:
        saved = date_parser.parse(date_match.group(1)).date()
    except (date_parser.ParserError, OverflowError) as exc:
        raise ValueError(f"Could not parse 'offset save' date in devfile: {line!r}") from exc

    return float(tcal_match.group(1)), float(ical_match.group(1)), saved.isoformat()


def _parse_wavelength_table(
    table_lines: list[str], ntbin: int
) -> tuple[list[float], list[float], list[float], list[float], list[list[float]], list[list[float]]]:
    cwvl, awvl, coff, aoff, ctbin, atbin = [], [], [], [], [], []
    min_tokens = 7 + 2 * ntbin
    for line in table_lines:
        tokens = line.split("\t")
        if len(tokens) < min_tokens:
            raise ValueError(f"Wavelength table row has too few fields: {line!r}")
        cwvl.append(float(tokens[0].replace("C", "0")))
        awvl.append(float(tokens[1].replace("A", "0")))
        coff.append(float(tokens[3]))
        aoff.append(float(tokens[4]))
        ctbin.append([float(v) for v in tokens[6:6 + ntbin]])
        atbin_start = 7 + ntbin
        atbin.append([float(v) for v in tokens[atbin_start:atbin_start + ntbin]])
    return cwvl, awvl, coff, aoff, ctbin, atbin
