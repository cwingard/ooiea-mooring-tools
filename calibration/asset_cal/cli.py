"""Command-line entry point for generating OOI calibration csv files.

Run from the calibration/ folder of ooiea-mooring-tools:

    python -m asset_cal.cli PARAD-J path/to/PARS-XXXX.dev \\
        --asset-management ~/code/asset-management
    python -m asset_cal.cli METCTD-CAL path/to/10906.cal --output-dir METBKA \\
        --asset-management ~/code/asset-management

The instrument class argument is formatted as CLASS-SERIES (e.g.
PARAD-J). The series you supply is cross-checked against the series
the parser actually determines from the source file. For a parser
registered under exactly one series (PARAD-J today) that check can
never fire, since there is only ever one candidate; it becomes real
protection once a class registers a shared, lookup-based parser
under more than one series key (the DOSTA/CTDBP pattern) -- there it
catches a mismatched file or a typo'd class argument instead of
silently writing to whatever folder the filename math produces. For
METCTD, "series" is repurposed as a source-format marker ("CAL" vs
"CAP") rather than a physical instrument series -- see
metctd/parser.py.

Writes directly into <asset-management>/calibration/<class>. There
is no interactive confirmation step -- review the result with
`git diff` / `git status` in asset-management before committing.

--mode test writes every generated file as '_preview_<name>' next to
where the real file would go, instead of the real file. Run a source
file whose calibration is already in asset-management and diff the
preview against the committed file to validate the parser; delete
the preview afterwards.

--caldate YYYYMMDD is required for classes whose source file does not
contain the calibration date (DOSTA, PHSEN: the date is on the vendor
certificate) and rejected for every other class, which reads the date
from the file. Input filenames are never parsed.

--qct <capture> is optional for PCO2W and DOFST (the MMP QCT with the 52-MP
"dc" output); for PCO2W: its values always come from the
vendor PDF certificate (the source file), and when the QCT capture of
the sensor is given as well, any disagreement between the two stops
the run. It is rejected for every other class.

--output-dir overrides which folder under calibration/ the csv goes
into. The default is f"{class_code}{series}" (e.g. PARADJ), which
works for every class except METCTD: it has no folder of its own,
so --output-dir METBKA must always be supplied for it.

Adding a new instrument class or series means adding one entry to
PARSERS below; the dispatch logic itself does not change.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from asset_cal.common.series_parser import SeriesParser
from asset_cal.ctdbp import CtdbpParser
from asset_cal.dofst import DofstParser
from asset_cal.dosta import DostaParser
from asset_cal.flort import FlortParser
from asset_cal.metctd import MetctdCalParser, MetctdCapParser
from asset_cal.nutnr import NutnrParser
from asset_cal.optaa import OptaaParser
from asset_cal.parad import ParadJParser
from asset_cal.pco2w import Pco2wParser
from asset_cal.phsen import PhsenParser
from asset_cal.presf import PresfParser
from asset_cal.spkir import SpkirParser

PREVIEW_PREFIX = "_preview_"

PARSERS: dict[str, SeriesParser] = {
    "PARAD-J": ParadJParser(),
    "DOSTA-D": DostaParser(series="D"),
    "DOSTA-J": DostaParser(series="J"),
    "PHSEN-D": PhsenParser(),
    "PCO2W-B": Pco2wParser(),
    "CTDBP-C": CtdbpParser(series="C"),
    "CTDBP-E": CtdbpParser(series="E"),
    "FLORT-D": FlortParser(series="D"),
    "FLORT-J": FlortParser(series="J"),
    "FLORT-K": FlortParser(series="K"),
    "PRESF-A": PresfParser(series="A"),
    "PRESF-B": PresfParser(series="B"),
    "PRESF-C": PresfParser(series="C"),
    "OPTAA-C": OptaaParser(series="C"),
    "OPTAA-D": OptaaParser(series="D"),
    "OPTAA-J": OptaaParser(series="J"),
    "METCTD-CAL": MetctdCalParser(),
    "METCTD-CAP": MetctdCapParser(),
    "NUTNR-B": NutnrParser(series="B"),
    "NUTNR-J": NutnrParser(series="J"),
    "SPKIR-B": SpkirParser(series="B"),
    "SPKIR-J": SpkirParser(series="J"),
    "DOFST-K": DofstParser(),
}


def _parse_class_arg(class_arg: str) -> tuple[str, str]:
    """Split a CLASS-SERIES argument like 'PARAD-J' into its parts."""
    key = class_arg.upper()
    try:
        class_code, series = key.split("-", 1)
    except ValueError:
        raise ValueError(
            f"instrument_class must be formatted as CLASS-SERIES, e.g. 'PARAD-J'; got {class_arg!r}"
        ) from None
    return class_code, series


def generate_cal_csv(
    class_arg: str,
    source_path: Path,
    calibration_root: Path,
    output_dir_name: str | None = None,
    preview: bool = False,
    caldate: str | None = None,
    qct_path: Path | None = None,
) -> Path:
    """Parse a source file and write its calibration csv.

    Parameters
    ----------
    class_arg : str
        Instrument class and series, formatted as CLASS-SERIES
        (e.g. "PARAD-J"). Case-insensitive.
    source_path : Path
        Path to the vendor/QCT source file to parse.
    calibration_root : Path
        The calibration/ directory of an asset-management clone.
    output_dir_name : str | None
        Overrides the output folder name under calibration_root.
        Defaults to f"{class_code}{series}" (e.g. "PARADJ") when
        not given. METCTD has no folder of its own (real files live
        in METBKA) and must always be called with an override.
    preview : bool
        If True, write every generated file (the csv and any
        companion files, e.g. OPTAA .ext arrays) into the real
        output folder under a "_preview_" prefix instead of its
        real name. Existing previews are overwritten; real files
        are never touched.
    caldate : str | None
        Calibration date as YYYYMMDD. Required for parsers whose
        requires_caldate is True; must be None for all others.
    qct_path : Path | None
        QCT capture of the sensor, cross-checked against the source
        file. Optional for parsers whose accepts_qct is True (PCO2W);
        must be None for all others.

    Returns
    -------
    Path
        Path to the written csv file (the preview path if preview).

    Raises
    ------
    ValueError
        If class_arg is not formatted as CLASS-SERIES, or if the
        series parsed from the source file does not match the
        series requested in class_arg, or if caldate is missing for
        a class that needs it or given for a class that does not.
    KeyError
        If "CLASS-SERIES" is not registered in PARSERS.
    FileNotFoundError
        If the output folder does not exist under calibration_root.
    """
    class_code, expected_series = _parse_class_arg(class_arg)
    key = f"{class_code}-{expected_series}"

    try:
        parser = PARSERS[key]
    except KeyError:
        raise KeyError(f"No parser registered for {key!r}. Registered classes: {sorted(PARSERS)}.") from None

    extra: dict[str, object] = {}
    if parser.requires_caldate:
        extra["caldate"] = caldate
    elif caldate is not None:
        raise ValueError(f"{key} reads the calibration date from the source file; do not pass --caldate.")
    if parser.accepts_qct:
        extra["qct_path"] = qct_path
    elif qct_path is not None:
        raise ValueError(f"{key} does not use a QCT capture alongside its source file; do not pass --qct.")
    cal = parser.parse(source_path, **extra)
    if cal.series != expected_series:
        raise ValueError(
            f"Requested {key} but the parsed instrument (serial {cal.serial_number}) "
            f"is series {cal.series!r}, not {expected_series!r}."
        )

    if not preview:
        return parser.write_csv(cal, calibration_root, output_dir_name)
    return _write_preview(parser, cal, calibration_root, output_dir_name or f"{parser.class_code}{cal.series}")


def _write_preview(parser: SeriesParser, cal: object, calibration_root: Path, dir_name: str) -> Path:
    """Run write_csv in a scratch tree, then copy results in as previews."""
    real_dir = calibration_root / dir_name
    if not real_dir.is_dir():
        raise FileNotFoundError(f"Expected existing directory {real_dir}.")
    with tempfile.TemporaryDirectory() as scratch:
        scratch_root = Path(scratch)
        (scratch_root / dir_name).mkdir()
        csv_path = parser.write_csv(cal, scratch_root, dir_name)
        for generated in sorted((scratch_root / dir_name).iterdir()):
            shutil.copyfile(generated, real_dir / f"{PREVIEW_PREFIX}{generated.name}")
    return real_dir / f"{PREVIEW_PREFIX}{csv_path.name}"


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m asset_cal.cli`."""
    arg_parser = argparse.ArgumentParser(
        description="Generate an OOI calibration csv file from a vendor/QCT source file."
    )
    arg_parser.add_argument(
        "instrument_class",
        help="Instrument class and series, formatted as CLASS-SERIES, e.g. PARAD-J.",
    )
    arg_parser.add_argument("source_path", type=Path, help="Path to the vendor/QCT source file.")
    arg_parser.add_argument(
        "--asset-management",
        required=True,
        type=Path,
        help="Path to the local asset-management git clone (contains calibration/).",
    )
    arg_parser.add_argument(
        "--output-dir",
        dest="output_dir_name",
        default=None,
        help=(
            "Override the output folder name under calibration/ (default: CLASS+SERIES, "
            "e.g. PARADJ). Required for classes with no folder of their own, e.g. "
            "METCTD-CAL/METCTD-CAP -> METBKA."
        ),
    )
    arg_parser.add_argument(
        "--caldate",
        default=None,
        help="Calibration date YYYYMMDD from the vendor certificate. Required for DOSTA and PHSEN only.",
    )
    arg_parser.add_argument(
        "--qct",
        type=Path,
        default=None,
        help="QCT capture of the sensor, cross-checked against the certificate. PCO2W and DOFST only; optional.",
    )
    arg_parser.add_argument(
        "--mode",
        choices=["update", "test"],
        default="update",
        help="'update' writes the real file (default); 'test' writes '_preview_<name>' files instead.",
    )
    args = arg_parser.parse_args(argv)

    if not args.source_path.exists():
        arg_parser.error(f"source file not found: {args.source_path}")
    calibration_root = args.asset_management.expanduser() / "calibration"
    if not calibration_root.is_dir():
        arg_parser.error(f"no calibration/ directory under {args.asset_management}")

    try:
        output_path = generate_cal_csv(
            args.instrument_class,
            args.source_path,
            calibration_root,
            output_dir_name=args.output_dir_name,
            preview=args.mode == "test",
            caldate=args.caldate,
            qct_path=args.qct,
        )
    except (KeyError, ValueError, FileNotFoundError, ImportError) as exc:
        arg_parser.error(str(exc))

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
