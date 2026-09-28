"""Tests for the PHSEN QCT parser.

phsen_qct_sample.txt is the QCT sample embedded verbatim in the Matlab
source's header comment (Name: P0088, Cal1-4: 18217/2216/13/40587).
phsen_qct_capture.txt is a real QCT capture (P0122) checked against AM.
"""
from pathlib import Path

import pytest

from asset_cal.phsen.parser import PhsenCal, PhsenParser

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "phsen_qct_sample.txt"
CALDATE = "20180629"

parser = PhsenParser()


def test_parse_returns_expected_coefficients() -> None:
    cal = parser.parse(FIXTURE_PATH, caldate=CALDATE)

    assert cal == PhsenCal(
        serial_number="P0088",
        series="D",
        caldate="20180629",
        ea434="18217",
        eb434="2216",
        ea578="13",
        eb578="40587",
    )


def test_parse_missing_samiinfo_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "anything.txt"
    bad_file.write_text("File created: x\nSAMI Client Version: 1.3.1\n")

    with pytest.raises(ValueError, match="SAMIinfo"):
        parser.parse(bad_file, caldate=CALDATE)


def test_parse_missing_name_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "anything.txt"
    bad_file.write_text(":SAMIinfo\nCal1: 1\nCal2: 2\nCal3: 3\nCal4: 4\n")

    with pytest.raises(ValueError, match="Name"):
        parser.parse(bad_file, caldate=CALDATE)


def test_write_csv_matches_current_script_format(tmp_path: Path) -> None:
    cal = parser.parse(FIXTURE_PATH, caldate=CALDATE)
    (tmp_path / "PHSEND").mkdir()

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "PHSEND" / "CGINS-PHSEND-P0088__20180629.csv"
    # The real archive uses "Constant" as the CC_psal note, not the
    # current script's "DELETE: use salinity from co-located
    # CTDBP" -- confirmed drift, same category as PARAD-J's CC_Im
    # provenance note and DOSTA's CC_conc_coef note. This test
    # asserts current script behavior, not the archived files.
    assert output_path.read_text() == (
        "serial,name,value,notes\n"
        "P0088,CC_ea434,18217,\n"
        "P0088,CC_eb434,2216,\n"
        "P0088,CC_ea578,13,\n"
        "P0088,CC_eb578,40587,\n"
        "P0088,CC_ind_off,0,\n"
        "P0088,CC_ind_slp,1,\n"
        "P0088,CC_psal,35,DELETE: use salinity from co-located CTDBP\n"
        "P0088,CC_sami_bits,12,\n"
    )


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = parser.parse(FIXTURE_PATH, caldate=CALDATE)

    with pytest.raises(FileNotFoundError, match="PHSEND"):
        parser.write_csv(cal, tmp_path)


def test_parse_requires_caldate() -> None:
    with pytest.raises(ValueError, match="--caldate"):
        parser.parse(FIXTURE_PATH)


def test_parse_rejects_invalid_caldate() -> None:
    with pytest.raises(ValueError, match="YYYYMMDD"):
        parser.parse(FIXTURE_PATH, caldate="20181331")


REAL_CAPTURE = FIXTURE_DIR / "phsen_qct_capture.txt"  # real QCT capture, P0122, 2024-12-23


def test_real_capture_matches_archived_values() -> None:
    """Values from the committed CGINS-PHSEND-P0122__20241210.csv, which was
    generated from the vendor certificate (written there as 19168.0 etc.)."""
    cal = parser.parse(REAL_CAPTURE, caldate="20241210")

    assert cal.serial_number == "P0122"
    assert [float(v) for v in (cal.ea434, cal.eb434, cal.ea578, cal.eb578)] == [19168.0, 2546.0, 111.0, 41962.0]
