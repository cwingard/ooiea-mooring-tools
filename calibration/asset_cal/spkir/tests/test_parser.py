"""Tests for the SPKIR (Satlantic OCR-507) cal file parser.

Fixtures are real files: spkir_vendor.cal is the Satlantic source
(DI7255L.cal) for the 2024-12-06 calibration of serial 255, and
CGINS-SPKIRB-00255__20241206.csv is the file committed to
asset-management from it by the Matlab script. The source filename
only appears in the provenance note, so the byte-for-byte comparison
runs on a copy under its original name.
"""
from pathlib import Path

import pytest

from asset_cal.spkir.parser import SpkirParser

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SOURCE = FIXTURE_DIR / "spkir_vendor.cal"
ARCHIVED = FIXTURE_DIR / "CGINS-SPKIRB-00255__20241206.csv"


def test_parse_real_cal_file() -> None:
    cal = SpkirParser(series="B").parse(SOURCE)

    assert cal.serial_number == 255
    assert cal.series == "B"
    assert cal.caldate == "20241206"
    assert cal.immersion_factor == ("1.368", "1.410", "1.365", "1.354", "1.372", "1.322", "1.347")
    assert cal.offset[0] == "2147358963.8"
    assert cal.scale[-1] == "2.04144849046e-007"


def test_write_csv_matches_archived_file(tmp_path: Path) -> None:
    parser = SpkirParser(series="B")
    (tmp_path / "SPKIRB").mkdir()
    original_name = tmp_path / "DI7255L.cal"
    original_name.write_bytes(SOURCE.read_bytes())

    output_path = parser.write_csv(parser.parse(original_name), tmp_path)

    assert output_path.name == ARCHIVED.name
    assert output_path.read_bytes() == ARCHIVED.read_bytes()


def test_five_digit_serial_is_not_truncated(tmp_path: Path) -> None:
    source = tmp_path / "DI712345A.cal"
    source.write_text(SOURCE.read_text(encoding="latin-1").replace("SN 0255", "SN 12345"), encoding="latin-1")
    parser = SpkirParser(series="J")
    (tmp_path / "SPKIRJ").mkdir()

    output_path = parser.write_csv(parser.parse(source), tmp_path)

    assert output_path.name == "CGINS-SPKIRJ-12345__20241206.csv"


def test_missing_channel_raises(tmp_path: Path) -> None:
    text = SOURCE.read_text(encoding="latin-1")
    source = tmp_path / "bad.cal"
    source.write_text(text.replace("ED 683.33", "XX 683.33"), encoding="latin-1")

    with pytest.raises(ValueError, match="found 6"):
        SpkirParser(series="B").parse(source)


def test_missing_serial_raises(tmp_path: Path) -> None:
    source = tmp_path / "bad.cal"
    source.write_text(SOURCE.read_text(encoding="latin-1").replace("SN 0255", "XN 0255"), encoding="latin-1")

    with pytest.raises(ValueError, match="SN"):
        SpkirParser(series="B").parse(source)


def test_write_csv_missing_directory_raises(tmp_path: Path) -> None:
    parser = SpkirParser(series="B")

    with pytest.raises(FileNotFoundError, match="SPKIRB"):
        parser.write_csv(parser.parse(SOURCE), tmp_path)
