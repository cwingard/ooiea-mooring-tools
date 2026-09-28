"""Command line: python -m asset_ingest.cli {generate,check} ...

Run from the ingestion/ folder of ooiea-mooring-tools. See README.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asset_ingest.check import check_site
from asset_ingest.config_wiring import ConfigError
from asset_ingest.deploy_state import DeployStateError
from asset_ingest.generate import GenerateError, generate
from asset_ingest.ingest_file import IngestFileError, write_ingest_csv

DEFAULT_TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'


def preview_name(name: str) -> str:
    return name.replace('_ingest.csv', '_ingest_preview.csv')


def cmd_generate(args: argparse.Namespace) -> int:
    result = generate(args.config, args.asset_management, args.templates)
    folder = Path(args.ingestion_csvs) / result.site
    if not folder.is_dir():
        raise GenerateError(f'{folder} does not exist')

    targets = {name: folder / (preview_name(name) if args.mode == 'test' else name) for name in result.files}
    if args.mode == 'live' and not args.replace:
        existing = [p.name for p in targets.values() if p.exists()]
        if existing:
            raise GenerateError(f'{", ".join(existing)} already exist; use --replace to overwrite')

    for name, rows in result.files.items():
        write_ingest_csv(targets[name], rows)
        print(f'wrote {targets[name]}')
    if result.not_deployed:
        print('Not Deployed (commented out): ' + ', '.join(result.not_deployed))
    if result.no_stream:
        print('Deployed, no template row (no ingestion stream): ' + ', '.join(result.no_stream))
    for note in result.follows_ctd:
        print('Follows its CTDBP: ' + note)
    if result.ignored_config:
        print('Config instruments with no reference designator (ignored): ' + ', '.join(result.ignored_config))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    findings = check_site(args.ingestion_csvs, args.site, args.asset_management, args.deployment)
    for f in findings:
        print(f)
    print(f'{len(findings)} finding(s)')
    return 1 if findings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='asset_ingest', description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest='command', required=True)

    g = sub.add_parser('generate', help='write D000NN and R000NN ingestion CSVs for one deployment')
    g.add_argument('--config', required=True, help='deployment configuration workbook (.xlsx)')
    g.add_argument('--asset-management', required=True, help='asset-management repo root')
    g.add_argument('--ingestion-csvs', required=True, help='ingestion-csvs repo root')
    g.add_argument('--templates', default=DEFAULT_TEMPLATES, help='templates folder (default: %(default)s)')
    g.add_argument('--mode', choices=('live', 'test'), default='live',
                   help='test writes *_ingest_preview.csv next to the real files')
    g.add_argument('--replace', action='store_true', help='overwrite existing files (live mode)')
    g.set_defaults(func=cmd_generate)

    c = sub.add_parser('check', help="report consistency problems in a site's ingestion CSVs")
    c.add_argument('site', help='site code, e.g. CE07SHSM')
    c.add_argument('--ingestion-csvs', required=True, help='ingestion-csvs repo root')
    c.add_argument('--asset-management', help='asset-management repo root (enables deployed-state checks)')
    c.add_argument('--deployment', type=int, help='check only this deployment number')
    c.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (GenerateError, ConfigError, DeployStateError, IngestFileError) as err:
        print(f'ERROR: {err}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
