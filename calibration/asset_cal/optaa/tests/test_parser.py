"""Tests for the OPTAA parser.

parse() and write_csv() are tested end to end against a real devfile
(fixtures/optaa_dev.dev, ACS-135) and the three files committed to
asset-management from it.

_write_csvwrite_style is also tested against a real row from
calibration/OPTAAD/CGINS-OPTAAD-00123__20121128__CC_taarray.ext. That
2012 file writes zero as "0.0"; the 2024 files write "0", which is
what this port reproduces. Numerically identical either way.

write_csv's formatting is also checked with small synthetic arrays.
"""
from pathlib import Path

import pytest

from asset_cal.optaa.parser import OptaaCal, OptaaParser, _write_csvwrite_style

# Verbatim first row of the real archived taarray file.
_REAL_TAARRAY_ROW_TEXT = (
    "-0.013738,-0.012053,-0.01177,-0.010794,-0.009626,-0.008598,-0.008327,-0.007632,-0.00677,-0.007042,"
    "-0.005665,-0.005216,-0.004008,-0.003388,-0.001985,-0.001683,-0.002571,-0.002286,-0.001833,-0.001696,"
    "-0.001387,-0.000762,0.0,0.00031,0.000488,0.000615,-0.000117,-0.000654,-0.001597,-0.001348,-0.002696,"
    "-0.004246,-0.006645,-0.008348,-0.008676"
)


def test_write_csvwrite_style_reproduces_real_archived_row(tmp_path: Path) -> None:
    real_values = [float(v) for v in _REAL_TAARRAY_ROW_TEXT.split(",")]
    out_path = tmp_path / "out.ext"

    _write_csvwrite_style(out_path, [real_values])

    assert out_path.read_text() == _REAL_TAARRAY_ROW_TEXT.replace(",0.0,", ",0,") + "\n"


def test_write_csv_formatting(tmp_path: Path) -> None:
    cal = OptaaCal(
        serial_number=123,
        series="D",
        caldate="20121128",
        cwvl=[400.1, 404.3],
        coff=[0.449779, 0.538688],
        awvl=[401.0, 405.1],
        aoff=[-0.465231, -0.274376],
        tcal=19.0,
        tbin=[3.684881, 4.425816],
        ctbin=[[1.0, 2.0], [3.0, 4.0]],
        atbin=[[5.0, 6.0], [7.0, 8.0]],
    )
    (tmp_path / "OPTAAD").mkdir()
    parser = OptaaParser(series="D")

    output_path = parser.write_csv(cal, tmp_path)

    assert output_path == tmp_path / "OPTAAD" / "CGINS-OPTAAD-00123__20121128.csv"
    assert output_path.read_text() == (
        "serial,name,value,notes\n"
        'ACS-123,CC_acwo,"[-0.465231, -0.274376]",\n'
        'ACS-123,CC_awlngth,"[401.0, 405.1]",\n'
        'ACS-123,CC_ccwo,"[0.449779, 0.538688]",\n'
        'ACS-123,CC_cwlngth,"[400.1, 404.3]",\n'
        "ACS-123,CC_taarray,SheetRef:CC_taarray,\n"
        'ACS-123,CC_tbins,"[3.684881, 4.425816]",\n'
        "ACS-123,CC_tcal,19.0,date in filename comes from 'offsets saved' date within factory devfile\n"
        "ACS-123,CC_tcarray,SheetRef:CC_tcarray,\n"
    )

    taarray_path = tmp_path / "OPTAAD" / "CGINS-OPTAAD-00123__20121128__CC_taarray.ext"
    tcarray_path = tmp_path / "OPTAAD" / "CGINS-OPTAAD-00123__20121128__CC_tcarray.ext"
    assert taarray_path.read_text() == "5,6\n7,8\n"
    assert tcarray_path.read_text() == "1,2\n3,4\n"


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    cal = OptaaCal(serial_number=123, series="D", caldate="20121128")
    parser = OptaaParser(series="D")

    with pytest.raises(FileNotFoundError, match="OPTAAD"):
        parser.write_csv(cal, tmp_path)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
REAL_DEV = FIXTURE_DIR / "optaa_dev.dev"  # WET Labs devfile, ACS-135, offsets saved 2/8/2024
ARCHIVED = "CGINS-OPTAAD-00135__20240208"  # committed to asset-management from REAL_DEV


def test_real_devfile_matches_archived_files(tmp_path: Path) -> None:
    parser = OptaaParser(series="D")
    (tmp_path / "OPTAAD").mkdir()

    output_path = parser.write_csv(parser.parse(REAL_DEV), tmp_path)

    assert output_path.name == f"{ARCHIVED}.csv"
    # Row order differs from the committed file and does not matter to CI.
    written = sorted(output_path.read_text().splitlines())
    assert written == sorted((FIXTURE_DIR / f"{ARCHIVED}.csv").read_text().splitlines())
    for suffix in ("__CC_taarray.ext", "__CC_tcarray.ext"):
        assert (tmp_path / "OPTAAD" / f"{ARCHIVED}{suffix}").read_text() == (
            FIXTURE_DIR / f"{ARCHIVED}{suffix}"
        ).read_text()


def test_devfile_without_temperature_bins_stops(tmp_path: Path) -> None:
    """Seen in a 2026 ACS-344 devfile: '0 ; number of temperature bins'."""
    lines = REAL_DEV.read_text().splitlines()
    lines[8] = "0\t\t\t; number of temperature bins"
    bad = tmp_path / "no_tbins.dev"
    bad.write_text("\n".join(lines) + "\n")

    with pytest.raises(ValueError, match="no temperature-correction table"):
        OptaaParser(series="D").parse(bad)
