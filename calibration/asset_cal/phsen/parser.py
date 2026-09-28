"""Calibration parser for the PHSEN instrument class (Sunburst SAMI pH).

Ported from tools/matlab/Endurance_cal_scripts/phsen/write_phsen_qct_to_csv.m.

Endurance/CGSN PHSEN units are always series D -- the Matlab source
says so explicitly ("All instruments are assumed to be series 'D'
(Endurance)") -- so there is no serial-number lookup at all here,
unlike CTDBP/DOSTA/FLORT/PRESF/OPTAA.

The QCT text file can in principle contain two copies of the
':SAMIinfoHex'/':SAMIinfo' block; the Matlab source truncates
everything after the first ':SAMIinfo' occurrence (plus a fixed
12-line window matching the known block layout) specifically to
avoid picking up a second, possibly different, copy of the
coefficients. That truncation is ported here.

Serial numbers are alphanumeric ("P0088"), not purely numeric --
kept as str throughout, never converted to int. They're parsed from
the QCT's "Name:" line, not the "Serial Number:" line -- the Matlab
source ignores the latter too.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser, check_caldate

_QCT_LABELS = ("Cal1:", "Cal2:", "Cal3:", "Cal4:")
_OOI_NAMES = ("CC_ea434", "CC_eb434", "CC_ea578", "CC_eb578")
_MATCH_LABELS = ("Ea_434", "Eb_434", "Ea_578", "Eb_578")


@dataclass(frozen=True)
class PhsenCal:
    """Calibration coefficients parsed from a PHSEN QCT file.

    Attributes
    ----------
    serial_number : str
        Alphanumeric instrument identifier (e.g. "P0088"), parsed
        from the QCT's "Name:" line.
    series : str
        Always "D" -- PHSEN has no other series in this pipeline.
    caldate : str
        Calibration date as YYYYMMDD, supplied by the operator (the
        QCT capture does not contain it; cli: --caldate).
    ea434 : str
    eb434 : str
    ea578 : str
    eb578 : str
        The four calibration coefficients, exact strings as read
        from the file.
    """

    serial_number: str
    series: str
    caldate: str
    ea434: str
    eb434: str
    ea578: str
    eb578: str


class PhsenParser(SeriesParser[PhsenCal]):
    """Parses PHSEN (Sunburst SAMI pH) QCT files. Series is always D."""

    class_code: ClassVar[str] = "PHSEN"
    series: ClassVar[str] = "D"
    requires_caldate: ClassVar[bool] = True

    def parse(self, source_path: Path, caldate: str | None = None) -> PhsenCal:
        """Parse a PHSEN QCT text file into a PhsenCal.

        caldate (YYYYMMDD) is required; the source filename is never
        read.

        Raises
        ------
        ValueError
            If the ':SAMIinfo' block, any coefficient, the "Name:"
            serial line, or the caldate cannot be found.
        """
        caldate = check_caldate(caldate, self.class_code)
        lines = source_path.read_text(encoding="ascii").splitlines()
        lines = [line.replace("\t", " ") for line in lines]
        lines = _truncate_after_first_samiinfo_block(lines)
        lines = _substitute_cal_labels(lines)

        coeffs = {
            ooi_name: _find_coefficient(lines, match_label)
            for ooi_name, match_label in zip(_OOI_NAMES, _MATCH_LABELS)
        }
        serial_number = _find_serial_number(lines)


        return PhsenCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            ea434=coeffs["CC_ea434"],
            eb434=coeffs["CC_eb434"],
            ea578=coeffs["CC_ea578"],
            eb578=coeffs["CC_eb578"],
        )

    def write_csv(
        self, cal: PhsenCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a PHSEN calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/PHSEND does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; PHSEN calibration csvs "
                "are never written into a directory this script creates itself."
            )

        filename = f"CGINS-{self.class_code}{self.series}-{cal.serial_number}__{cal.caldate}.csv"
        output_path = output_dir / filename

        coefficients = [
            CalCoefficient("CC_ea434", cal.ea434),
            CalCoefficient("CC_eb434", cal.eb434),
            CalCoefficient("CC_ea578", cal.ea578),
            CalCoefficient("CC_eb578", cal.eb578),
            CalCoefficient("CC_ind_off", "0"),
            CalCoefficient("CC_ind_slp", "1"),
            CalCoefficient("CC_psal", "35", "DELETE: use salinity from co-located CTDBP"),
            CalCoefficient("CC_sami_bits", "12"),
        ]
        return write_cal_csv(output_path, cal.serial_number, coefficients)


def _truncate_after_first_samiinfo_block(lines: list[str]) -> list[str]:
    """Keep only the first ':SAMIinfo' block (plus its 11-line body),
    matching the Matlab truncation that guards against a QCT file
    containing two copies of the coefficients."""
    marked = [line.replace(":SAMIinfoHex", "ZZTop") for line in lines]
    for i, line in enumerate(marked):
        if ":SAMIinfo" in line:
            return marked[: i + 12]
    raise ValueError("No ':SAMIinfo' block found in QCT file.")


def _substitute_cal_labels(lines: list[str]) -> list[str]:
    substituted = lines
    for qct_label, match_label in zip(_QCT_LABELS, _MATCH_LABELS):
        substituted = [line.replace(qct_label, match_label) for line in substituted]
    return substituted


def _find_coefficient(lines: list[str], match_label: str) -> str:
    matches = [line.strip() for line in lines if line.strip().lower().startswith(match_label.lower())]
    if not matches:
        raise ValueError(f"PHSEN calcoeff {match_label!r} not found in QCT file.")
    if len(matches) != 1:
        raise ValueError(f"More than one PHSEN calcoeff for {match_label!r} found in QCT file.")
    return matches[0][len(match_label):].strip()


def _find_serial_number(lines: list[str]) -> str:
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("name:"):
            return stripped[len("Name:"):].strip()
    raise ValueError("Could not find 'Name:' serial number line in QCT file.")
