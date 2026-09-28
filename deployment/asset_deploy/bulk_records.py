"""Checks and appends against the bulk_load-AssetRecord.csv files.

Ported from:
    find_missing_bulkSensor_entries.m
    find_missing_bulkEng_entries.m
    sub_append_platconUID_to_engAssetRecord.m
    append_mooringUID_to_platformAssetRecord.m

Design note: unlike deploy_csv.py, this module deliberately keeps
untouched asset-record rows as raw text lines rather than round-tripping
them through csv.reader/csv.writer. Several existing rows contain embedded
commas inside quoted fields (e.g. multi-part equipment descriptions); a
full parse-then-reserialize pass risks silently changing quoting style on
rows that were never meant to change, which would blow up the git diff.
This mirrors the MATLAB source's own approach of treating each row as an
opaque text line and only ever constructing *new* lines from scratch.
"""
from __future__ import annotations

from pathlib import Path

EXPECTED_BULK_HEADER = [
    'ASSET_UID',
    'LEGACY_ASSET_UID',
    'TYPE',
    'Mobile',
    'DESCRIPTION OF EQUIPMENT',
    'MIO_Inventory_Description',
    'Manufacturer',
    'Model',
    "Manufacturer's Serial No./Other Identifier",
    'Firmware Version',
    'ACQUISITION DATE',
    'ORIGINAL COST',
    'comments',
    'MIO',
]

_PROFILER_CGCON_MARKERS = ('BST', 'CSPP', 'WFP')

# key1: platform code (7th char of a CGCON-XYYY__-ZZZZZ uid)
# key2: controller type (chars 8-10)
_PLATCON_DICT = {
    'B': 'Surface Buoy ',
    'E': 'Surface Buoy ',
    'N': 'Near Surface Instrument Frame ',
    'M': 'Multi-Function Node ',
    'CPM': 'Communications and Power Manager',
    'DCL': 'Data Concentrator Logger',
}

# key1: mooring location code (chars 7-8 of a CGMCE-XXYYYY-ZZZZZ uid)
# key2: mooring type code (chars 11-12)
_MOORING_DICT = {
    '01': 'Coastal Endurance Oregon Inshore ',
    '02': 'Coastal Endurance Oregon Shelf ',
    '04': 'Coastal Endurance Oregon Offshore ',
    '06': 'Coastal Endurance Washington Inshore ',
    '07': 'Coastal Endurance Washington Shelf ',
    '09': 'Coastal Endurance Washington Offshore ',
    'SM': 'Surface Mooring',
    'SP': 'Surface Piercing Profiler Mooring',
    'PM': 'Wire Following Profiler Mooring',
}


def _unique_stable(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _read_raw_lines(path: str | Path) -> list[str]:
    with open(path, encoding='utf-8', newline='') as f:
        text = f.read()
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def _write_raw_lines(path: str | Path, lines: list[str]) -> None:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines) + '\n')


def _check_header(header_line: str, path: str | Path) -> None:
    fields = header_line.split(',')
    if len(fields) != len(EXPECTED_BULK_HEADER):
        raise ValueError(
            f'Unexpected number of columns in {path}: {header_line!r}')
    if [f.strip() for f in fields] != EXPECTED_BULK_HEADER:
        raise ValueError(
            f'column labels of asset record are not as expected in {path}: '
            f'{header_line!r}')


def _asset_uid(line: str) -> str:
    # First field never itself contains a comma, so splitting on the first
    # comma is sufficient (matches the MATLAB source's own approach).
    return line.split(',', 1)[0]


def _find_missing(
    sensor_uids: list[str],
    bulk_path: str | Path,
    drop_prefix: str,
    kind: str,
) -> list[str]:
    uids = _unique_stable(
        [u for u in sensor_uids if u and drop_prefix not in u])
    print()
    print(f'Checking bulk{kind} Asset record for these Sensor_UIDs:')
    print(uids)
    print()

    lines = _read_raw_lines(bulk_path)
    _check_header(lines[0], bulk_path)
    print(f"column labels of '{kind}' asset record are as expected.")
    existing = {_asset_uid(line) for line in lines[1:]}
    missing = [u for u in uids if u not in existing]

    print()
    print(f"UIDs missing from the '{kind}' asset record:")
    print('None.' if not missing else missing)
    print()
    return missing


def find_missing_bulk_sensor_entries(
    sensor_uids: list[str], bulk_path: str | Path,
) -> list[str]:
    """Missing CGINS (instrument) uids -- read-only, no file changes."""
    return _find_missing(sensor_uids, bulk_path, drop_prefix='CGCON',
                          kind='Sensor')


def find_missing_bulk_eng_entries(
    sensor_uids: list[str], bulk_path: str | Path,
) -> list[str]:
    """Missing CGCON (controller) uids -- read-only, no file changes.

    Also flags the corresponding CGVEH node uid if a profiler controller
    (CSPP/WFP) is missing, since a new profiler also needs a node record.
    """
    missing = _find_missing(sensor_uids, bulk_path, drop_prefix='CGINS',
                             kind='Eng')
    if missing:
        nodes = [
            q.replace('CGCON-CSPPCE', 'CGVEH-CSPPCE')
             .replace('CGCON-CWFPCE', 'CGVEH-CWFPCE')
            for q in missing
        ]
        nodes = [n for n in nodes if n.lower().startswith('cgveh')]
        if nodes:
            print('UID missing from the node asset record:')
            print(nodes)
    return missing


def resolve_sensor_uids(sensor_uids: list[str], bulk_path: str | Path) -> list[str]:
    """Take each CGINS uid's series letter from the sensor asset record.

    The platform tables fix a series letter per reference designator, but
    the series actually deployed changes between deployments (e.g. PHSEN-D
    vs PHSEN-G on the same refdes). The class and serial number are
    reliable; the series letter is looked up. CGCON and '' entries pass
    through unchanged.

    Raises
    ------
    ValueError
        Listing every uid with no match, or more than one match, in the
        asset record.
    """
    lines = _read_raw_lines(bulk_path)
    _check_header(lines[0], bulk_path)
    index: dict[tuple[str, str], set[str]] = {}
    for line in lines[1:]:
        uid = _asset_uid(line)
        if uid.startswith('CGINS-') and len(uid) > 12:
            index.setdefault((uid[:11], uid[12:]), set()).add(uid)

    resolved: list[str] = []
    problems: list[str] = []
    for uid in sensor_uids:
        if not uid.startswith('CGINS-'):
            resolved.append(uid)
            continue
        matches = sorted(index.get((uid[:11], uid[12:]), set()))
        if len(matches) == 1:
            if matches[0] != uid:
                print(f'series resolved: {uid} -> {matches[0]}')
            resolved.append(matches[0])
        else:
            resolved.append(uid)
            reason = 'no match' if not matches else f'ambiguous {matches}'
            problems.append(f'{uid}: {reason}')

    if problems:
        raise ValueError(
            f'Cannot resolve sensor uids against {Path(bulk_path).name}:\n  ' + '\n  '.join(problems))
    return resolved


def sub_append_platcon_uid_to_eng_asset_record(
    missing_uid: list[str], mode: str, bulk_path: str | Path,
) -> None:
    """Append new CGCON platcon entries to eng_bulk_load-AssetRecord.csv.

    Should only be called with missing uids from a surface mooring
    (ISSM/SHSM/OSSM) deployment -- profiler mooring CGCON uids are
    acknowledged and discarded, matching the MATLAB source's guard, since
    adding new profiler controller entries has not been automated.

    mode='update' writes the asset record file in place; anything else
    writes a '_preview_<name>' file alongside it instead.
    """
    profiler = [u for u in missing_uid
                if any(m in u for m in _PROFILER_CGCON_MARKERS)]
    if profiler:
        print('Profiler cgcon UIDs (mistakenly(?)) input to function: ')
        print(profiler)
        print('These will not be processed.')
        print()

    missing_uid = [u for u in missing_uid if u and u not in profiler]
    if not missing_uid:
        print('No missing CGCON uids.')
        print()
        return

    lines = _read_raw_lines(bulk_path)
    header, data_lines = lines[0], lines[1:]
    _check_header(header, bulk_path)
    print('column labels of asset record are as expected.')

    new_entries: list[str] = []
    for uid in missing_uid:
        key1 = uid[6]
        key2 = uid[7:10]
        if key1 not in _PLATCON_DICT or key2 not in _PLATCON_DICT:
            print('One or both keys are not present in surface mooring '
                  'PlatCon dictionary for:')
            print(uid)
            print(f"Key1 = '{key1}',  Key2 = '{key2}'")
            print()
            continue
        equipment = _PLATCON_DICT[key1] + _PLATCON_DICT[key2]
        inventory = _PLATCON_DICT[key2]
        sernum = str(int(uid[-5:]))  # strips leading zeros
        fields = [uid, '', 'Sensor', '0', equipment, inventory, 'WHOI',
                  key2, sernum, '', '', '', '', '']
        new_entries.append(','.join(fields))

    print('New Platcon entries added to the sorted bulk_sensor Asset '
          'Record:')
    if not new_entries:
        print('    None needed.')
        print('Program terminated; Asset Record not modified.')
        print()
        return
    print(new_entries)

    combined = sorted(data_lines + new_entries)
    out_path = Path(bulk_path)
    if mode == 'update':
        _write_raw_lines(out_path, [header, *combined])
    else:
        preview = out_path.with_name('_preview_' + out_path.name)
        _write_raw_lines(preview, [header, *combined])
        print(f'Test mode: wrote preview to {preview}')


def append_mooring_uid_to_platform_asset_record(
    mooring_sn: list[str], mode: str, bulk_path: str | Path,
) -> None:
    """Append new mooring uids to platform_bulk_load-AssetRecord.csv.

    `mooring_sn` entries look like 'CE01ISSM-00022'. mode='update' writes
    the asset record file in place; anything else writes a
    '_preview_<name>' file alongside it instead.
    """
    mooring_uid = ['CGM' + sn[:2] + '-' + sn[2:14] for sn in mooring_sn]

    lines = _read_raw_lines(bulk_path)
    header, data_lines = lines[0], lines[1:]
    _check_header(header, bulk_path)
    print('column labels of platformAssetRecord are as expected.')

    existing = {_asset_uid(line) for line in data_lines}
    missing = _unique_stable([u for u in mooring_uid if u not in existing])

    print()
    print('UIDs missing from the asset record:')
    if not missing:
        print('None.')
        print('Program terminated.')
        print()
        return
    print(missing)
    print()

    new_entries: list[str] = []
    for uid in missing:
        key1 = uid[6:8]
        key2 = uid[10:12]
        equipment = _MOORING_DICT[key1] + _MOORING_DICT[key2]
        model = uid[3:5] + uid[6:12]
        sernum = uid[3:5] + uid[6:]
        fields = [uid, '', 'Platform', '0', equipment,
                  'MOORING ENDURANCE', 'WHOI', model, sernum, '', '', '',
                  '', 'Oregon State University']
        new_entries.append(','.join(fields))

    print('New asset entries:')
    print(new_entries)

    combined = sorted(data_lines + new_entries)
    out_path = Path(bulk_path)
    if mode == 'update':
        _write_raw_lines(out_path, [header, *combined])
    else:
        preview = out_path.with_name('_preview_' + out_path.name)
        _write_raw_lines(preview, [header, *combined])
        print(f'Test mode: wrote preview to {preview}')
