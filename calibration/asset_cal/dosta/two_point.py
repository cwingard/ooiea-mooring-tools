"""Calibration csv for a DOSTA after an in-house (OSU) 2-point Winkler recalibration.

Source: the OOI "Oxygen Optode Calibration Form" (control number 3305-01815,
"2-POINT WINKLER CALIBRATION for MULTIPOINT CALIBRATED OXYGEN OPTODE (OSU)"),
exported to PDF. There was no MATLAB script for this; earlier OSU 2-point
files in asset-management were written by hand.

What the form provides and how it is used
-----------------------------------------
- "Optode Serial Number", "2-Point Recalibration Date" (the csv date) and
  "Last Multipoint Calibration Filename" (an asset-management csv name).
- Calibration points: for the air-saturated 10 C calibration bath, the
  zero-oxygen (Na2SO3) bath and the air-saturated 20 C check bath, the
  optode Phase and Temperature, the "Mean optode reading" and the Winkler
  target (N/A, i.e. 0, for the zero bath).
- Calibration results: ConcCoef offset and slope and the 20 C check
  percentage, with the acceptance window in the column header
  (e.g. "20 C Check [-1.8% +/- 2%]").
- Settings: SVUFoilCoef, PhaseCoef and TempCoef as loaded on the optode.

The mean optode readings are the optode's raw Stern-Volmer-Uchida (SVU)
output with no ConcCoef applied (the SVU equation reproduces them from
Phase and Temperature), so the form's offset and slope replace
CC_conc_coef outright; they are not composed with any earlier ConcCoef.
The multipoint SVU coefficients are unchanged by a 2-point recalibration,
so CC_csv is copied verbatim from the named multipoint file.

Output matches the OSU files already in asset-management:
CC_conc_coef "[offset, slope]" as printed on the form, noted
"offset and slope determined at Oregon State University", then CC_csv.

Checks that stop the run (the form is internally inconsistent, or points
at the wrong multipoint calibration):
- a required field is missing or ambiguous, or the table layout is not
  recognised;
- the named multipoint file is not in the output folder, is for a
  different serial, is not older than the 2-point date, or its CC_csv
  disagrees with the form's SVUFoilCoef;
- the offset and slope refitted from the Winkler targets and mean
  readings disagree with the printed ConcCoef;
- the 20 C check recomputed with the refitted coefficients disagrees
  with the printed percentage. (The form computes it with the unrounded
  fit: for SN 315 2024-11-15 the printed -2.62/1.0554 give -0.415 %,
  the full-precision fit -0.417 %, printed -0.42 %.)

Numbers are compared with asset_cal.common.compare.values_agree (one unit
in the last printed place).

Warnings only (never stop the run):
- the printed 20 C check is outside the window in its column header;
- a mean optode reading differs from the SVU equation applied to its
  Phase and Temperature by more than SVU_TOLERANCE_UM (a mean of
  per-sample SVU values need not equal SVU of the mean inputs exactly);
- PhaseCoef is not the identity (the SVU recheck then means little);
- a DOSTA file for this serial dated between the multipoint file and the
  2-point date carries a different CC_csv (the form's "Last Multipoint
  Calibration Filename" may be stale).

The PDF's file name is never parsed.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar

from asset_cal.common.compare import values_agree
from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

CONC_COEF_NOTE = "offset and slope determined at Oregon State University"
# Allowed difference (uM) between a printed mean optode reading and the SVU
# equation evaluated at the printed mean Phase and Temperature.
SVU_TOLERANCE_UM = Decimal("0.05")

Table = list[list[str | None]]

_PLUS_MINUS = chr(0x00B1)
_WINDOW = re.compile(
    r"\[\s*([-+]?\d+(?:\.\d+)?)\s*%\s*(?:" + _PLUS_MINUS + r"|\+/-|\+-)\s*(\d+(?:\.\d+)?)\s*%\s*\]"
)
_AM_NAME = re.compile(r"^CGINS-DOSTA([A-Z])-(\d{5})__(\d{8})\.csv$")
_IDENTITY_PHASE = ("0", "1", "0", "0")
# Calibration Points rows: key -> label prefix ("phase (" so PhaseCoef does not match).
_POINT_ROWS = {
    "phase": "phase (",
    "optode temperature": "optode temperature",
    "mean optode reading": "mean optode reading",
    "winkler target": "winkler target",
}


@dataclass(frozen=True)
class DostaTwoPointCal:
    """One OSU 2-point recalibration, ready to write.

    Attributes
    ----------
    serial_number : int
        Optode serial number.
    series : str
        Series letter of the multipoint file's folder (always "D" now).
    caldate : str
        2-point recalibration date, YYYYMMDD.
    offset, slope : str
        ConcCoef exactly as printed on the form.
    svu_csv : str
        CC_csv value copied verbatim from the multipoint file, already
        wrapped in double quotes for the csv.
    multipoint_file : str
        Name of the multipoint file CC_csv was taken from.
    warnings : tuple[str, ...]
        Findings that do not stop the run; returned by review().
    """

    serial_number: int
    series: str
    caldate: str
    offset: str
    slope: str
    svu_csv: str
    multipoint_file: str
    warnings: tuple[str, ...] = ()


class DostaTwoPointParser(SeriesParser[DostaTwoPointCal]):
    """Parses an OSU 2-point Winkler calibration form for a DOSTA-D.

    Registered in cli.PARSERS as "DOSTA2P-D"; class_code stays "DOSTA"
    so the csv lands in calibration/DOSTAD with the usual name.
    """

    class_code: ClassVar[str] = "DOSTA"
    reads_calibration_folder: ClassVar[bool] = True

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path, calibration_folder: Path) -> DostaTwoPointCal:
        """Parse the form PDF and check it against asset-management.

        Parameters
        ----------
        source_path : Path
            The 2-point calibration form, as PDF.
        calibration_folder : Path
            asset-management calibration/DOSTA<series>, which must hold
            the form's "Last Multipoint Calibration Filename".

        Raises
        ------
        ValueError
            If the form is incomplete or inconsistent, or disagrees
            with the multipoint file.
        FileNotFoundError
            If the multipoint file is not in calibration_folder.
        """
        return parse_tables(_read_pdf_tables(source_path), calibration_folder, self.series)

    def review(
        self, cal: DostaTwoPointCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> list[str]:
        """Warnings collected while parsing."""
        return list(cal.warnings)

    def write_csv(
        self, cal: DostaTwoPointCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write the DOSTA csv into calibration_root/DOSTA<series>.

        Raises
        ------
        FileNotFoundError
            If the output folder does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{cal.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; DOSTA calibration csvs "
                "are never written into a directory this script creates itself."
            )
        filename = f"CGINS-{self.class_code}{cal.series}-{cal.serial_number:05d}__{cal.caldate}.csv"
        coefficients = [
            CalCoefficient("CC_conc_coef", f'"[{cal.offset}, {cal.slope}]"', CONC_COEF_NOTE),
            CalCoefficient("CC_csv", cal.svu_csv),
        ]
        return write_cal_csv(output_dir / filename, str(cal.serial_number), coefficients)


def parse_tables(tables: list[Table], calibration_folder: Path, series: str) -> DostaTwoPointCal:
    """Build a DostaTwoPointCal from the form's extracted tables.

    Split from DostaTwoPointParser.parse so it can be tested without a
    PDF. Tables are read by their row labels and column headers, not
    by position on the page.

    Parameters
    ----------
    tables : list[Table]
        Every table on the form, as pdfplumber extract_tables() returns
        them (rows of cell strings or None).
    calibration_folder : Path
        asset-management calibration/DOSTA<series>.
    series : str
        Series letter the output is for.

    Returns
    -------
    DostaTwoPointCal

    Raises
    ------
    ValueError
        If the form is incomplete or inconsistent, or disagrees with
        the multipoint file.
    FileNotFoundError
        If the multipoint file is not in calibration_folder.
    """
    rows = [[_clean(cell) for cell in row] for table in tables for row in table if row]
    warnings: list[str] = []

    serial = int(_number(_value(rows, "optode serial number"), "Optode Serial Number"))
    caldate = _parse_date(_value(rows, "2-point recalibration date"))
    multipoint_name = _value(rows, "last multipoint calibration filename")

    # Calibration points, by column header.
    points = _calibration_points(rows)
    readings = {k: _dec(v, f"mean optode reading ({k})") for k, v in points["mean optode reading"].items()}
    targets = {
        k: Decimal(0) if v.upper() in ("N/A", "NA") else _dec(v, f"Winkler target ({k})")
        for k, v in points["winkler target"].items()
    }

    # Printed results.
    offset, slope, check_pct, window = _results(rows)

    # Refit and compare.
    fit_slope = (targets["cal"] - targets["zero"]) / (readings["cal"] - readings["zero"])
    fit_offset = targets["cal"] - fit_slope * readings["cal"]
    for name, printed, fitted in (("offset", offset, fit_offset), ("slope", slope, fit_slope)):
        if not values_agree(printed, str(fitted)):
            raise ValueError(
                f"ConcCoef {name}: printed {printed}, but the Winkler targets and mean readings give "
                f"{fitted:.6f}."
            )
    fit_check = ((fit_offset + fit_slope * readings["check"]) / targets["check"] - 1) * 100
    if not values_agree(check_pct, str(fit_check)):
        raise ValueError(f"20 C check: printed {check_pct} %, but the refitted coefficients give {fit_check:.3f} %.")
    if window is None:
        warnings.append("20 C check: acceptance window not found in the column header; not checked.")
    else:
        center, half = window
        if not center - half <= Decimal(check_pct) <= center + half:
            warnings.append(
                f"20 C check {check_pct} % is outside the acceptance window [{center} % +/- {half} %]."
            )

    # Optode settings.
    svu_form = _row_values(rows, "svufoilcoef", 7)
    phase_coef = _row_values(rows, "phasecoef", 4)
    if any(Decimal(p) != Decimal(i) for p, i in zip(phase_coef, _IDENTITY_PHASE)):
        warnings.append(f"PhaseCoef is not the identity ({phase_coef}); the SVU recheck below assumes it is.")
    svu_c = [Decimal(v) for v in svu_form]
    for key in ("cal", "zero", "check"):
        phase = _dec(points["phase"][key], f"phase ({key})")
        temp = _dec(points["optode temperature"][key], f"optode temperature ({key})")
        expected = _svu(svu_c, phase, temp)
        if abs(expected - readings[key]) > SVU_TOLERANCE_UM:
            warnings.append(
                f"Mean optode reading ({key}) {readings[key]} uM differs from SVU(phase {phase}, "
                f"temperature {temp}) = {expected:.2f} uM by more than {SVU_TOLERANCE_UM} uM."
            )

    # The multipoint file.
    multipoint_path = calibration_folder / multipoint_name
    if not multipoint_path.is_file():
        raise FileNotFoundError(
            f"Last Multipoint Calibration Filename {multipoint_name!r} is not in {calibration_folder}."
        )
    name_match = _AM_NAME.match(multipoint_name)
    if name_match is None or name_match.group(1) != series:
        raise ValueError(f"{multipoint_name!r} is not a DOSTA{series} calibration csv name.")
    multipoint_date = name_match.group(3)
    if multipoint_date >= caldate:
        raise ValueError(f"Multipoint file {multipoint_name} is not older than the 2-point date {caldate}.")
    mp_serial, svu_am = _read_cc_csv(multipoint_path)
    if mp_serial != serial:
        raise ValueError(f"{multipoint_name} is for serial {mp_serial}, not the form's {serial}.")
    am_values = _split_array(svu_am)
    if len(am_values) != len(svu_form) or not all(map(values_agree, am_values, svu_form)):
        raise ValueError(f"SVUFoilCoef on the form {svu_form} does not match CC_csv in {multipoint_name} {svu_am}.")

    warnings.extend(_stale_reference(calibration_folder, series, serial, multipoint_date, caldate, am_values))

    return DostaTwoPointCal(
        serial_number=serial,
        series=series,
        caldate=caldate,
        offset=offset,
        slope=slope,
        svu_csv=f'"{svu_am}"',
        multipoint_file=multipoint_name,
        warnings=tuple(warnings),
    )


def _read_pdf_tables(path: Path) -> list[Table]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("DOSTA 2-point needs pdfplumber: conda install -c conda-forge pdfplumber") from exc
    with pdfplumber.open(path) as pdf:
        return [table for page in pdf.pages for table in page.extract_tables()]


def _clean(cell: str | None) -> str:
    return " ".join((cell or "").split())


def _key(cell: str) -> str:
    return cell.lower()


def _rows_starting(rows: list[list[str]], prefix: str) -> list[list[str]]:
    return [row for row in rows if _key(row[0]).startswith(prefix)]


def _value(rows: list[list[str]], label: str) -> str:
    """The single non-empty value next to a label."""
    matches = {row[1] for row in _rows_starting(rows, label) if len(row) > 1 and row[1]}
    if len(matches) != 1:
        raise ValueError(f"Expected one value for {label!r} on the form; found {sorted(matches) or 'none'}.")
    return matches.pop()


def _row_values(rows: list[list[str]], label: str, count: int) -> list[str]:
    """The first count cells after a label that must appear exactly once."""
    matches = _rows_starting(rows, label)
    if len(matches) != 1:
        raise ValueError(f"Expected one {label!r} row on the form; found {len(matches)}.")
    values = matches[0][1:1 + count]
    if len(values) != count or not all(values):
        raise ValueError(f"{label!r} row has fewer than {count} values: {matches[0]}.")
    for v in values:
        _dec(v, label)
    return values


def _calibration_points(rows: list[list[str]]) -> dict[str, dict[str, str]]:
    """Phase, temperature, mean reading and Winkler target per bath.

    Columns are identified by header text: "Zero" -> zero-oxygen bath,
    "Check" -> 20 C check bath, the other "Calibration" column -> the
    air-saturated calibration bath.
    """
    headers = _rows_starting(rows, "property")
    if len(headers) != 1:
        raise ValueError("Calibration Points table ('Property' header row) not found once on the form.")
    columns: dict[str, int] = {}
    for idx, text in enumerate(headers[0][1:], start=1):
        low = text.lower()
        key = "zero" if "zero" in low else "check" if "check" in low else "cal" if "calibration" in low else None
        if key is not None:
            if key in columns:
                raise ValueError(f"Calibration Points header has more than one {key!r} column: {headers[0]}.")
            columns[key] = idx
    if set(columns) != {"cal", "zero", "check"}:
        raise ValueError(f"Calibration Points header not recognised: {headers[0]}.")
    points: dict[str, dict[str, str]] = {}
    for label, prefix in _POINT_ROWS.items():
        matches = _rows_starting(rows, prefix)
        if len(matches) != 1:
            raise ValueError(f"Expected one {label!r} row in Calibration Points; found {len(matches)}.")
        row = matches[0]
        try:
            points[label] = {key: row[idx] for key, idx in columns.items()}
        except IndexError:
            raise ValueError(f"{label!r} row is shorter than the Calibration Points header: {row}.") from None
    return points


def _results(rows: list[list[str]]) -> tuple[str, str, str, tuple[Decimal, Decimal] | None]:
    """Printed offset, slope, 20 C check % and its acceptance window."""
    headers = [row for row in rows if "Offset" in row and "Slope" in row]
    if len(headers) != 1:
        raise ValueError("Calibration Results header ('Offset', 'Slope') not found once on the form.")
    header = headers[0]
    check_cols = [i for i, text in enumerate(header) if "check" in text.lower()]
    if len(check_cols) != 1:
        raise ValueError(f"Calibration Results header has no single check column: {header}.")
    matches = _rows_starting(rows, "conccoef")
    if len(matches) != 1:
        raise ValueError(f"Expected one 'ConcCoef' row on the form; found {len(matches)}.")
    row = matches[0]
    offset, slope = row[header.index("Offset")], row[header.index("Slope")]
    check = row[check_cols[0]].replace("%", "").strip()
    for name, text in (("offset", offset), ("slope", slope), ("20 C check", check)):
        _dec(text, f"ConcCoef {name}")
    window_match = _WINDOW.search(header[check_cols[0]])
    window = None if window_match is None else (Decimal(window_match.group(1)), Decimal(window_match.group(2)))
    return offset, slope, check, window


def _svu(c: list[Decimal], phase: Decimal, temp: Decimal) -> Decimal:
    """Aanderaa Stern-Volmer-Uchida oxygen (uM), salinity 0."""
    ksv = c[0] + c[1] * temp + c[2] * temp * temp
    p0 = c[3] + c[4] * temp
    pc = c[5] + c[6] * phase
    return (p0 / pc - 1) / ksv


def _read_cc_csv(path: Path) -> tuple[int, str]:
    """(serial, CC_csv value without quotes) from an asset-management DOSTA csv."""
    with path.open(newline="", encoding="ascii") as fh:
        found = [(row["serial"], row["value"]) for row in csv.DictReader(fh) if row["name"] == "CC_csv"]
    if len(found) != 1:
        raise ValueError(f"Expected one CC_csv row in {path.name}; found {len(found)}.")
    serial, value = found[0]
    return int(serial), value


def _split_array(value: str) -> list[str]:
    return [v.strip() for v in value.strip().strip("[]").split(",")]


def _stale_reference(
    folder: Path, series: str, serial: int, after: str, before: str, svu: list[str]
) -> list[str]:
    """Warn about files between the multipoint and 2-point dates with a different CC_csv."""
    warnings = []
    for path in sorted(folder.glob(f"CGINS-DOSTA{series}-{serial:05d}__*.csv")):
        match = _AM_NAME.match(path.name)
        if match is None or not after < match.group(3) < before:
            continue
        try:
            other = _split_array(_read_cc_csv(path)[1])
        except (ValueError, KeyError) as exc:
            warnings.append(f"{path.name} could not be read for the stale-reference check: {exc}")
            continue
        if len(other) != len(svu) or not all(map(values_agree, other, svu)):
            warnings.append(
                f"{path.name} (between the multipoint file and this 2-point) has a different CC_csv; "
                "the form's Last Multipoint Calibration Filename may be stale."
            )
    return warnings


def _parse_date(text: str) -> str:
    cleaned = text.strip().strip("[]").strip()
    try:
        return date.fromisoformat(cleaned).strftime("%Y%m%d")
    except ValueError:
        raise ValueError(f"2-Point Recalibration Date must be YYYY-MM-DD; got {text!r}.") from None


def _dec(text: str, what: str) -> Decimal:
    try:
        return Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"{what}: not a number: {text!r}.") from None


def _number(text: str, what: str) -> str:
    if not text.strip().isdigit():
        raise ValueError(f"{what}: not an integer: {text!r}.")
    return text.strip()
