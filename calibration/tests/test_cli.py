"""Tests for the cli.py dispatcher.

Class-specific parsing behavior belongs in each class's own tests
(e.g. parad/tests/test_parser_j.py) -- these tests only cover
dispatch, the CLASS-SERIES argument format, the series cross-check,
and the argparse entry point.
"""
from pathlib import Path

import pytest

from asset_cal.cli import generate_cal_csv, main

FIXTURE_DIR = Path(__file__).parent.parent / "asset_cal" / "parad" / "tests" / "fixtures"


def test_generate_cal_csv_dispatches_to_parad(tmp_path: Path) -> None:
    (tmp_path / "PARADJ").mkdir()

    output_path = generate_cal_csv("PARAD-J", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path)

    assert output_path == tmp_path / "PARADJ" / "CGINS-PARADJ-00505__20161108.csv"
    assert output_path.exists()


def test_generate_cal_csv_is_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "PARADJ").mkdir()

    output_path = generate_cal_csv("parad-j", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path)

    assert output_path.exists()


def test_generate_cal_csv_missing_series_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="CLASS-SERIES"):
        generate_cal_csv("PARAD", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path)


def test_generate_cal_csv_series_mismatch_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Series mismatch only fires for a shared, lookup-based parser
    (the future DOSTA/CTDBP pattern) -- exercise it with a stand-in
    rather than depending on PARAD, which registers one parser per
    series and so never hits this path itself.
    """
    from dataclasses import dataclass

    from asset_cal import cli
    from asset_cal.common.series_parser import SeriesParser

    @dataclass(frozen=True)
    class _FakeCal:
        serial_number: int
        series: str

    class _FakeLookupParser(SeriesParser):
        class_code = "FAKE"

        def parse(self, source_path: Path) -> _FakeCal:
            return _FakeCal(serial_number=1, series="J")  # always resolves to J

        def write_csv(self, cal: _FakeCal, calibration_root: Path) -> Path:
            raise AssertionError("write_csv should not be reached on a series mismatch")

    monkeypatch.setitem(cli.PARSERS, "FAKE-D", _FakeLookupParser())

    with pytest.raises(ValueError, match="series 'J', not 'D'"):
        cli.generate_cal_csv("FAKE-D", tmp_path / "irrelevant.dev", calibration_root=tmp_path)


def test_generate_cal_csv_unknown_class_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        generate_cal_csv("NOPE-X", tmp_path / "irrelevant.dev", calibration_root=tmp_path)


def test_main_missing_source_file_exits_nonzero(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["PARAD-J", str(tmp_path / "does_not_exist.dev"), "--asset-management", str(tmp_path)])

    assert exc_info.value.code != 0


def test_generate_cal_csv_preview_writes_prefixed_file_only(tmp_path: Path) -> None:
    (tmp_path / "PARADJ").mkdir()

    output_path = generate_cal_csv(
        "PARAD-J", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path, preview=True
    )

    assert output_path == tmp_path / "PARADJ" / "_preview_CGINS-PARADJ-00505__20161108.csv"
    assert sorted(p.name for p in (tmp_path / "PARADJ").iterdir()) == [output_path.name]


def test_generate_cal_csv_preview_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="PARADJ"):
        generate_cal_csv("PARAD-J", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path, preview=True)


def test_main_requires_asset_management(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["PARAD-J", str(FIXTURE_DIR / "parad_dev_sample.dev")])

    assert exc_info.value.code != 0


PHSEN_FIXTURE = Path(__file__).parent.parent / "asset_cal" / "phsen" / "tests" / "fixtures" / "phsen_qct_sample.txt"


def test_generate_cal_csv_passes_caldate_to_parser_that_needs_it(tmp_path: Path) -> None:
    (tmp_path / "PHSEND").mkdir()

    output_path = generate_cal_csv("PHSEN-D", PHSEN_FIXTURE, calibration_root=tmp_path, caldate="20180629")

    assert output_path.name == "CGINS-PHSEND-P0088__20180629.csv"


def test_generate_cal_csv_missing_caldate_raises(tmp_path: Path) -> None:
    (tmp_path / "PHSEND").mkdir()

    with pytest.raises(ValueError, match="--caldate"):
        generate_cal_csv("PHSEN-D", PHSEN_FIXTURE, calibration_root=tmp_path)


def test_generate_cal_csv_rejects_caldate_for_class_that_reads_it(tmp_path: Path) -> None:
    (tmp_path / "PARADJ").mkdir()

    with pytest.raises(ValueError, match="do not pass --caldate"):
        generate_cal_csv(
            "PARAD-J", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path, caldate="20200101"
        )


def test_generate_cal_csv_rejects_qct_for_class_that_does_not_use_it(tmp_path: Path) -> None:
    (tmp_path / "PARADJ").mkdir()

    with pytest.raises(ValueError, match="do not pass --qct"):
        generate_cal_csv(
            "PARAD-J", FIXTURE_DIR / "parad_dev_sample.dev", calibration_root=tmp_path, qct_path=tmp_path / "x.txt"
        )
