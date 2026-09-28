"""Tests for the DOFST-K (SBE 43F) parser.

Real fixtures: dofst_4511_cert.pdf (certificate with a vendor adjusted
Soc) and the csv committed to asset-management for it;
dofst_4361_cert.pdf (certificate without an adjusted Soc); and
mmp_qct_4361.txt, an MMP QCT whose 52-MP "dc" output holds the
coefficients for 4361 with a host-adjusted Soc (06-mar-24).

The rule-by-rule tests work on text, so they need no PDF library.
"""
import csv
from pathlib import Path

import pytest

from asset_cal.dofst.parser import DofstParser, parse_texts

FIXTURE_DIR = Path(__file__).parent / "fixtures"
QCT_TEXT = (FIXTURE_DIR / "mmp_qct_4361.txt").read_text(encoding="latin-1")

# Text pdfplumber extracts from dofst_4361_cert.pdf (the coefficient part).
CERT_4361 = (
    "SENSOR SERIAL NUMBER: 4361 SBE 43F OXYGEN CALIBRATION DATA\nwww.seabird.com\n"
    "CALIBRATION DATE: 31-Jan-24\nCOEFFICIENTS: A = -3.6087e-003 NOMINAL DYNAMIC COEFFICIENTS\n"
    "Soc = 3.6592e-004 B = 1.2683e-004 D1 = 1.92634e-4 H1 = -3.300000e-2\n"
    "Foffset = -766.69 C = -2.2744e-006 D2 = -4.64803e-2 H2 = 5.00000e+3\n"
    "Tau20 = 1.11 E nominal = 0.036 H3 = 1.45000e+3\n"
)


def _values(path: Path) -> dict[str, float]:
    return {row["name"]: float(row["value"]) for row in csv.DictReader(path.open())}


def test_vendor_adjusted_certificate_matches_archived_values(tmp_path: Path) -> None:
    pytest.importorskip("pdfplumber")
    parser = DofstParser()
    (tmp_path / "DOFSTK").mkdir()

    output_path = parser.write_csv(parser.parse(FIXTURE_DIR / "dofst_4511_cert.pdf"), tmp_path)

    assert output_path.name == "CGINS-DOFSTK-04511__20240521.csv"
    assert _values(output_path) == _values(FIXTURE_DIR / "CGINS-DOFSTK-04511__20240521.csv")
    assert "vendor adjusted" in output_path.read_text()


def test_real_certificate_and_capture_use_host_adjusted_soc() -> None:
    pytest.importorskip("pdfplumber")
    cal = DofstParser().parse(FIXTURE_DIR / "dofst_4361_cert.pdf", qct_path=FIXTURE_DIR / "mmp_qct_4361.txt")

    assert cal.soc == "3.801300e-04"
    assert "host 2024-03-06" in cal.soc_note


def test_no_adjustment_and_no_capture_uses_estimated_factor() -> None:
    cal = parse_texts(CERT_4361, None, "c.pdf")

    assert cal.soc == "3.7887e-04"
    assert "1.0354 fixed factor" in cal.soc_note


def test_capture_without_host_adjustment_uses_estimated_factor() -> None:
    unadjusted_host = QCT_TEXT.replace("Soc =  3.801300e-04", "Soc =  3.659200e-04")

    cal = parse_texts(CERT_4361, unadjusted_host, "c.pdf")

    assert "1.0354 fixed factor" in cal.soc_note


def test_last_digit_differences_are_not_disagreements() -> None:
    cert = CERT_4361.replace("A = -3.6087e-003", "A = -3.6088e-003")

    assert parse_texts(cert, QCT_TEXT, "c.pdf").a == "-3.6088e-003"


def test_coefficient_disagreement_stops() -> None:
    with pytest.raises(ValueError, match="b: certificate"):
        parse_texts(CERT_4361.replace("B = 1.2683e-004", "B = 1.2783e-004"), QCT_TEXT, "c.pdf")


def test_host_soc_outside_adjustment_range_stops() -> None:
    with pytest.raises(ValueError, match="host-adjustment range"):
        parse_texts(CERT_4361, QCT_TEXT.replace("Soc =  3.801300e-04", "Soc =  4.500000e-04"), "c.pdf")


def test_capture_older_than_certificate_stops() -> None:
    with pytest.raises(ValueError, match="older calibration"):
        parse_texts(CERT_4361, QCT_TEXT.replace("4361: 06-mar-24", "4361: 06-mar-23"), "c.pdf")


def test_capture_for_other_sensor_stops() -> None:
    with pytest.raises(ValueError, match="not the certificate's"):
        parse_texts(CERT_4361, QCT_TEXT.replace("oxygen S/N = 4361", "oxygen S/N = 4511"), "c.pdf")


def test_vendor_adjusted_soc_must_match_host() -> None:
    adjusted = CERT_4361.replace("Soc = 3.6592e-004", "Soc = 3.7000e-004 (adj)")

    with pytest.raises(ValueError, match="certificate adjusted"):
        parse_texts(adjusted, QCT_TEXT, "c.pdf")
