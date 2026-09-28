"""Tests for the FLORT dev file parser.

The fixture is the dev file sample embedded verbatim in the Matlab
source's header comment (BBFL2W-1030, Created on 12/06/16,
Lambda=4/Chl=6/CDOM=8 rows). No real vendor dev file exists in the
repo yet.
"""
from dataclasses import replace
from pathlib import Path

import pytest

from asset_cal.flort.parser import FlortCal, FlortParser

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "flort_dev_sample.dev"


def test_parse_returns_expected_coefficients() -> None:
    parser = FlortParser(series="J")
    cal = parser.parse(FIXTURE_PATH)

    assert cal == FlortCal(
        serial_number=1030,
        series="J",
        caldate="20161206",
        dark_counts_cdom="47",
        scale_factor_cdom="0.0650",
        dark_counts_chlorophyll_a="47",
        scale_factor_chlorophyll_a="0.0116",
        dark_counts_volume_scatter="48",
        scale_factor_volume_scatter="3.437E-06",
    )


def test_parse_missing_serial_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.DEV"
    bad_file.write_text("Created on: 12/06/16\nLambda=4\t1\t2\t700\t700\n")

    with pytest.raises(ValueError, match="BBFL2-"):
        FlortParser(series="D").parse(bad_file)


def test_parse_missing_channel_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.DEV"
    bad_file.write_text("ECO BBFL2-1030\nCreated on: 12/06/16\n")

    with pytest.raises(ValueError, match="lambda"):
        FlortParser(series="D").parse(bad_file)


def test_write_csv_series_j_row_order_and_notes(tmp_path: Path) -> None:
    parser = FlortParser(series="J")
    cal = parser.parse(FIXTURE_PATH)
    (tmp_path / "FLORTJ").mkdir()

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "FLORTJ" / "CGINS-FLORTJ-01030__20161206.csv"
    assert output_path.read_text() == (
        "serial,name,value,notes\n"
        "1030,CC_dark_counts_cdom,47,date in filename comes from dev file\n"
        "1030,CC_scale_factor_cdom,0.0650,\n"
        "1030,CC_dark_counts_chlorophyll_a,47,\n"
        "1030,CC_scale_factor_chlorophyll_a,0.0116,\n"
        "1030,CC_dark_counts_volume_scatter,48,\n"
        "1030,CC_scale_factor_volume_scatter,3.437E-06,\n"
        "1030,CC_depolarization_ratio,0.039,Constant\n"
        "1030,CC_measurement_wavelength,700,[nm]; Constant\n"
        "1030,CC_scattering_angle,124,[degrees]; Constant\n"
        "1030,CC_angular_resolution,1.076,"
        "Erroneously named constant; this coefficient scales the particulate "
        "scattering at 124 degrees to total backscatter from particles\n"
    )


def test_write_csv_series_d_uses_plain_serial(tmp_path: Path) -> None:
    parser = FlortParser(series="D")
    cal = replace(parser.parse(FIXTURE_PATH), series="D")
    (tmp_path / "FLORTD").mkdir()

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "FLORTD" / "CGINS-FLORTD-01030__20161206.csv"
    first_line = output_path.read_text().splitlines()[1]
    assert first_line.startswith("1030,")  # bare serial for every series


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    parser = FlortParser(series="K")
    cal = parser.parse(FIXTURE_PATH)

    with pytest.raises(FileNotFoundError, match="FLORTK"):
        parser.write_csv(cal, tmp_path)


def test_parse_non_numeric_coefficient_raises(tmp_path: Path) -> None:
    """A dev file exported from a broken spreadsheet (seen: '#REF!')."""
    bad_file = tmp_path / "bad.dev"
    bad_file.write_text(FIXTURE_PATH.read_text().replace("3.437E-06", "#REF!"))

    with pytest.raises(ValueError, match="non-numeric coefficient '#REF!'"):
        FlortParser(series="D").parse(bad_file)
