"""Tests for the PARAD-J dev file parser."""
from pathlib import Path

import pytest

from asset_cal.parad.parser import ParadJCal, ParadJParser

FIXTURE_DIR = Path(__file__).parent / "fixtures"

parser = ParadJParser()


def test_parse_returns_expected_coefficients() -> None:
    cal = parser.parse(FIXTURE_DIR / "parad_dev_sample.dev")

    assert cal == ParadJCal(
        serial_number=505,
        series="J",
        caldate="20161108",
        im="1.3589",
        a0="4431",
        a1="2890",
    )


def test_parse_missing_serial_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "no_serial.dev"
    bad_file.write_text("Created on:\t11/08/16\nim=\t1.3589\n")

    with pytest.raises(ValueError, match="serial"):
        parser.parse(bad_file)


def test_parse_missing_coefficient_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "no_im.dev"
    bad_file.write_text("ECO\tPARS-505\nCreated on:\t11/08/16\n")

    with pytest.raises(ValueError, match="im="):
        parser.parse(bad_file)


def test_write_csv_matches_archived_output(tmp_path: Path) -> None:
    cal = parser.parse(FIXTURE_DIR / "parad_dev_sample.dev")
    (tmp_path / "PARADJ").mkdir()

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "PARADJ" / "CGINS-PARADJ-00505__20161108.csv"
    # This is the exact content of the real, already-archived
    # calibration/PARADJ/CGINS-PARADJ-00505__20161108.csv, except
    # that file's CC_Im row has an empty notes field -- an older
    # version of the Matlab script did not yet add the caldate
    # provenance note. Flagged for Chris; this test asserts current
    # (provenance-included) Matlab behavior, not the archived file.
    assert output_path.read_text() == (
        "serial,name,value,notes\n"
        "505,CC_Im,1.3589,date in filename comes from factory devfile\n"
        "505,CC_a0,4431,digital\n"
        "505,CC_a1,2890,digital\n"
    )


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = parser.parse(FIXTURE_DIR / "parad_dev_sample.dev")

    with pytest.raises(FileNotFoundError, match="PARADJ"):
        parser.write_csv(cal, tmp_path)
