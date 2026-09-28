"""Append missing mooring uids to platform_bulk_load-AssetRecord.csv.

Ported from append_mooringUID_to_platformAssetRecord.m. The MATLAB source
hardcoded the list of mooring S/Ns at the top of the file and relied on a
hand-maintained comment convention to track which moorings had already been
updated; here the S/Ns are passed as CLI arguments instead, so there is
nothing to hand-edit before each turn.

Usage:
    python append_mooring_uid.py CE02SHSM-00020 CE09OSPM-00022 \\
        --asset-management "C:\\Users\\chris\\code\\asset-management"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from asset_deploy import bulk_records


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'mooring_sn', nargs='+',
        help="mooring S/N(s), e.g. 'CE02SHSM-00020'")
    parser.add_argument(
        '--asset-management', required=True,
        help='path to the local asset-management git clone (contains '
             'bulk/)')
    parser.add_argument(
        '--mode', choices=['update', 'test'], default='update',
        help="'update' writes the asset record in place (default); "
             "'test' writes a '_preview_<name>' file alongside it instead")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    bulk_path = (Path(args.asset_management) / 'bulk'
                 / 'platform_bulk_load-AssetRecord.csv')
    bulk_records.append_mooring_uid_to_platform_asset_record(
        args.mooring_sn, args.mode, bulk_path)


if __name__ == '__main__':
    main()
