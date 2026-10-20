"""Tests for the NUTNR parser.

parse() has NO tests here -- unverified, untested port with no real
calfile sample anywhere. See parser.py's module docstring.

write_csv is tested with small synthetic arrays (formatting/ordering
logic only -- the real archived file's arrays are 256 elements
long). The order, formatting and provenance placement were visually
confirmed against calibration/NUTNRB/CGINS-NUTNRB-01056__20170923.csv
before writing this parser.
"""
from pathlib import Path

import pytest

from asset_cal.nutnr.parser import NutnrCal, NutnrParser


def test_write_csv_matches_alphabetical_order_and_formatting(tmp_path: Path) -> None:
    cal = NutnrCal(
        serial_number=1056,
        series="B",
        caldate="20170923",
        cal_temp=19.9,
        wvl=[189.86, 190.66],
        eno3=[0.00043957, 0.00169151],
        eswa=[0.00240772, 0.00106537],
        di=[36.41666667, 41.70833333],
        source_filename="SNA1056C.cal",
    )
    (tmp_path / "NUTNRB").mkdir()
    parser = NutnrParser(series="B")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "NUTNRB" / "CGINS-NUTNRB-01056__20170923.csv"
    assert output_path.read_bytes().decode() == (
        "serial,name,value,notes\n"
        "1056,CC_cal_temp,19.90,date in filename comes from latest caldate within calfile SNA1056C.cal\n"
        '1056,CC_di,"[36.41666667, 41.70833333]",\n'
        '1056,CC_eno3,"[0.00043957, 0.00169151]",\n'
        '1056,CC_eswa,"[0.00240772, 0.00106537]",\n'
        "1056,CC_lower_wavelength_limit_for_spectra_fit,217,\n"
        "1056,CC_upper_wavelength_limit_for_spectra_fit,240,\n"
        '1056,CC_wl,"[189.86, 190.66]",\n'
    )


def test_write_csv_uses_series_j_folder_and_isus_style_filename(tmp_path: Path) -> None:
    cal = NutnrCal(
        serial_number=239,
        series="B",
        caldate="20120920",
        cal_temp=20.0,
        wvl=[190.0],
        eno3=[0.0],
        eswa=[0.0],
        di=[0.0],
        source_filename="ISUS0239A.cal",
    )
    (tmp_path / "NUTNRB").mkdir()
    parser = NutnrParser(series="B")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "NUTNRB" / "CGINS-NUTNRB-00239__20120920.csv"


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = NutnrCal(serial_number=1056, series="J", caldate="20170923", cal_temp=19.9)
    parser = NutnrParser(series="J")

    with pytest.raises(FileNotFoundError, match="NUTNRJ"):
        parser.write_csv(cal, tmp_path)
