"""Tests for the DOSTA parser.

write_csv() is tested directly against manually-constructed DostaCal
records -- its output format is fixed by the archived calibration/
DOSTAD and DOSTAJ csv files and does not depend on QCT parsing.

parse() has NO tests here. It's an unverified direct port of the
Matlab textscan logic with no real QCT file available to confirm
token positions against -- see the parser.py module docstring. Add
parse() tests once a real QCT (or QCT + cal cert pair) is available.

The calibration date is operator-supplied (parse(..., caldate=...));
the QCT filename is never parsed.
"""
from pathlib import Path

import pytest

from asset_cal.dosta.parser import DostaCal, DostaParser


def test_write_csv_formats_conc_coef_and_svu(tmp_path: Path) -> None:
    cal = DostaCal(
        serial_number=211,
        series="D",
        caldate="20130704",
        conc_coef_offset="0.0",
        conc_coef_slope="1.0",
        svu_coefficients=[
            "0.00315218",
            "0.000133734",
            "2.61979e-06",
            "230.297",
            "-0.343226",
            "-58.5185",
            "4.55436",
        ],
    )
    (tmp_path / "DOSTAD").mkdir()
    parser = DostaParser(series="D")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "DOSTAD" / "CGINS-DOSTAD-00211__20130704.csv"
    assert output_path.read_bytes().decode() == (
        "serial,name,value,notes\n"
        '211,CC_conc_coef,"[0.0, 1.0]",date in filename comes from factory calibration certificate\n'
        '211,CC_csv,"[0.00315218, 0.000133734, 2.61979e-06, 230.297, -0.343226, -58.5185, 4.55436]",\n'
    )


def test_write_csv_uses_series_j_folder(tmp_path: Path) -> None:
    cal = DostaCal(
        serial_number=209,
        series="J",
        caldate="20130704",
        conc_coef_offset="0.0",
        conc_coef_slope="1.0",
        svu_coefficients=["1"] * 7,
    )
    (tmp_path / "DOSTAJ").mkdir()
    parser = DostaParser(series="J")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "DOSTAJ" / "CGINS-DOSTAJ-00209__20130704.csv"


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = DostaCal(
        serial_number=1,
        series="D",
        caldate="20200101",
        conc_coef_offset="0",
        conc_coef_slope="1",
        svu_coefficients=["1"] * 7,
    )
    parser = DostaParser(series="D")

    with pytest.raises(FileNotFoundError, match="DOSTAD"):
        parser.write_csv(cal, tmp_path)


def test_parse_requires_caldate(tmp_path: Path) -> None:
    """The caldate check runs before any QCT parsing, so an empty file
    is enough to prove the filename is never consulted for it."""
    source = tmp_path / "3305-00115-00385_SN_220_20211102.log"
    source.write_text("")

    with pytest.raises(ValueError, match="--caldate"):
        DostaParser(series="D").parse(source)
