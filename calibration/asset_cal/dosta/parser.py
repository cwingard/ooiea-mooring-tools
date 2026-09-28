"""Calibration parser for the DOSTA instrument class (series D and J).

Ported from tools/matlab/Endurance_cal_scripts/dosta/write_dosta_qct_to_csv.m.

D and J share identical source format (QCT text file) and coefficient
set -- they only differ in which series letter lands in the output
filename -- so this is one DostaParser class, registered under both
"DOSTA-D" and "DOSTA-J" in cli.PARSERS with the series fixed at
construction time. There is no serial-number-to-series lookup here:
the cli requires the operator to state the series explicitly, and
that's what gets used. The Matlab source's own seriesD/seriesJ
hardcoded lists (and the ismember check that picks between them) are
NOT ported, by agreement -- they were also confirmed stale against
the real calibration/DOSTAD archive.

parse() is a direct port of the Matlab textscan-based field
extraction (Serial Number / ConcCoef / SVUFoilCoef lines, tab and
space delimited). UNVERIFIED: no real DOSTA QCT file was available
to confirm token positions against. Treat this as a best-effort
translation pending a real sample, not validated behavior.

The QCT capture does not contain the calibration date (it is on the
vendor PDF certificate). The Matlab workflow had the operator append
it to the QCT filename; here it is passed explicitly as
parse(..., caldate="YYYYMMDD") (cli: --caldate) and the source
filename is never read.

write_csv() is not subject to that caveat -- its output format is
fixed by the archived calibration/DOSTAD and calibration/DOSTAJ csv
files, which do not depend on QCT parsing details.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser, check_caldate

_CALDATE_PROVENANCE = "date in filename comes from factory calibration certificate"

_TOKEN_SPLIT = re.compile(r"[\t ]+")


@dataclass(frozen=True)
class DostaCal:
    """Calibration coefficients parsed from a DOSTA QCT file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, cross-checked between two
        occurrences on the QCT's "Serial Number" line.
    series : str
        "D" or "J", as supplied by the caller -- not derived from
        the serial number.
    caldate : str
        Calibration date as YYYYMMDD, supplied by the operator from
        the vendor certificate (cli: --caldate).
    conc_coef_offset : str
        ConcCoef offset, exact string as read from the file.
    conc_coef_slope : str
        ConcCoef slope, exact string as read from the file.
    svu_coefficients : list[str]
        The 7-element Stern-Volmer-Uchida foil coefficient array,
        exact strings as read from the file.
    """

    serial_number: int
    series: str
    caldate: str
    conc_coef_offset: str
    conc_coef_slope: str
    svu_coefficients: list[str] = field(default_factory=list)


class DostaParser(SeriesParser[DostaCal]):
    """Parses DOSTA QCT files for a fixed series (D or J)."""

    class_code: ClassVar[str] = "DOSTA"
    requires_caldate: ClassVar[bool] = True

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path, caldate: str | None = None) -> DostaCal:
        """Parse a DOSTA QCT text file into a DostaCal.

        UNVERIFIED -- see module docstring. caldate (YYYYMMDD, from
        the vendor certificate) is required.

        Raises
        ------
        ValueError
            If the serial number, ConcCoef, SVUFoilCoef, or caldate
            cannot be found or parsed.
        """
        caldate = check_caldate(caldate, self.class_code)
        lines = source_path.read_text(encoding="ascii").splitlines()

        serial_number = _find_serial_number(lines)
        offset, slope = _find_conc_coef(lines)
        svu_coefficients = _find_svu_coefficients(lines)

        return DostaCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            conc_coef_offset=offset,
            conc_coef_slope=slope,
            svu_coefficients=svu_coefficients,
        )

    def write_csv(
        self, cal: DostaCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a DOSTA calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/DOSTA<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; DOSTA calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_str = f"{cal.serial_number:05d}"
        filename = f"CGINS-{self.class_code}{self.series}-{sn_str}__{cal.caldate}.csv"
        output_path = output_dir / filename

        conc_coef = f'"[{cal.conc_coef_offset}, {cal.conc_coef_slope}]"'
        svu = '"[' + ", ".join(cal.svu_coefficients) + ']"'

        coefficients = [
            CalCoefficient("CC_conc_coef", conc_coef, _CALDATE_PROVENANCE),
            CalCoefficient("CC_csv", svu, ""),
        ]
        return write_cal_csv(output_path, str(cal.serial_number), coefficients)


def _find_serial_number(lines: list[str]) -> int:
    """UNVERIFIED -- see module docstring."""
    for line in lines:
        if "Serial Number" in line:
            tokens = [t for t in _TOKEN_SPLIT.split(line.strip()) if t]
            if len(tokens) < 4:
                raise ValueError(f"Could not parse 'Serial Number' line: {line!r}")
            sernum, sernum_check = tokens[3], tokens[2]
            if sernum != sernum_check:
                raise ValueError(
                    f"Serial number values within QCT do not agree: {sernum!r} != {sernum_check!r}"
                )
            return int(sernum)
    raise ValueError("Could not find 'Serial Number' line in QCT file.")


def _find_conc_coef(lines: list[str]) -> tuple[str, str]:
    """UNVERIFIED -- see module docstring."""
    for line in lines:
        if "ConcCoef" in line:
            tokens = [t for t in _TOKEN_SPLIT.split(line.strip()) if t]
            if len(tokens) < 5:
                raise ValueError(f"Could not parse 'ConcCoef' line: {line!r}")
            return tokens[3], tokens[4]
    raise ValueError("Could not find 'ConcCoef' line in QCT file.")


def _find_svu_coefficients(lines: list[str]) -> list[str]:
    """UNVERIFIED -- see module docstring."""
    for line in lines:
        if "SVUFoilCoef" in line:
            tokens = [t for t in _TOKEN_SPLIT.split(line.strip()) if t]
            svu = tokens[3:]
            if not svu:
                raise ValueError(f"No SVU coefficients found in line: {line!r}")
            return svu
    raise ValueError("Could not find 'SVUFoilCoef' line in QCT file.")
