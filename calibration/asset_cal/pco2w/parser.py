"""Calibration parser for the PCO2W instrument class (Sunburst SAMI CO2).

Replaces tools/matlab/Endurance_cal_scripts/pco2w/write_pco2w_pdf_to_csv.m
(which read the vendor PDF certificate) and
compare_pco2w_qct_v_CalCert.m (a by-eye QCT vs certificate check).

Endurance/CGSN PCO2W units are always series B.

The vendor calibration certificate (PDF) is the source of every value
written: A, B, C and Tavg at full precision, the calibration range
(used by the QC checks, only on the certificate) and the calibration
date (only on the certificate). The calibration range is the one
integer "low-high" pair (hyphen, en/em dash, or a dash glyph the PDF
reader cannot decode), the date the one "Month D, YYYY" (or
"D Month YYYY") date, and the serial the "Serial Number:" field.

Certificate only: A, B, C and Tavg come from Table 1, whose header is
"A B C K434 K620 Tavg Range (ppm)" (subscripts extract as a separate
line). The header must be present in that column order and followed
by exactly one row of six decimals and a range; anything else stops
the run and asks for the QCT capture. Every Sunburst certificate seen
so far (C0062, 2017-2025) has this layout.

With the QCT capture (optional): the certificate is not read by
position at all. Its text is treated as an unordered set of decimal
numbers, and each coefficient is the one certificate number that
rounds to the capture's Cal1-Cal4 (A, B, C and Tavg as loaded on the
sensor, e.g. Tavg 8.95 for a certificate value of 8.9474) at the
capture's displayed precision. This copes with layout changes, and
any coefficient or serial that disagrees with the sensor stops the
run: a vendor error or the wrong certificate/capture pair is never
papered over. A certificate serial of "SAMI" is replaced by the
capture's "Name:".

Neither file's name is parsed. The certificate's file name is copied
into the CC_cala note for traceability only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
            ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
            ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"), ("december", "dec"),
        ],
        start=1,
    )
    for name in names
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_MDY = re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE)
_DATE_DMY = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_RE})\.?,?\s+(\d{{4}})\b", re.IGNORECASE)
_DECIMAL_NUMBER = re.compile(r"(?<![\w.])-?\d+\.\d+(?![\w.])")
_RANGE = re.compile(r"(?<![\d.])(\d{2,5})\s*[-\u2013\u2014]\s*(\d{2,5})(?![\d.])")
# pdfplumber renders glyphs it cannot map as "(cid:NN)"; a 2023 Sunburst
# certificate prints its range dash that way ("202(cid:21)1996").
_UNMAPPED_GLYPH_BETWEEN_DIGITS = re.compile(r"(?<=\d)\s*\(cid:\d+\)\s*(?=\d)")
_CERT_SERIAL = re.compile(r"Serial\s+Number:\s*(\S+)", re.IGNORECASE)
_CAPTURE_LINE = re.compile(r"^\s*(Name|Cal[1-4]):\s*(\S+)\s*$")

_COEFFICIENTS = ("cala", "calb", "calc", "calt")  # capture Cal1-Cal4, in order

# Table 1 header as extracted: "A B C K K T Range (ppm)" (subscripts on the
# next line), or with the subscripts inline ("K434 K620 Tavg").
_TABLE_1_HEADER = re.compile(r"^\s*A\s+B\s+C\s+K(?:434)?\s+K(?:620)?\s+T(?:avg)?\s+Range\b", re.IGNORECASE)
_DEC = r"(-?\d+\.\d+)"
_TABLE_1_ROW = re.compile(
    rf"^\s*{_DEC}\s+{_DEC}\s+{_DEC}\s+{_DEC}\s+{_DEC}\s+{_DEC}\s+\d{{2,5}}\s*[-\u2013\u2014]\s*\d{{2,5}}\s*$"
)


@dataclass(frozen=True)
class Pco2wCal:
    """Calibration coefficients for one PCO2W calibration.

    Attributes
    ----------
    serial_number : str
        Instrument identifier, e.g. "C0062".
    series : str
        Always "B".
    caldate : str
        Calibration date as YYYYMMDD, from the certificate.
    cala, calb, calc, calt : str
        A, B, C and Tavg, exact strings as printed on the
        certificate.
    cal_range : str
        '"[low,high]"', ready for the csv value column.
    source_filename : str
        Certificate file name, for the CC_cala provenance note.
    """

    serial_number: str
    series: str
    caldate: str
    cala: str
    calb: str
    calc: str
    calt: str
    cal_range: str
    source_filename: str


class Pco2wParser(SeriesParser[Pco2wCal]):
    """Parses a PCO2W certificate, identified against its QCT capture."""

    class_code: ClassVar[str] = "PCO2W"
    series: ClassVar[str] = "B"
    accepts_qct: ClassVar[bool] = True

    def parse(self, source_path: Path, qct_path: Path | None = None) -> Pco2wCal:
        """Parse a certificate PDF, optionally checked against its QCT capture.

        Parameters
        ----------
        source_path : Path
            Vendor calibration certificate (PDF).
        qct_path : Path | None
            QCT capture text file for the same calibration. When
            given, values are identified against it and any
            disagreement is an error.

        Raises
        ------
        ValueError
            If any value cannot be found unambiguously, or disagrees
            between the certificate and the capture.
        """
        cert_text = _read_pdf_text(source_path)
        capture_text = None if qct_path is None else qct_path.read_text(encoding="latin-1")
        return parse_texts(cert_text, capture_text, source_path.name)

    def write_csv(
        self, cal: Pco2wCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a PCO2W calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/PCO2WB does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; PCO2W calibration csvs "
                "are never written into a directory this script creates itself."
            )

        filename = f"CGINS-{self.class_code}{self.series}-{cal.serial_number}__{cal.caldate}.csv"
        coefficients = [
            CalCoefficient("CC_cala", cal.cala, f"coeffs from {cal.source_filename}"),
            CalCoefficient("CC_calb", cal.calb),
            CalCoefficient("CC_calc", cal.calc),
            CalCoefficient("CC_calt", cal.calt),
            CalCoefficient("CC_ea434", "19706", "constant"),
            CalCoefficient("CC_ea620", "34", "constant"),
            CalCoefficient("CC_eb434", "3073", "constant"),
            CalCoefficient("CC_eb620", "44327", "constant"),
            CalCoefficient("CC_sami_bits", "12"),
            CalCoefficient("CC_cal_range", cal.cal_range),
        ]
        return write_cal_csv(output_dir / filename, cal.serial_number, coefficients)


def parse_texts(cert_text: str, capture_text: str | None, source_filename: str) -> Pco2wCal:
    """Build a Pco2wCal from certificate text and optional QCT capture text.

    Split from Pco2wParser.parse so it can be tested without a PDF.

    Parameters
    ----------
    cert_text : str
        Text extracted from the certificate PDF.
    capture_text : str | None
        Contents of the QCT capture file, or None for certificate
        only.
    source_filename : str
        Certificate file name, for the provenance note.

    Returns
    -------
    Pco2wCal

    Raises
    ------
    ValueError
        If a value is missing, ambiguous, or disagrees between the
        certificate and the capture.
    """
    cert_text = _UNMAPPED_GLYPH_BETWEEN_DIGITS.sub("-", cert_text)
    if capture_text is None:
        values = _read_table_1(cert_text)
        serial = _resolve_serial(cert_text, None)
    else:
        capture_name, capture_cals = _parse_capture(capture_text)
        cert_numbers = _DECIMAL_NUMBER.findall(cert_text)
        values = {
            name: _match_certificate_value(name, capture_value, cert_numbers)
            for name, capture_value in zip(_COEFFICIENTS, capture_cals)
        }
        serial = _resolve_serial(cert_text, capture_name)
    return Pco2wCal(
        serial_number=serial,
        series="B",
        caldate=_find_caldate(cert_text),
        cal_range=_find_cal_range(cert_text),
        source_filename=source_filename,
        **values,
    )


def _read_pdf_text(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("PCO2W needs pdfplumber: conda install -c conda-forge pdfplumber") from exc
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _parse_capture(text: str) -> tuple[str, list[str]]:
    """Return (Name, [Cal1..Cal4]) from the first :SAMIinfo block."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == ":SAMIinfo")
    except StopIteration:
        raise ValueError("QCT capture has no ':SAMIinfo' block.") from None
    found: dict[str, str] = {}
    for line in lines[start + 1:]:
        if line.startswith(":"):
            break
        match = _CAPTURE_LINE.match(line)
        if match:
            found.setdefault(match.group(1), match.group(2))
    missing = [key for key in ("Name", "Cal1", "Cal2", "Cal3", "Cal4") if key not in found]
    if missing:
        raise ValueError(f"QCT capture ':SAMIinfo' block is missing {missing}.")
    return found["Name"], [found[f"Cal{i}"] for i in range(1, 5)]


def _match_certificate_value(name: str, capture_value: str, cert_numbers: list[str]) -> str:
    """Return the one certificate number that rounds to capture_value."""
    target = Decimal(capture_value)
    exponent = target.as_tuple().exponent
    tolerance = Decimal(1).scaleb(exponent) / 2 if isinstance(exponent, int) and exponent < 0 else Decimal("0.5")
    matches = sorted({n for n in cert_numbers if abs(Decimal(n) - target) <= tolerance})
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(
            f"{name}: no certificate value matches the sensor's {capture_value} "
            "(vendor error, or certificate and capture are from different calibrations)."
        )
    raise ValueError(f"{name}: several certificate values match the sensor's {capture_value}: {matches}")


def _read_table_1(cert_text: str) -> dict[str, str]:
    """Read A, B, C, Tavg by column from the certificate's Table 1."""
    lines = cert_text.splitlines()
    header_idx = [i for i, line in enumerate(lines) if _TABLE_1_HEADER.match(line)]
    if len(header_idx) != 1:
        raise ValueError(
            "Certificate Table 1 header 'A B C K434 K620 Tavg Range' not found in the expected column order; "
            "the layout has changed -- supply the QCT capture with --qct."
        )
    rows = [m for line in lines[header_idx[0] + 1:] if (m := _TABLE_1_ROW.match(line))]
    if len(rows) != 1:
        raise ValueError(
            f"Expected one Table 1 row of six coefficients and a range after the header; found {len(rows)}. "
            "Supply the QCT capture with --qct."
        )
    a, b, c, _k434, _k620, tavg = rows[0].groups()[:6]
    return {"cala": a, "calb": b, "calc": c, "calt": tavg}


def _resolve_serial(cert_text: str, capture_name: str | None) -> str:
    match = _CERT_SERIAL.search(cert_text)
    cert_is_sami = match is not None and match.group(1).upper().startswith("SAMI")
    if capture_name is None:
        if match is None or cert_is_sami:
            raise ValueError("Certificate has no usable serial number; supply the QCT capture with --qct.")
        return _normalize_serial(match.group(1))
    capture_serial = _normalize_serial(capture_name)
    if match is None or cert_is_sami:
        return capture_serial
    cert_serial = _normalize_serial(match.group(1))
    if cert_serial != capture_serial:
        raise ValueError(f"Certificate serial {cert_serial} does not match QCT capture serial {capture_serial}.")
    return cert_serial


def _normalize_serial(raw: str) -> str:
    """'C62', 'C062', 'C0062' -> 'C0062'."""
    match = re.fullmatch(r"([A-Za-z])0*(\d{1,4})", raw.strip())
    if match is None:
        raise ValueError(f"Unrecognized PCO2W serial number: {raw!r}")
    return f"{match.group(1).upper()}{int(match.group(2)):04d}"


def _find_caldate(cert_text: str) -> str:
    dates = {
        f"{int(y):04d}{_MONTHS[m.lower()]:02d}{int(d):02d}" for m, d, y in _DATE_MDY.findall(cert_text)
    } | {f"{int(y):04d}{_MONTHS[m.lower()]:02d}{int(d):02d}" for d, m, y in _DATE_DMY.findall(cert_text)}
    if len(dates) != 1:
        raise ValueError(f"Expected one calibration date on the certificate; found {sorted(dates) or 'none'}.")
    return dates.pop()


def _find_cal_range(cert_text: str) -> str:
    ranges = {(int(lo), int(hi)) for lo, hi in _RANGE.findall(cert_text) if int(lo) < int(hi)}
    if len(ranges) != 1:
        raise ValueError(f"Expected one calibration range on the certificate; found {sorted(ranges) or 'none'}.")
    low, high = ranges.pop()
    return f'"[{low},{high}]"'
