"""Asset-management deployment records for Endurance moorings.

Two subcommands, each taking every operator input exactly once:

deploy
    Append a new deployment to <PLATFORM>_Deploy.csv from the deployment
    config workbook, and add the mooring uid to
    platform_bulk_load-AssetRecord.csv. The platform is read from the
    workbook's 'Reference Designator:' row. With --replace, regenerate an
    existing (not yet recovered) deployment in place from the workbook, e.g.
    to swap pre-cruise placeholders for the as-deployed configuration.

        python -m asset_deploy.cli deploy --config CE07SHSM-00021.xlsx \\
            --asset-management ~/code/asset-management

recover
    Write the recovery time and cruise into every row of one deployment.

        python -m asset_deploy.cli recover CE07SHSM-00021 --cruise SR2614 \\
            --time 2026-10-01T15:30:00 \\
            --asset-management ~/code/asset-management

Both validate before writing anything: the cruise must exist in
cruise/CruiseInformation.csv and the launch or recovery time must fall inside
it. deploy also resolves every CGINS series letter from
sensor_bulk_load-AssetRecord.csv, refuses to append a deployment number that
already exists (use --replace), and stops on CGCON uids missing from
eng_bulk_load-AssetRecord.csv that it cannot auto-append (profilers).
recover refuses to overwrite existing recovery info without --force.

--mode test writes '_preview_<name>' files alongside the real ones instead.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import re
from pathlib import Path
from types import ModuleType

from asset_deploy import bulk_records, cruise, deploy_csv
from asset_deploy.config_xlsx import read_config
from asset_deploy.metadata import read_metadata

_MOORING_SN = re.compile(r'^([A-Z0-9]{8})-(\d{5})$')


def _load_platform(platform_code: str) -> ModuleType:
    name = f'asset_deploy.platforms.{platform_code.lower()}'
    if importlib.util.find_spec(name) is None:
        raise ValueError(f'No deployment builder for platform {platform_code!r}')
    return importlib.import_module(name)


def _deploy_csv_path(asset_management: Path, platform_code: str) -> Path:
    return asset_management / 'deployment' / f'{platform_code}_Deploy.csv'


def _out_path(path: Path, mode: str) -> Path:
    return path if mode == 'update' else path.with_name('_preview_' + path.name)


def deploy(args: argparse.Namespace) -> None:
    asset_management = Path(args.asset_management)
    bulk_dir = asset_management / 'bulk'
    sensor_bulk = bulk_dir / 'sensor_bulk_load-AssetRecord.csv'
    eng_bulk = bulk_dir / 'eng_bulk_load-AssetRecord.csv'
    platform_bulk = bulk_dir / 'platform_bulk_load-AssetRecord.csv'

    config = read_config(args.config)
    meta = read_metadata(config)
    platform = _load_platform(meta.platform_code)
    deploy_path = Path(args.deploy_csv or _deploy_csv_path(asset_management, meta.platform_code))

    cruise.check_cruise(asset_management, meta.cruise_id, meta.start_date_time, 'Launch')
    existing = deploy_csv.read_deploy_csv(deploy_path)
    current = deploy_csv.deployment_rows(existing, meta.dep_num)
    if args.replace:
        if not current:
            raise ValueError(f'{deploy_path.name} has no rows for deployment {meta.dep_num} to replace')
        if any(r.get(deploy_csv.COL_STOP_DATETIME) or r.get(deploy_csv.COL_CUID_RECOVER) for r in current):
            raise ValueError(f'Deployment {meta.dep_num} is already recovered; edit its rows by hand')
        version = current[-1][deploy_csv.COL_VERSION_NUMBER]
    elif current:
        raise ValueError(
            f'{deploy_path.name} already has rows for deployment {meta.dep_num}; use --replace to update them')
    else:
        version = deploy_csv.previous_version_number(existing)
    result = platform.build_deployment(config, version)

    # Validate every uid before anything is written.
    result.sensor_uids = bulk_records.resolve_sensor_uids(result.sensor_uids, sensor_bulk)
    for row, uid in zip(result.rows, result.sensor_uids):
        row['sensor.uid'] = uid
    missing_eng = bulk_records.find_missing_bulk_eng_entries(result.sensor_uids, eng_bulk)
    can_append = args.append_platcon and getattr(platform, 'SUPPORTS_PLATCON_APPEND', True)
    if missing_eng and not can_append:
        raise ValueError(
            f'CGCON uids missing from {eng_bulk.name} that are not auto-appended for '
            f'{meta.platform_code}: {missing_eng}. Add them by hand, then re-run.')

    print()
    print(f'Mooring_uid: {meta.mooring_sn}')
    print(f' latitude as written out:   {meta.lat}')
    print(f'longitude as written out:  {meta.lon}')
    print(f'datetime as written out:   {meta.start_date_time}')
    print()

    if args.replace:
        changes = deploy_csv.replace_deployment(existing, meta.dep_num, result.rows)
        _print_changes(changes, len(result.rows))
    else:
        deploy_csv.append_new_deployment(existing, result.rows)
    out_path = _out_path(deploy_path, args.mode)
    deploy_csv.write_deploy_csv(out_path, existing)
    print(f"{'replaced' if args.replace else 'wrote'} {len(result.rows)} rows in {out_path}")

    if can_append:
        bulk_records.sub_append_platcon_uid_to_eng_asset_record(missing_eng, args.mode, eng_bulk)
    bulk_records.append_mooring_uid_to_platform_asset_record([meta.mooring_sn], args.mode, platform_bulk)


def _print_changes(changes: list[tuple[str, str, str, str]], n_rows: int) -> None:
    if not changes:
        print('No changes from the existing rows.')
        return
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for refdes, field, old, new in changes:
        grouped.setdefault((field, old, new), []).append(refdes)
    print('Changes:')
    for (field, old, new), refdes in grouped.items():
        where = 'all rows' if len(refdes) == n_rows else ', '.join(rd[9:] for rd in refdes)
        print(f'  {field}: {old!r} -> {new!r}  ({where})')


def recover(args: argparse.Namespace) -> None:
    match = _MOORING_SN.match(args.mooring.strip().upper())
    if match is None:
        raise ValueError(f'Expected a mooring S/N like CE07SHSM-00021, got {args.mooring!r}')
    platform_code, dep_num = match.group(1), int(match.group(2))
    asset_management = Path(args.asset_management)
    deploy_path = Path(args.deploy_csv or _deploy_csv_path(asset_management, platform_code))

    stop = cruise.parse_time(args.time)
    stop_date_time = cruise.format_time(stop)
    cruise.check_cruise(asset_management, args.cruise, stop_date_time, 'Recovery')

    existing = deploy_csv.read_deploy_csv(deploy_path)
    rows = deploy_csv.deployment_rows(existing, dep_num)
    if not rows:
        raise ValueError(f'{deploy_path.name} has no rows for deployment {dep_num}')
    start = max(cruise.parse_time(r[deploy_csv.COL_START_DATETIME]) for r in rows)
    if stop <= start:
        raise ValueError(f'Recovery time {stop_date_time} is not after deployment start {cruise.format_time(start)}')

    deploy_csv.record_recovery(existing, dep_num, stop_date_time, args.cruise, force=args.force)
    out_path = _out_path(deploy_path, args.mode)
    deploy_csv.write_deploy_csv(out_path, existing)
    print(f'{platform_code}-{dep_num:05d}: recovered {stop_date_time} on {args.cruise}; '
          f'updated {len(rows)} rows in {out_path}')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        '--asset-management', required=True,
        help='path to the local asset-management git clone (contains deployment/, bulk/ and cruise/)')
    common.add_argument(
        '--deploy-csv',
        help='override the target *_Deploy.csv path (default: <asset-management>/deployment/<PLATFORM>_Deploy.csv)')
    common.add_argument(
        '--mode', choices=['update', 'test'], default='update',
        help="'update' writes files in place (default); 'test' writes '_preview_<name>' files instead")

    p = sub.add_parser('deploy', parents=[common], help='append a new deployment from a config workbook')
    p.add_argument('--config', required=True, help='path to the deployment config.xlsx file')
    p.add_argument(
        '--replace', action='store_true',
        help='regenerate an existing, not yet recovered deployment in place (e.g. final as-deployed values)')
    p.add_argument(
        '--no-append-platcon', dest='append_platcon', action='store_false',
        help='skip appending missing platcon uids to eng_bulk_load-AssetRecord.csv')
    p.set_defaults(func=deploy)

    p = sub.add_parser('recover', parents=[common], help='record the recovery of a deployment')
    p.add_argument('mooring', help='mooring S/N being recovered, e.g. CE07SHSM-00021')
    p.add_argument('--cruise', required=True, help='recovery cruise ID, e.g. SR2614 (or UNRECOVERED)')
    p.add_argument('--time', required=True, help='recovery date-time, UTC, e.g. 2026-10-01T15:30:00')
    p.add_argument('--force', action='store_true', help='overwrite existing recovery info')
    p.set_defaults(func=recover)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(f'error: {exc}') from None


if __name__ == '__main__':
    main()
