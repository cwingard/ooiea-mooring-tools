"""Tests for the PCO2W certificate + QCT capture parser.

Fixtures are real files for one calibration of C0062:
pco2w_cert.pdf (the Sunburst certificate, originally
C0062_110225_CalCert.pdf), pco2w_qct_capture.txt (the QCT capture)
and CGINS-PCO2WB-C0062__20250211.csv (committed to asset-management
from the certificate by the Matlab script).

The layout-independence tests work on the certificate's extracted
text, rearranged, so they need no PDF library.
"""
from pathlib import Path

import pytest

from asset_cal.pco2w.parser import Pco2wParser, parse_texts

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CERT = FIXTURE_DIR / "pco2w_cert.pdf"
CAPTURE = FIXTURE_DIR / "pco2w_qct_capture.txt"
ARCHIVED = FIXTURE_DIR / "CGINS-PCO2WB-C0062__20250211.csv"
CAPTURE_TEXT = CAPTURE.read_text(encoding="latin-1")

# Text pdfplumber extracts from pco2w_cert.pdf (header and blank-intensity
# table included, since they are what a matcher has to ignore).
CERT_TEXT = (
    "Sunburst Sensors, LLC\n1226 W Broadway Ave\nMissoula, MT 59802\n+1 406 532 3247\n"
    "SAMI2 CO Calibration Certificate February 11, 2025\n2\nSerial Number: C0062\n"
    "Board Version: E Board\nTechnician: BW\nReagent: 606\nReagent Remaining: 65%\n"
    "Table 1: SAMI2 CO calibration parameters.\n2\nA B C K K T Range (ppm)\n434 620 avg\n"
    "0.0636 0.5328 -1.4839 1.0248 1.1558 8.9474 201\u20131996\n"
    "Table 2: Blank intensities.\nSource Reference Signal\nDark 45 34\n434 nm 3083 3149\n"
    "620 nm 2691 3094\nBuild Notes\nPressure Test: 200 psi\nPage 1 / 2\nPage 2 / 2"
)


def test_real_files_reproduce_archived_csv(tmp_path: Path) -> None:
    pytest.importorskip("pdfplumber")
    cert = tmp_path / "C0062_110225_CalCert.pdf"  # the name recorded in the archived note
    cert.write_bytes(CERT.read_bytes())
    (tmp_path / "PCO2WB").mkdir()
    parser = Pco2wParser()

    output_path = parser.write_csv(parser.parse(cert, qct_path=CAPTURE), tmp_path)

    assert output_path.name == ARCHIVED.name
    assert output_path.read_bytes().decode() == ARCHIVED.read_bytes().decode()


def test_tavg_comes_from_certificate_not_sensor() -> None:
    cal = parse_texts(CERT_TEXT, CAPTURE_TEXT, "cert.pdf")

    assert cal.calt == "8.9474"  # the sensor holds 8.95


def test_layout_changes_do_not_matter() -> None:
    reordered = (
        "Calibration date: 11 February 2025\nSerial Number: C62\n"
        "Range (ppm): 201 - 1996\nTavg 8.9474\nK620 1.1558\nC -1.4839\nK434 1.0248\nB 0.5328\nA 0.0636\n"
    )

    cal = parse_texts(reordered, CAPTURE_TEXT, "cert.pdf")

    assert (cal.cala, cal.calb, cal.calc, cal.calt) == ("0.0636", "0.5328", "-1.4839", "8.9474")
    assert (cal.serial_number, cal.caldate, cal.cal_range) == ("C0062", "20250211", '"[201,1996]"')


def test_sami_serial_falls_back_to_capture() -> None:
    cal = parse_texts(CERT_TEXT.replace("Serial Number: C0062", "Serial Number: SAMI"), CAPTURE_TEXT, "c.pdf")

    assert cal.serial_number == "C0062"


def test_coefficient_disagreement_stops() -> None:
    with pytest.raises(ValueError, match="cala: no certificate value matches"):
        parse_texts(CERT_TEXT.replace("0.0636", "0.0641"), CAPTURE_TEXT, "c.pdf")


def test_serial_disagreement_stops() -> None:
    with pytest.raises(ValueError, match="does not match QCT capture serial"):
        parse_texts(CERT_TEXT.replace("Serial Number: C0062", "Serial Number: C0053"), CAPTURE_TEXT, "c.pdf")


def test_two_ranges_stop() -> None:
    with pytest.raises(ValueError, match="one calibration range"):
        parse_texts(CERT_TEXT + "\nRange (ppm) 200-2000", CAPTURE_TEXT, "c.pdf")


def test_two_dates_stop() -> None:
    with pytest.raises(ValueError, match="one calibration date"):
        parse_texts(CERT_TEXT + "\nIssued March 3, 2025", CAPTURE_TEXT, "c.pdf")


def test_capture_without_samiinfo_stops() -> None:
    with pytest.raises(ValueError, match="SAMIinfo"):
        parse_texts(CERT_TEXT, "File created: x\n", "c.pdf")


def test_certificate_only_reproduces_archived_csv(tmp_path: Path) -> None:
    pytest.importorskip("pdfplumber")
    cert = tmp_path / "C0062_110225_CalCert.pdf"
    cert.write_bytes(CERT.read_bytes())
    (tmp_path / "PCO2WB").mkdir()
    parser = Pco2wParser()

    output_path = parser.write_csv(parser.parse(cert), tmp_path)

    assert output_path.read_bytes().decode() == ARCHIVED.read_bytes().decode()


def test_certificate_only_and_with_capture_agree() -> None:
    assert parse_texts(CERT_TEXT, None, "c.pdf") == parse_texts(CERT_TEXT, CAPTURE_TEXT, "c.pdf")


def test_certificate_only_unrecognized_layout_asks_for_capture() -> None:
    reordered = CERT_TEXT.replace("A B C K K T Range (ppm)", "Tavg A B C K434 K620 Range (ppm)")

    with pytest.raises(ValueError, match="--qct"):
        parse_texts(reordered, None, "c.pdf")


def test_certificate_only_sami_serial_asks_for_capture() -> None:
    with pytest.raises(ValueError, match="--qct"):
        parse_texts(CERT_TEXT.replace("Serial Number: C0062", "Serial Number: SAMI"), None, "c.pdf")


def test_unmapped_dash_glyph_in_range() -> None:
    """pdfplumber output for the 2023-12-27 C0062 certificate."""
    cal = parse_texts(CERT_TEXT.replace("201\u20131996", "201(cid:21)1996"), CAPTURE_TEXT, "c.pdf")

    assert cal.cal_range == '"[201,1996]"'
