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


# --- PARAD-K ----------------------------------------------------------------

from asset_cal.parad.parser import ParadKParser  # noqa: E402

K_VALUES = {"serial": "20611", "dark_offset": "0.45", "scale_wet": "9.04E-18"}  # certificate 2024-05-17


def test_paradk_writes_transcribed_values(tmp_path: Path) -> None:
    parser_k = ParadKParser()
    (tmp_path / "PARADK").mkdir()

    cal = parser_k.parse(tmp_path / "cert.pdf", caldate="20240517", transcribed=K_VALUES)
    output_path = parser_k.write_csv(cal, tmp_path)

    assert output_path.name == "CGINS-PARADK-20611__20240517.csv"
    assert output_path.read_text().splitlines()[1:] == [
        "20611,CC_dark_offset,0.45,probe dark [mV]; transcribed from cert.pdf",
        "20611,CC_scale_wet,9.04E-18,[V/(quanta/cm2-sec)]",
    ]


@pytest.mark.parametrize(
    ("name", "typo"),
    [("dark_offset", "0.045"), ("dark_offset", "45"), ("scale_wet", "9.04E-17"), ("scale_wet", "9.04E-19")],
)
def test_paradk_rejects_likely_typos(tmp_path: Path, name: str, typo: str) -> None:
    with pytest.raises(ValueError, match="plausible range"):
        ParadKParser().parse(tmp_path / "c.pdf", caldate="20240517", transcribed={**K_VALUES, name: typo})


def test_paradk_requires_caldate(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--caldate"):
        ParadKParser().parse(tmp_path / "c.pdf", transcribed=K_VALUES)


def test_paradk_review_warns_on_large_change_only(tmp_path: Path) -> None:
    folder = tmp_path / "PARADK"
    folder.mkdir()
    (folder / "CGINS-PARADK-20611__20230328.csv").write_text(
        "serial,name,value,notes\n20611,CC_dark_offset,1.28,\n20611,CC_scale_wet,8.81E-18,\n"
    )
    parser_k = ParadKParser()

    normal = parser_k.parse(tmp_path / "c.pdf", caldate="20240517", transcribed=K_VALUES)
    jumped = parser_k.parse(tmp_path / "c.pdf", caldate="20240517", transcribed={**K_VALUES, "scale_wet": "1.10E-17"})

    assert parser_k.review(normal, tmp_path) == []
    assert "differs by 25%" in parser_k.review(jumped, tmp_path)[0]
