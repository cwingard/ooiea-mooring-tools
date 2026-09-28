"""Tests for the PRESF parser.

parse() has NO tests here -- unverified port, no real cap file
available (and unlike FLORT/PARAD-J/PHSEN-D, no sample embedded in
the Matlab source either). write_csv() is tested against a real
archived example (calibration/PRESFA/
CGINS-PRESFA-01328__20120330.csv). _parse_presf_date is tested
against the three formats the Matlab source's own comment documents.
"""
from pathlib import Path

import pytest

from asset_cal.presf.parser import PresfCal, PresfParser, _parse_presf_date

_REAL_COEFFICIENTS = {
    "c1": "607.2786",
    "c2": "-6.532171",
    "c3": "-1024.374",
    "d1": "0.02928",
    "d2": "0",
    "pressure_offset_calibration_coefficient": "-0.1172",
    "t1": "27.83369",
    "t2": "0.607202",
    "t3": "18.21885",
    "t4": "27.90597",
    "u0": "5.827194",
    "y1": "-3910.859",
    "y2": "-10708.25",
    "y3": "0",
    "b": "8388.6",
    "m": "125829.1",
}


@pytest.mark.parametrize(
    "date_str",
    ["9-nov-16", "09-nov-2016", "11-09-2016"],
)
def test_parse_presf_date_handles_all_three_formats(date_str: str) -> None:
    assert _parse_presf_date(date_str) == "20161109"


def test_write_csv_matches_archived_output(tmp_path: Path) -> None:
    cal = PresfCal(
        serial_number=1328,
        series="A",
        caldate="20120330",
        coefficients=_REAL_COEFFICIENTS,
    )
    (tmp_path / "PRESFA").mkdir()
    parser = PresfParser(series="A")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "PRESFA" / "CGINS-PRESFA-01328__20120330.csv"
    assert output_path.read_text() == (
        "serial,name,value,notes\n"
        "26P-1328,CC_b,8388.6,date in filename comes from latest sensor caldate "
        "read from file captured from relevant QCT\n"
        "26P-1328,CC_c1,607.2786,\n"
        "26P-1328,CC_c2,-6.532171,\n"
        "26P-1328,CC_c3,-1024.374,\n"
        "26P-1328,CC_d1,0.02928,\n"
        "26P-1328,CC_d2,0,\n"
        "26P-1328,CC_m,125829.1,\n"
        "26P-1328,CC_offset_correction_factor,0,\n"
        "26P-1328,CC_pressure_offset_calibration_coefficient,-0.1172,\n"
        "26P-1328,CC_slope_correction_factor,1,\n"
        "26P-1328,CC_t1,27.83369,\n"
        "26P-1328,CC_t2,0.607202,\n"
        "26P-1328,CC_t3,18.21885,\n"
        "26P-1328,CC_t4,27.90597,\n"
        "26P-1328,CC_u0,5.827194,\n"
        "26P-1328,CC_y1,-3910.859,\n"
        "26P-1328,CC_y2,-10708.25,\n"
        "26P-1328,CC_y3,0,\n"
    )


def test_write_csv_uses_series_b_folder(tmp_path: Path) -> None:
    cal = PresfCal(serial_number=1384, series="B", caldate="20140227", coefficients=_REAL_COEFFICIENTS)
    (tmp_path / "PRESFB").mkdir()
    parser = PresfParser(series="B")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "PRESFB" / "CGINS-PRESFB-01384__20140227.csv"


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = PresfCal(serial_number=1328, series="A", caldate="20120330", coefficients=_REAL_COEFFICIENTS)
    parser = PresfParser(series="A")

    with pytest.raises(FileNotFoundError, match="PRESFA"):
        parser.write_csv(cal, tmp_path)
