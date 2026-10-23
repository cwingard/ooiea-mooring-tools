"""Command line: python -m asset_discrete.cli {new,migrate,build,validate} ...

Run from the discrete/ folder of ooiea-mooring-tools. See README.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asset_discrete.btl import BtlError
from asset_discrete.labs import LabError
from asset_discrete.summary import BuildError, build, write_outputs
from asset_discrete.validate_summary import Validator, read_cruises, write_issues
from asset_discrete.workbook import WorkbookError, make_workbook, migrate


def _refuse_overwrite(path: Path, replace: bool) -> None:
    if path.exists() and not replace:
        raise WorkbookError(f'{path} already exists; use --replace to overwrite')


def cmd_new(args: argparse.Namespace) -> int:
    out = Path(args.output)
    _refuse_overwrite(out, args.replace)
    make_workbook().save(out)
    print(f'wrote {out}')
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    src, out = Path(args.workbook), Path(args.output)
    if out.resolve() == src.resolve():
        raise WorkbookError('write the migrated workbook to a new file, then replace the original after checking it')
    _refuse_overwrite(out, args.replace)
    migrate(src).save(out)
    print(f'wrote {out}')
    return 0


def _labs(items: list[str]) -> dict[str, str]:
    """['oxygen=path', ...] -> {'oxygen': 'path', ...}."""
    labs = {}
    for item in items:
        analysis, sep, path = item.partition('=')
        if not sep or not analysis or not path:
            raise BuildError(f'--lab expects ANALYSIS=PATH, got {item!r}')
        if analysis in labs:
            raise BuildError(f'--lab {analysis} given twice')
        labs[analysis] = path
    return labs


def cmd_build(args: argparse.Namespace) -> int:
    result = build(args.workbook, args.btl_dir, _labs(args.lab))
    for path in write_outputs(result, args.workbook, args.output_dir, args.version, args.note):
        print(f'wrote {path}')
    for line in result.log:
        print(f'  {line}')
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cruises = read_cruises(args.asset_management) if args.asset_management else None
    validator = Validator(cruises)
    issues = [i for f in args.files for i in validator.check(Path(f))]
    write_issues(issues, args.out)
    errors = sum(i.severity == 'ERROR' for i in issues)
    print(f'{len(issues)} issue(s), {errors} error(s); written to {args.out}')
    if cruises is None:
        print('  no --asset-management given: cruise IDs and cruise windows were not checked')
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='asset_discrete', description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('new', help='write a blank transcription workbook')
    p.add_argument('output', help='new .xlsx path')
    p.add_argument('--replace', action='store_true', help='overwrite an existing file')
    p.set_defaults(func=cmd_new)

    p = sub.add_parser('migrate', help='move a filled workbook to the current layout')
    p.add_argument('workbook', help='existing transcription workbook')
    p.add_argument('output', help='new .xlsx path (not the input)')
    p.add_argument('--replace', action='store_true', help='overwrite an existing output file')
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser('build', help='build the Discrete Summary xlsx, README and build log')
    p.add_argument('workbook', help='transcription workbook (current layout)')
    p.add_argument('btl_dir', help='folder with one .btl per cast')
    p.add_argument('output_dir', help='folder for the outputs (README history is kept there)')
    p.add_argument('--version', required=True, help='README revision, e.g. 1.00')
    p.add_argument('--note', required=True, help='README revision note')
    p.add_argument('--lab', action='append', default=[], metavar='ANALYSIS=PATH',
                   help='lab results file, e.g. oxygen=SR2614_O2.LST (repeat per analysis)')
    p.set_defaults(func=cmd_build)

    p = sub.add_parser('validate', help='check Discrete Summary CSV files against the OOI-wide format')
    p.add_argument('files', nargs='+', help='summary CSV files')
    p.add_argument('--out', required=True, help='issues CSV to write')
    p.add_argument('--asset-management', help='asset-management clone, for cruise IDs and windows')
    p.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (WorkbookError, BuildError, BtlError, LabError, FileNotFoundError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
