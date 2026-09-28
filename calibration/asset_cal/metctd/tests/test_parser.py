"""Tests for the METCTD parsers.

parse() is tested for both parsers against real files for one
calibration of serial 13471 (QCT capture and vendor .cal). See
parser.py's module docstring.

write_csv is tested against a real archived example
(calibration/METBKA/CGINS-METCTD-10906__20130717.csv) -- the
provenance note here matches the Matlab source exactly, unlike every
other class checked so far, since there's no reordering to disturb
it.

_extract_xml_value and _normalize_metctd_caldate are tested directly
as self-consistency checks of the ported logic.
"""
from pathlib import Path

import pytest

from asset_cal.metctd.parser import (
    MetctdCal,
    MetctdCalParser,
    MetctdCapParser,
    _extract_xml_value,
    _normalize_metctd_caldate,
)

_REAL_COEFFICIENTS = {
    "a0": "-1.030606e-04",
    "a1": "3.059972e-04",
    "a2": "-4.460791e-06",
    "a3": "2.023694e-07",
    "g": "-9.788475e-01",
    "h": "1.364905e-01",
    "i": "-2.269128e-04",
    "j": "3.536941e-05",
    "cpcor": "-9.570000e-08",
    "ctcor": "3.250000e-06",
    "wbotc": "5.593731e-07",
}


def test_normalize_metctd_caldate() -> None:
    assert _normalize_metctd_caldate("17-jul-13") == "20130717"


def test_extract_xml_value() -> None:
    assert _extract_xml_value("<A0>-7.128462e-005</A0>") == "-7.128462e-005"


def test_write_csv_matches_archived_output(tmp_path: Path) -> None:
    cal = MetctdCal(
        serial_number="10906",
        series="CAL",
        caldate="20130717",
        source_provenance="source: QCT 3305-00116-00011",
        coefficients=_REAL_COEFFICIENTS,
    )
    (tmp_path / "METBKA").mkdir()
    parser = MetctdCalParser()

    output_path = parser.write_csv(cal, tmp_path, output_dir_name="METBKA")

    assert output_path == tmp_path / "METBKA" / "CGINS-METCTD-10906__20130717.csv"
    assert output_path.read_text() == (
        "serial,name,value,notes\n"
        "37-10906,CC_a0,-1.030606e-04,source: QCT 3305-00116-00011\n"
        "37-10906,CC_a1,3.059972e-04,\n"
        "37-10906,CC_a2,-4.460791e-06,\n"
        "37-10906,CC_a3,2.023694e-07,\n"
        "37-10906,CC_g,-9.788475e-01,\n"
        "37-10906,CC_h,1.364905e-01,\n"
        "37-10906,CC_i,-2.269128e-04,\n"
        "37-10906,CC_j,3.536941e-05,\n"
        "37-10906,CC_cpcor,-9.570000e-08,\n"
        "37-10906,CC_ctcor,3.250000e-06,\n"
        "37-10906,CC_wbotc,5.593731e-07,\n"
    )


def test_write_csv_no_default_folder_raises(tmp_path: Path) -> None:
    """No override given -- the f"{class_code}{series}" default
    (METCTDCAL) does not exist and never will."""
    cal = MetctdCal(
        serial_number="10906", series="CAL", caldate="20130717", source_provenance="x",
        coefficients=_REAL_COEFFICIENTS,
    )
    parser = MetctdCalParser()

    with pytest.raises(FileNotFoundError, match="METCTDCAL"):
        parser.write_csv(cal, tmp_path)


def test_write_csv_cap_series_also_needs_override(tmp_path: Path) -> None:
    cal = MetctdCal(
        serial_number="10906", series="CAP", caldate="20130717", source_provenance="x",
        coefficients=_REAL_COEFFICIENTS,
    )
    (tmp_path / "METBKA").mkdir()
    parser = MetctdCapParser()

    output_path = parser.write_csv(cal, tmp_path, output_dir_name="METBKA")

    assert output_path == tmp_path / "METBKA" / "CGINS-METCTD-10906__20130717.csv"


FIXTURE_DIR = Path(__file__).parent / "fixtures"
CAPTURE = FIXTURE_DIR / "metctd_capture.cap"  # real QCT capture, SN 13471, cal 04-Jun-26
VENDOR_CAL = FIXTURE_DIR / "metctd_vendor.cal"  # vendor .cal for the same calibration


def test_cap_parse_real_capture() -> None:
    cal = MetctdCapParser().parse(CAPTURE)

    assert cal.serial_number == "13471"
    assert cal.series == "CAP"
    assert cal.caldate == "20260604"
    assert cal.source_provenance == "source: metctd_capture.cap"
    assert cal.coefficients["a0"] == "-1.253292e-04"
    assert cal.coefficients["wbotc"] == "4.336702e-07"


def test_cap_and_cal_sources_agree(tmp_path: Path) -> None:
    """Independent parse paths over two vendor sources for the same
    calibration must produce the same coefficients, as exact strings."""
    cap = MetctdCapParser().parse(CAPTURE)
    cal = MetctdCalParser().parse(VENDOR_CAL)

    assert (cap.serial_number, cap.caldate) == (cal.serial_number, cal.caldate)
    assert cap.coefficients == cal.coefficients


def test_cap_parse_ignores_filename(tmp_path: Path) -> None:
    source = tmp_path / "foogoo.cap"
    source.write_bytes(CAPTURE.read_bytes())

    cal = MetctdCapParser().parse(source)

    assert cal.caldate == "20260604"
    assert cal.source_provenance == "source: foogoo.cap"
