"""Calibration parser for the DOFST-K instrument class (Sea-Bird SBE 43F).

Replaces tools/matlab/Endurance_cal_scripts/dofst/write_dofst_cal_to_csv.m,
which read a vendor .cal file that the operator had to hand-edit to add
the adjusted Soc and its date. Here the source is the Sea-Bird
calibration certificate (PDF), read by its standard labels
("SENSOR SERIAL NUMBER:", "CALIBRATION DATE:", "Soc =", "Foffset =",
"A =", "B =", "C =", "E nominal ="); layout does not matter.

The 43F sits on a McLane profiler (CE09OSPM) whose SBE 52-MP stores the
oxygen coefficients. An MMP QCT capture (--qct) that includes the
52-MP "dc" output reports them as "oxygen S/N = <sn>: <date>" followed
by Soc, Foffset, A, B, C and E.

Soc (see calibration/docs/dofst_soc_adjustment.md for the background):

1. The certificate marks Soc "(adj)": Sea-Bird's adjusted Soc is used.
2. No "(adj)", and a QCT capture shows a host adjustment -- the 52-MP
   Soc divided by the certificate Soc is within HOST_ADJUSTMENT_RANGE:
   the Soc loaded on the host is used. A ratio of 1 (no host
   adjustment) falls through to 3; any other ratio outside the range
   stops the run.
3. Otherwise: certificate Soc x ESTIMATED_SOC_FACTOR, noted as an
   estimate.

Whenever a capture is given, it must be for the same oxygen serial,
dated no earlier than the certificate, and agree with the certificate
on Foffset, A, B, C and E (and on Soc when the certificate's Soc is
adjusted), within one unit in the last place of the less precise value
(asset_cal.common.compare). Any disagreement stops the run.

Neither file's name is parsed; the certificate's name is copied into
the CC_frequency_offset note for traceability.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

from asset_cal.common.compare import values_agree
from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

# Russ Desiderio's fit of Sea-Bird adjusted/unadjusted Soc for WFP 43F
# sensors 2496, 2498 and 3535, 2015-2022 (14 calibrations; ratios 1.0099
# to 1.0792, sd 0.017). See calibration/docs/dofst_soc_adjustment.md.
ESTIMATED_SOC_FACTOR = Decimal("1.0354")
# Accepted host-adjusted/unadjusted Soc ratio: the historical 1.0099-1.0792
# with some margin. A ratio of exactly 1 means no host adjustment was made.
HOST_ADJUSTMENT_RANGE = (Decimal("1.000"), Decimal("1.100"))

_NUM = r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
_CERT_FIELDS = {
    "soc": rf"\bSoc\s*=\s*{_NUM}",
    "foffset": rf"\bFoffset\s*=\s*{_NUM}",
    "a": rf"\bA\s*=\s*{_NUM}",
    "b": rf"\bB\s*=\s*{_NUM}",
    "c": rf"\bC\s*=\s*{_NUM}",
    "e": rf"\bE\s+nominal\s*=\s*{_NUM}",
}
_CERT_ADJ = re.compile(rf"\bSoc\s*=\s*{_NUM}\s*\(adj\)", re.IGNORECASE)
_CERT_SERIAL = re.compile(r"SENSOR\s+SERIAL\s+NUMBER:\s*(\d+)", re.IGNORECASE)
_CERT_DATE = re.compile(r"CALIBRATION\s+DATE:\s*(\d{1,2}-[A-Za-z]{3}-\d{2,4})", re.IGNORECASE)
_QCT_HEADER = re.compile(r"oxygen\s+S/N\s*=\s*(\d+)\s*:\s*(\d{1,2}-[A-Za-z]{3}-\d{2,4})", re.IGNORECASE)
_QCT_FIELD = re.compile(rf"^\s*(Soc|Foffset|A|B|C|E)\s*=\s*{_NUM}\s*$")
_QCT_KEYS = {"Soc": "soc", "Foffset": "foffset", "A": "a", "B": "b", "C": "c", "E": "e"}


@dataclass(frozen=True)
class DofstCal:
    """Calibration coefficients for one SBE 43F calibration.

    Attributes
    ----------
    serial_number : int
        43F serial number.
    series : str
        Always "K".
    caldate : str
        Certificate calibration date, YYYYMMDD.
    soc, foffset, a, b, c, e : str
        Coefficients as written to the csv.
    soc_note : str
        How Soc was determined (vendor adjusted, host adjusted, or
        estimated).
    source_filename : str
        Certificate file name, for the provenance note.
    """

    serial_number: int
    series: str
    caldate: str
    soc: str
    foffset: str
    a: str
    b: str
    c: str
    e: str
    soc_note: str
    source_filename: str


class DofstParser(SeriesParser[DofstCal]):
    """Parses an SBE 43F certificate, optionally checked against an MMP QCT."""

    class_code: ClassVar[str] = "DOFST"
    series: ClassVar[str] = "K"
    accepts_qct: ClassVar[bool] = True

    def parse(self, source_path: Path, qct_path: Path | None = None) -> DofstCal:
        """Parse a 43F calibration certificate (PDF).

        Parameters
        ----------
        source_path : Path
            Sea-Bird SBE 43F calibration certificate.
        qct_path : Path | None
            MMP QCT capture containing the 52-MP "dc" output.

        Raises
        ------
        ValueError
            If a field is missing or ambiguous, or the capture
            disagrees with the certificate.
        """
        from asset_cal.pco2w.parser import _read_pdf_text

        cert_text = _read_pdf_text(source_path)
        capture_text = None if qct_path is None else qct_path.read_text(encoding="latin-1")
        return parse_texts(cert_text, capture_text, source_path.name)

    def write_csv(
        self, cal: DofstCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a DOFST-K calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/DOFSTK does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; DOFST calibration csvs "
                "are never written into a directory this script creates itself."
            )
        filename = f"CGINS-{self.class_code}{self.series}-{cal.serial_number:05d}__{cal.caldate}.csv"
        coefficients = [
            CalCoefficient("CC_frequency_offset", cal.foffset, f"coeffs from {cal.source_filename}"),
            CalCoefficient("CC_oxygen_signal_slope", cal.soc, cal.soc_note),
            CalCoefficient("CC_residual_temperature_correction_factor_a", cal.a),
            CalCoefficient("CC_residual_temperature_correction_factor_b", cal.b),
            CalCoefficient("CC_residual_temperature_correction_factor_c", cal.c),
            CalCoefficient("CC_residual_temperature_correction_factor_e", cal.e),
        ]
        return write_cal_csv(output_dir / filename, f"43-{cal.serial_number}", coefficients)


def parse_texts(cert_text: str, capture_text: str | None, source_filename: str) -> DofstCal:
    """Build a DofstCal from certificate text and optional MMP QCT text.

    Split from DofstParser.parse so it can be tested without a PDF.

    Raises
    ------
    ValueError
        If a field is missing or ambiguous, or the capture disagrees
        with the certificate.
    """
    serial = int(_one(_CERT_SERIAL.findall(cert_text), "certificate serial number"))
    cert_date = _parse_date(_one(_CERT_DATE.findall(cert_text), "certificate calibration date"))
    cert = {name: _one(re.findall(pattern, cert_text), f"certificate {name}") for name, pattern in _CERT_FIELDS.items()}
    vendor_adjusted = _CERT_ADJ.search(cert_text) is not None

    host = None if capture_text is None else _parse_capture(capture_text, serial)
    if host is not None:
        host_date, host_values = host
        if host_date < cert_date:
            raise ValueError(
                f"QCT oxygen calibration date {host_date:%Y-%m-%d} is earlier than the certificate's "
                f"{cert_date:%Y-%m-%d}: the capture is from an older calibration."
            )
        for name in ("foffset", "a", "b", "c", "e"):
            if not values_agree(cert[name], host_values[name]):
                raise ValueError(f"{name}: certificate {cert[name]} does not match the 52-MP's {host_values[name]}.")

    if vendor_adjusted:
        if host is not None and not values_agree(cert["soc"], host[1]["soc"]):
            raise ValueError(f"Soc: certificate adjusted {cert['soc']} does not match the 52-MP's {host[1]['soc']}.")
        soc, note = cert["soc"], "vendor adjusted Soc (O2 signal slope)"
    else:
        soc, note = _unadjusted_soc(cert["soc"], host)

    return DofstCal(
        serial_number=serial,
        series="K",
        caldate=f"{cert_date:%Y%m%d}",
        soc=soc,
        foffset=cert["foffset"],
        a=cert["a"],
        b=cert["b"],
        c=cert["c"],
        e=cert["e"],
        soc_note=note,
        source_filename=source_filename,
    )


def _unadjusted_soc(cert_soc: str, host: tuple[datetime, dict[str, str]] | None) -> tuple[str, str]:
    """Soc and note when the certificate's Soc is not vendor adjusted."""
    if host is not None and not values_agree(cert_soc, host[1]["soc"]):
        host_date, host_values = host
        ratio = Decimal(host_values["soc"]) / Decimal(cert_soc)
        low, high = HOST_ADJUSTMENT_RANGE
        if not low < ratio <= high:
            raise ValueError(
                f"Soc: the 52-MP's {host_values['soc']} is {ratio:.4f} x the certificate's {cert_soc}, outside the "
                f"expected host-adjustment range {low}-{high}."
            )
        return host_values["soc"], (
            f"adjusted Soc as loaded on host {host_date:%Y-%m-%d} (from QCT; {ratio:.4f} x certificate Soc)"
        )
    estimate = Decimal(cert_soc) * ESTIMATED_SOC_FACTOR
    note = f"estimated adjusted Soc: certificate Soc {cert_soc} x {ESTIMATED_SOC_FACTOR} fixed factor"
    return f"{float(estimate):.4e}", note


def _parse_capture(text: str, serial: int) -> tuple[datetime, dict[str, str]]:
    """Return (date, coefficients) from the 52-MP 'dc' oxygen block(s)."""
    lines = text.splitlines()
    blocks = []
    for i, line in enumerate(lines):
        header = _QCT_HEADER.search(line)
        if not header:
            continue
        values: dict[str, str] = {}
        for follow in lines[i + 1:i + 8]:
            field = _QCT_FIELD.match(follow)
            if not field:
                break
            values[_QCT_KEYS[field.group(1)]] = field.group(2)
        blocks.append((int(header.group(1)), _parse_date(header.group(2)), values))
    if not blocks:
        raise ValueError("QCT capture has no 52-MP 'oxygen S/N = ...' coefficient block.")
    distinct = {(sn, date, tuple(sorted(v.items()))) for sn, date, v in blocks}
    if len(distinct) != 1:
        raise ValueError("QCT capture has more than one differing oxygen coefficient block.")
    sn, date, values = blocks[0]
    if sn != serial:
        raise ValueError(f"QCT capture is for oxygen sensor {sn}, not the certificate's {serial}.")
    missing = [k for k in _QCT_KEYS.values() if k not in values]
    if missing:
        raise ValueError(f"QCT oxygen coefficient block is missing {missing}.")
    return date, values


def _parse_date(text: str) -> datetime:
    for fmt in ("%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {text!r}")


def _one(matches: list[str], what: str) -> str:
    distinct = set(matches)
    if len(distinct) != 1:
        raise ValueError(f"Expected one {what}; found {sorted(distinct) or 'none'}.")
    return distinct.pop()
