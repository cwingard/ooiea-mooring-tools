"""Tests for asset_cal.dosta.two_point.

The fixture tables are pdfplumber's extract_tables() output for
DOSTA-D_SN315_2-point_Winkler_Calibration_2024-11-15.pdf; the expected csv
is calibration/DOSTAD/CGINS-DOSTAD-00315__20241115.csv in asset-management.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from asset_cal.dosta.two_point import DostaTwoPointParser, parse_tables

DEG = chr(0x00B0)
PM = chr(0x00B1)

SVU = "2.794689E-03, 1.242044E-04, 2.063696E-06, 1.596713E+02, -1.995395E-01, -3.852097E+01, 3.122664E+00"
MULTIPOINT = f'serial,name,value,notes\n315,CC_conc_coef,"[0.000000E+00, 1.000000E+00]",date in filename comes from ' \
             f'factory calibration certificate\n315,CC_csv,"[{SVU}]",\n'
EXPECTED = (
    "serial,name,value,notes\n"
    '315,CC_conc_coef,"[-2.62, 1.0554]",offset and slope determined at Oregon State University\n'
    f'315,CC_csv,"[{SVU}]",\n'
)

SN315_TABLES = [
    [
        ["Oxygen Optode Calibration Form", "Control Number: 3305-01815"],
        [None, "Version: 1-02"],
        [None, "Version Date: 2024-06-15"],
        [None, "Quality Reviewer: R. Desiderio, 2025-01-21"],
    ],
    [
        ["Optode Serial Number", "315"],
        ["Foil ID", "1517M"],
        ["2-Point Recalibration Date", "[2024-11-15]"],
        ["Last Multipoint Calibration Filename", "CGINS-DOSTAD-00315__20190705.csv"],
        ["Excel Calibration Workbook Filename", "3305-00815-00059_SN315_2024-11-15.xlsx"],
        ["Notes:", None],
    ],
    [
        [
            "Property",
            f"Air-saturated\n10{DEG}C Water Calibration",
            "Zero-oxygen water\n(Na SO solution)\n2 3",
            f"Air-saturated\n20{DEG}C Water Check",
        ],
        [f"Phase ({DEG})", "33.124", "61.460", "31.195"],
        [f"Optode Temperature ({DEG}C)", "10.027", "19.849", "20.154"],
        ["Air Pressure (hPa)", "1011.36", "1010.87", "1011.77"],
        ["Mean optode reading (uM)", "336.40", "2.48", "267.75"],
        ["Winkler Target (uM)", "352.41", "N/A", "281.13"],
        ["Notes:", None, None, None],
    ],
    [
        ["", "Offset", "Slope", f"20{DEG}C Check [-1.8% {PM} 2%]"],
        ["ConcCoef", "-2.62", "1.0554", "-0.42%"],
        ["Notes:", None, None, None],
    ],
    [
        ["Index", "0", "1", "2", "3", "4", "5", "6"],
        ["SVUFoilCoef", *SVU.split(", ")],
        ["PhaseCoef", "0.000000E+00", "1.000000E+00", "0.000000E+00", "0.000000E+00", "n/a", "n/a", "n/a"],
        ["TempCoef", "2.390303E+01", "-3.082766E-02", "2.842077E-06", "-4.209253E-09", "0.000000E+00",
         "0.000000E+00", "n/a"],
        ["Notes: Salinity = 0", None, None, None, None, None, None, None],
    ],
]


@pytest.fixture
def cal_root(tmp_path: Path) -> Path:
    folder = tmp_path / "DOSTAD"
    folder.mkdir()
    (folder / "CGINS-DOSTAD-00315__20190705.csv").write_text(MULTIPOINT, newline="\n")
    # A vendor 2-point in between, same SVU: must not warn.
    (folder / "CGINS-DOSTAD-00315__20231214.csv").write_text(
        f'serial,name,value,notes\n315,CC_conc_coef,"[-2.099751E+00, 1.002327E+00]",x\n315,CC_csv,"[{SVU}]",\n',
        newline="\n",
    )
    return tmp_path


def _tables(**edits: str) -> list:
    """SN315 tables with cells replaced: key 'row label|column index'."""
    tables = copy.deepcopy(SN315_TABLES)
    for key, value in edits.items():
        label, col = key.split("|")
        for table in tables:
            for row in table:
                if row[0] and row[0].startswith(label):
                    row[int(col)] = value
    return tables


def test_sn315_matches_asset_management(cal_root: Path) -> None:
    cal = parse_tables(SN315_TABLES, cal_root / "DOSTAD", "D")
    assert cal.warnings == ()
    out = DostaTwoPointParser(series="D").write_csv(cal, cal_root)
    assert out.name == "CGINS-DOSTAD-00315__20241115.csv"
    assert out.read_bytes() == EXPECTED.encode("ascii")


def test_printed_slope_disagrees_with_fit(cal_root: Path) -> None:
    with pytest.raises(ValueError, match="slope"):
        parse_tables(_tables(**{"ConcCoef|2": "1.0560"}), cal_root / "DOSTAD", "D")


def test_printed_check_disagrees_with_fit(cal_root: Path) -> None:
    with pytest.raises(ValueError, match="20 C check"):
        parse_tables(_tables(**{"ConcCoef|3": "-0.60%"}), cal_root / "DOSTAD", "D")


def test_check_outside_window_warns_only(cal_root: Path) -> None:
    tables = copy.deepcopy(SN315_TABLES)
    tables[3][0][3] = f"20{DEG}C Check [-3.0% {PM} 2%]"
    cal = parse_tables(tables, cal_root / "DOSTAD", "D")
    assert any("outside the acceptance window" in w for w in cal.warnings)


def test_missing_multipoint_file(cal_root: Path) -> None:
    tables = _tables(**{"Last Multipoint|1": "CGINS-DOSTAD-00315__20180509.csv"})
    with pytest.raises(FileNotFoundError):
        parse_tables(tables, cal_root / "DOSTAD", "D")


def test_svu_disagrees_with_multipoint_file(cal_root: Path) -> None:
    with pytest.raises(ValueError, match="SVUFoilCoef"):
        parse_tables(_tables(**{"SVUFoilCoef|1": "2.794700E-03"}), cal_root / "DOSTAD", "D")


def test_serial_disagrees_with_multipoint_file(cal_root: Path) -> None:
    with pytest.raises(ValueError, match="serial"):
        parse_tables(_tables(**{"Optode Serial|1": "316"}), cal_root / "DOSTAD", "D")


def test_stale_multipoint_reference_warns(cal_root: Path) -> None:
    other = SVU.replace("3.122664E+00", "3.200000E+00")
    (cal_root / "DOSTAD" / "CGINS-DOSTAD-00315__20220101.csv").write_text(
        f'serial,name,value,notes\n315,CC_conc_coef,"[0, 1]",x\n315,CC_csv,"[{other}]",\n', newline="\n"
    )
    cal = parse_tables(SN315_TABLES, cal_root / "DOSTAD", "D")
    assert any("may be stale" in w for w in cal.warnings)


def test_mean_reading_off_svu_warns_only(cal_root: Path) -> None:
    # Keep the fit consistent: only the check-bath phase moves.
    cal = parse_tables(_tables(**{"Phase (|3": "31.300"}), cal_root / "DOSTAD", "D")
    assert any("Mean optode reading (check)" in w for w in cal.warnings)
