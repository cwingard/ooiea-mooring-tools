#!/usr/bin/env python3
"""Build a mooring instrument directory tree from a deployment config spreadsheet.

Pure-Python replacement for the original buildtree bash/awk/ssconvert script.
Platform name and deployment number are taken from the config file name,
separated by a dash or underscore (e.g. CE07SHSM-00020.xlsx ->
platform=CE07SHSM, deployment=00020). DCL number, instrument name, and
serial number are read from the "Instruments" section of the first
worksheet and used to build:

    <platform>/R<deployment>/instrmts/dcl<NN>/<INSTRUMENT>_sn<SERIAL>

for each instrument serial-number entry found. Existing directories are
never deleted or modified.
"""

from __future__ import annotations

import argparse
import re
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import openpyxl

DCL_PORT_RE = re.compile(r"dcl.*:.*port", re.IGNORECASE)
STC_PORT_RE = re.compile(r"stc.*port", re.IGNORECASE)
SERIAL_FIELD_RE = re.compile(r"s/n", re.IGNORECASE)
SERIAL_TOKEN_RE = re.compile(r"s.n", re.IGNORECASE)
LOCATION_RE = re.compile(r"location", re.IGNORECASE)
DEPTH_RE = re.compile(r"depth", re.IGNORECASE)
NA_RE = re.compile(r"n.a", re.IGNORECASE)


@dataclass
class Action:
    """One event produced while walking the Instruments section.

    `directory`, if set, is a directory that should be created (or
    reported as already existing). `warning`, if set, should be printed
    to stderr regardless of whether `directory` is also set.
    """

    directory: str | None = None
    warning: str | None = None


def cell_text(value: object) -> str:
    """Coerce a spreadsheet cell value to a stripped string.

    Excel stores serial numbers that look like integers (e.g. "2218")
    as numeric cells, so plain str() would otherwise round-trip them
    through a float representation.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def load_rows(path: Path) -> list[list[str]]:
    """Load the first worksheet of an xlsx file as rows of text cells."""
    with warnings.catch_warnings():
        # openpyxl warns when a workbook has a header/footer block it can't
        # parse; that block is irrelevant to us, so silence just that warning.
        warnings.filterwarnings(
            "ignore",
            message="Cannot parse header or footer",
            category=UserWarning,
        )
        wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    return [[cell_text(c) for c in row] for row in ws.iter_rows(values_only=True)]


def platform_and_deployment(path: Path) -> tuple[str, int]:
    """Extract platform name and deployment number from the config filename."""
    parts = re.split(r"[-_]", path.stem)
    if len(parts) != 2:
        raise ValueError(
            "can't figure out platform name and deployment number from "
            f"file name: {path.name}"
        )
    platform, deployment = parts
    if not deployment.isdigit():
        raise ValueError(f"deployment number is not numeric: {deployment!r}")
    return platform.upper(), int(deployment)


def clean_serial(raw: str) -> str:
    """Replicate the original script's serial-number cleanup rules."""
    if NA_RE.search(raw):
        return ""
    s = raw
    s = re.sub(r"/.*$", "", s)
    s = s.replace("@", "", 1)
    s = re.sub(r" $", "", s)
    s = re.sub(r" +", "-", s)
    s = re.sub(r"\(.*\)", "", s, count=1)
    s = re.sub(r"-$", "", s)
    if NA_RE.search(s):
        return ""
    return s


def find_instruments_start(rows: list[list[str]]) -> int:
    """Return the row index of the "Instruments" section header."""
    for i, row in enumerate(rows):
        if row and "instruments" in row[0].lower():
            return i
    raise ValueError("start of Instruments section never found")


def is_blank(row: list[str]) -> bool:
    """A row counts as blank if its first four fields are all empty."""
    return all(v == "" for v in row[:4])


def build_directories(
    rows: list[list[str]], platform: str, deployment: int
) -> list[Action]:
    """Walk the Instruments section and return the directories it implies.

    The section ends at two consecutive blank rows (or end of sheet).
    Sub-section headers ("Buoy", "NSIF", "MFN", ...), Location/Depth
    lines, and anything else that isn't a "DCL:Port #" or "S/N" line
    are silently skipped, matching the original script.
    """
    start = find_instruments_start(rows)
    actions: list[Action] = []
    dcl = 0
    n = len(rows)
    i = start + 1

    def read_next() -> list[str] | None:
        nonlocal i
        if i >= n:
            return None
        row = rows[i]
        i += 1
        return row

    while True:
        row = read_next()
        if row is None:
            break

        if is_blank(row):
            row2 = read_next()
            if row2 is None or is_blank(row2):
                break
            row = row2

        f1 = row[0] if len(row) > 0 else ""
        f2 = row[1] if len(row) > 1 else ""

        if DCL_PORT_RE.search(f1):
            parts = f2.split(":")
            if len(parts) >= 2 and parts[0].strip().isdigit():
                dcl = int(parts[0])
            elif "N/A" in f2:
                dcl = 0
            else:
                dcl = 0
                actions.append(
                    Action(warning=f'garbled DCL# - defaulting to DCL=00 ("{f1}", "{f2}")')
                )

        elif STC_PORT_RE.search(f1):
            dcl = 0

        elif SERIAL_FIELD_RE.search(f1):
            tokens = f1.split()
            instr = tokens[0] if tokens else ""
            serial = ""
            if (len(tokens) > 1 and SERIAL_TOKEN_RE.search(tokens[1])) or (
                len(tokens) > 2 and SERIAL_TOKEN_RE.search(tokens[2])
            ):
                serial = clean_serial(f2)

            warning: str | None = None
            if "unknown" in serial.lower():
                serial = ""
                warning = f'missing serial # ("{f1}", "{f2}")'

            directory = f"{platform}/R{deployment:05d}/instrmts/dcl{dcl:02d}/{instr}_sn{serial}"
            actions.append(Action(directory=directory, warning=warning))

        elif LOCATION_RE.search(f1) or DEPTH_RE.search(f1):
            pass

        # anything else (sub-section headers, unrecognized lines): skip

    return actions


def run(actions: list[Action], dry_run: bool) -> None:
    for action in actions:
        if action.warning:
            print(f"buildtree warning: {action.warning}", file=sys.stderr)
        if action.directory is None:
            continue
        path = Path(action.directory)
        exists = path.is_dir()
        if dry_run:
            print(f"{'already exists' if exists else 'would create'}: {path}")
        elif exists:
            print(f"directory already exists: {path}")
        else:
            print(f"creating: {path}")
            path.mkdir(parents=True, exist_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="buildtree",
        description=(
            "Build a directory tree for a mooring deployment from a "
            "deployment configuration spreadsheet."
        ),
    )
    parser.add_argument(
        "configfile", type=Path, help="deployment configuration .xlsx file"
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="parse the config file but don't create any directories",
    )
    args = parser.parse_args(argv)

    if not args.configfile.exists():
        print(f"no such file: {args.configfile}", file=sys.stderr)
        return 1
    if args.configfile.suffix.lower() != ".xlsx":
        print(
            f"unsupported file type: {args.configfile.suffix!r} (expected .xlsx)",
            file=sys.stderr,
        )
        return 1

    try:
        platform, deployment = platform_and_deployment(args.configfile)
        rows = load_rows(args.configfile)
        actions = build_directories(rows, platform, deployment)
    except ValueError as exc:
        print(f"buildtree error: {exc}", file=sys.stderr)
        return 1

    run(actions, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
