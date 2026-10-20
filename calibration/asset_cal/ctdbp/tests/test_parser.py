"""Tests for the CTDBP parser.

parse() has NO tests here -- it's an unverified port with no real
cap file available, same policy as DOSTA. write_csv() is tested
against a real archived example (calibration/CTDBPC/
CGINS-CTDBPC-07240__20121213.csv), confirmed by hand before writing
this parser. _normalize_caldate and the duplicate-entry handling in
_find_coefficient are tested as self-consistency checks against
what the Matlab source documents, not against real files.
"""
from pathlib import Path

import pytest

from asset_cal.ctdbp.parser import CtdbpCal, CtdbpParser, _find_coefficient, _normalize_caldate

_REAL_COEFFICIENTS = {
    "A0": "0.001236782",
    "A1": "0.000277456",
    "A2": "-1.231E-06",
    "A3": "1.877461E-07",
    "CPCOR": "-9.57E-08",
    "CTCOR": "3.25E-06",
    "G": "-0.9853341",
    "H": "0.1559784",
    "I": "-0.000387642",
    "J": "5.332017E-05",
    "PA0": "0.03994165",
    "PA1": "0.0004914568",
    "PA2": "-5.858501E-12",
    "PTCA0": "524746.7",
    "PTCA1": "10.36083",
    "PTCA2": "-0.3199536",
    "PTCB0": "24.85687",
    "PTCB1": "-0.000625",
    "PTCB2": "0",
    "PTEMPA0": "-64.70695",
    "PTEMPA1": "54.75891",
    "PTEMPA2": "-0.8707395",
}


def test_normalize_caldate_converts_dd_mmm_yy() -> None:
    assert _normalize_caldate("13-dec-12") == "20121213"


def test_find_coefficient_uses_last_occurrence() -> None:
    lines = ["G = -1.0", "some other line", "G = -0.9853341"]
    assert _find_coefficient(lines, "G") == "-0.9853341"


def test_write_csv_matches_archived_output(tmp_path: Path) -> None:
    cal = CtdbpCal(
        serial_number=7240,
        series="C",
        caldate="20121213",
        coefficients=_REAL_COEFFICIENTS,
    )
    (tmp_path / "CTDBPC").mkdir()
    parser = CtdbpParser(series="C")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "CTDBPC" / "CGINS-CTDBPC-07240__20121213.csv"
    assert output_path.read_bytes().decode() == (
        "serial,name,value,notes\n"
        "16-7240,CC_a0,0.001236782,date in filename comes from latest sensor caldate within QCT cap file\n"
        "16-7240,CC_a1,0.000277456,\n"
        "16-7240,CC_a2,-1.231E-06,\n"
        "16-7240,CC_a3,1.877461E-07,\n"
        "16-7240,CC_cpcor,-9.57E-08,\n"
        "16-7240,CC_ctcor,3.25E-06,\n"
        "16-7240,CC_g,-0.9853341,\n"
        "16-7240,CC_h,0.1559784,\n"
        "16-7240,CC_i,-0.000387642,\n"
        "16-7240,CC_j,5.332017E-05,\n"
        "16-7240,CC_pa0,0.03994165,\n"
        "16-7240,CC_pa1,0.0004914568,\n"
        "16-7240,CC_pa2,-5.858501E-12,\n"
        "16-7240,CC_ptca0,524746.7,\n"
        "16-7240,CC_ptca1,10.36083,\n"
        "16-7240,CC_ptca2,-0.3199536,\n"
        "16-7240,CC_ptcb0,24.85687,\n"
        "16-7240,CC_ptcb1,-0.000625,\n"
        "16-7240,CC_ptcb2,0,\n"
        "16-7240,CC_ptempa0,-64.70695,\n"
        "16-7240,CC_ptempa1,54.75891,\n"
        "16-7240,CC_ptempa2,-0.8707395,\n"
    )


def test_write_csv_uses_series_e_folder(tmp_path: Path) -> None:
    cal = CtdbpCal(serial_number=50005, series="E", caldate="20200101", coefficients=_REAL_COEFFICIENTS)
    (tmp_path / "CTDBPE").mkdir()
    parser = CtdbpParser(series="E")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "CTDBPE" / "CGINS-CTDBPE-50005__20200101.csv"


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = CtdbpCal(serial_number=7240, series="C", caldate="20121213", coefficients=_REAL_COEFFICIENTS)
    parser = CtdbpParser(series="C")

    with pytest.raises(FileNotFoundError, match="CTDBPC"):
        parser.write_csv(cal, tmp_path)
