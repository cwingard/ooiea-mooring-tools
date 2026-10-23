"""Transcription workbook: the hand-entered record of one cruise.

The sheet and header names below are the contract with the build; columns
are read by header. `make_workbook` writes the blank template, `migrate`
moves a filled workbook from an older layout to this one (matching by
header, so nothing is dropped silently), and `read_workbook` returns the
sheets as lists of dicts for the build.
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime, time
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from asset_discrete import REFERENCE
from asset_discrete.flags import choices


class WorkbookError(ValueError):
    """The workbook does not match the expected layout."""


def _sites() -> list[str]:
    with open(REFERENCE / 'stations.csv', newline='', encoding='utf-8-sig') as f:
        return [row['station'] for row in csv.DictReader(f)]


FONT = 'Arial'
SIZE = 10
RULE = Border(bottom=Side(style='thin', color='000000'))
MAX_ROWS = 1000
MIN_W, MAX_W, TEXT_W = 6, 40, 50
SOFT_LISTS = {'All'}    # suggestion only: Notes Cast/Niskin also take numbers and ranges
TIME_TAG = '[UTC HH:MM]'
TIME_FORMAT = 'h:mm'
DATE_TAG = '[UTC YYYY-MM-DD]'
DATE_FORMAT = 'yyyy-mm-dd'

FLAG_SETS = {'Cast Flags': choices('castFlags'), 'CTD File Flags': choices('CTDFileFlags'),
             'Niskin Flags': choices('niskinFlags'), 'Sample Flags': choices('discreteSampleFlags')}
LISTS = {'All'}    # suggestion only: Notes Cast/Niskin also take numbers and ranges
TIME_TAG = '[UTC HH:MM]'
TIME_FORMAT = 'h:mm'
DATE_TAG = '[UTC YYYY-MM-DD]'
DATE_FORMAT = 'yyyy-mm-dd'

FLAG_SETS = {
    'Cast Flags': ['Delayed start to data collection', 'Non-standard winch speed', 'Non-standard surface soak time',
                   'Non-standard bottle soak time before Niskin trip',
                   'Sensor issues but cast completed and data collected',
                   'Cable issues but cast completed and data collected',
                   'Winch issues but cast completed and data collected',
                   'Premature cast end with data and/or data loss', 'Significant ship heave',
                   'Station position not adequately maintained during cast', 'Tow-yo, Yo-yo cast',
                   'ROV bottle sample'],
    'CTD File Flags': ['Data cast only, no Niskins triggered', 'File processed using modified parameters',
                       'File processed using alternate XMLCON', 'Missing scans as indicated by modulo error counts',
                       'Missing metadata'],
    'Niskin Flags': ['Bottle information unavailable', 'Leaking', 'Ran out of water during sampling', 'Vent open',
                     'Misfire at wrong depth', 'Unknown problem'],
    'Sample Flags': ['Questionable measurement', 'Bad measurement', 'Not reported', 'Sample collected out of order',
                     'Sample processed using alternative method; see notes'],
}
LISTS = {
    'Sites': _sites(),
    'Analyses': ['oxygen', 'salinity', 'nutrients', 'chlorophyll', 'dic_ta'],
    'Sample Issue Types': ['assign', 'exclude', 'flag', 'review'],
    **FLAG_SETS,
    'Summary Flag Columns': ['Cast Flag', 'CTD File Flag', 'Niskin Flag', 'CTD Pressure Flag', 'CTD Temperature 1 Flag',
                             'CTD Temperature 2 Flag', 'CTD Conductivity 1 Flag', 'CTD Conductivity 2 Flag',
                             'CTD Oxygen Flag', 'CTD Fluorescence Flag', 'CTD Transmissometer Flag', 'CTD pH Flag',
                             'Discrete Oxygen Flag', 'Discrete Fluorescence Flag', 'Discrete Nutrients Flag',
                             'Discrete Salinity Flag', 'Discrete Alkalinity Flag', 'Discrete DIC Flag',
                             'Discrete pCO2 Flag', 'Discrete pH Flag'],
    'All': ['All'],
}

# sheet -> [(internal key, header, list name or None, free text?)]
_POS = [('lat_deg', 'Latitude [deg]'), ('lat_min', 'Latitude [min]'), ('lon_deg', 'Longitude [deg W]'),
        ('lon_min', 'Longitude [min]'), ('water_depth_m', 'Water Depth [m]'), ('ctd_depth_m', 'CTD Depth [m]'),
        ('time_utc', 'Time [UTC HH:MM]')]
_CHECK = [('check', 'Transcription Check', None, True)]
SCHEMA = {
    'Cruise': [
        ('cruise', 'Cruise', None, False), ('expedition', 'Expedition', None, False), ('ship', 'Ship', None, False),
        ('start_date', 'Start Date [UTC YYYY-MM-DD]', None, False),
        ('end_date', 'End Date [UTC YYYY-MM-DD]', None, False), ('notes', 'Notes', None, True)],
    'Cast Log': [
        ('cruise', 'Cruise', None, False), ('cast', 'Cast', None, False), ('site', 'Site', 'Sites', False),
        ('target_assets', 'Target Assets', None, True), ('ctd_file', 'CTD File', None, False),
        ('date_utc', 'Cast Date [UTC YYYY-MM-DD]', None, False),
        ('start_time_utc', 'Start Time [UTC HH:MM]', None, False),
        ('start_lat_deg', 'Start Latitude [deg]', None, False), ('start_lat_min', 'Start Latitude [min]', None, False),
        ('start_lon_deg', 'Start Longitude [deg]', None, False),
        ('start_lon_min', 'Start Longitude [min]', None, False),
        ('start_water_depth_m', 'Start Water Depth [m]', None, False),
        ('cast_flag', 'Cast Flag', 'Cast Flags', False), ('cast_flag_2', 'Cast Flag 2', 'Cast Flags', False),
        ('ctd_file_flag', 'CTD File Flag', 'CTD File Flags', False), ('notes', 'Notes', None, True), *_CHECK],
    'Niskin Log': [
        ('cruise', 'Cruise', None, False), ('cast', 'Cast', None, False), ('niskin', 'Niskin', None, False),
        ('trip_time_utc', 'Trip Time [UTC HH:MM]', None, False), ('trip_depth_m', 'Trip Depth [m]', None, False),
        ('temp_c', 'Temperature [deg C]', None, False), ('salinity_psu', 'Salinity [psu]', None, False),
        ('niskin_flag', 'Niskin Flag', 'Niskin Flags', False), ('notes', 'Notes', None, True),
        ('oxygen_samples', 'Oxygen Samples', None, False),
        ('draw_temp_c', 'Oxygen Draw Temperature [deg C]', None, False),
        ('dic_ta_samples', 'DIC/TA Samples', None, False), ('salinity_samples', 'Salinity Samples', None, False),
        ('nutrient_samples', 'Nutrient Samples', None, False), ('chl_filters', 'Chlorophyll Filters', None, False),
        ('volume_ml', 'Chlorophyll Volume Filtered [mL]', None, False), *_CHECK],
    'Sample Issues': [
        ('cruise', 'Cruise', None, False), ('cast', 'Cast', None, False), ('niskin', 'Niskin', None, False),
        ('analysis', 'Analysis', 'Analyses', False), ('sample_id', 'Sample ID', None, False),
        ('action', 'Issue', 'Sample Issue Types', False), ('sample_flag', 'Sample Flag', 'Sample Flags', False),
        ('reason', 'Reason', None, True), ('lab_file', 'Lab File', None, True),
        ('lab_key', 'Lab Sample Key', None, False), ('lab_row', 'Lab File Row', None, False)],
    'Notes': [
        ('cruise', 'Cruise', None, False), ('cast', 'Cast', 'All', False), ('niskin', 'Niskin', 'All', False),
        ('applies_to', 'Summary Flag Column', 'Summary Flag Columns', False), ('note', 'Note', None, True)],
}
# Column widths and number formats, taken from the reviewed Endurance-25 workbook (2026-10-23).
G, T = 'General', '@'
LAYOUT = {
    'README': {'Discrete Sample Transcription Workbook': (115, G)},
    'Cruise': {'Cruise': (15.71, G), 'Expedition': (14, G), 'Ship': (20.71, G),
               'Start Date [UTC YYYY-MM-DD]': (15.71, DATE_FORMAT), 'End Date [UTC YYYY-MM-DD]': (15.71, DATE_FORMAT),
               'Notes': (70.71, G)},
    'Cast Log': {'Cruise': (15.71, G), 'Cast': (7.71, G), 'Site': (7.71, G), 'Target Assets': (40.71, G),
                 'CTD File': (25.71, G), 'Cast Date [UTC YYYY-MM-DD]': (15.71, DATE_FORMAT),
                 'Start Time [UTC HH:MM]': (15.71, TIME_FORMAT), 'Start Latitude [deg]': (15.71, G),
                 'Start Latitude [min]': (15.71, '0.000'), 'Start Longitude [deg]': (15.71, G),
                 'Start Longitude [min]': (15.71, '0.000'), 'Start Water Depth [m]': (15.71, '0.0'),
                 'Cast Flag': (47.14, G), 'Cast Flag 2': (47.14, G), 'CTD File Flag': (44.29, G), 'Notes': (50, G),
                 'Transcription Check': (50, G)},
    'Niskin Log': {'Cruise': (8, G), 'Cast': (6, G), 'Niskin': (8, G), 'Trip Time [UTC HH:MM]': (23, TIME_FORMAT),
                   'Trip Depth [m]': (14.71, G), 'Temperature [deg C]': (14.71, G), 'Salinity [psu]': (14.71, G),
                   'Niskin Flag': (33.14, T), 'Notes': (50, T), 'Oxygen Samples': (16, T),
                   'Oxygen Draw Temperature [deg C]': (16.71, '0.00'), 'DIC/TA Samples': (16, T),
                   'Salinity Samples': (18, T), 'Nutrient Samples': (18, T), 'Chlorophyll Filters': (21, T),
                   'Chlorophyll Volume Filtered [mL]': (20.43, G), 'Transcription Check': (50, G)},
    'Sample Issues': {'Cruise': (15.71, G), 'Cast': (6, G), 'Niskin': (8, G), 'Analysis': (12, G),
                      'Sample ID': (10, G), 'Issue': (10, G), 'Sample Flag': (50.71, G), 'Reason': (60, G),
                      'Lab File': (44, G), 'Lab Sample Key': (16, G), 'Lab File Row': (12, G)},
    'Notes': {'Cruise': (8, G), 'Cast': (6, G), 'Niskin': (8, G), 'Summary Flag Column': (31.86, G),
              'Note': (50, G)},
    'Lists': {'Sites': (12, G), 'Analyses': (13, G), 'Sample Issue Types': (20, G), 'Cast Flags': (40, G),
              'CTD File Flags': (40, G), 'Niskin Flags': (34, G), 'Sample Flags': (40, G),
              'Summary Flag Columns': (28, G), 'All': (6, G)},
}
CENTERED = {'Cruise', 'Cast Log', 'Niskin Log', 'Sample Issues'}     # header and data centred, header wrapped
HEADER_HEIGHT = {'Cruise': 25.5, 'Cast Log': 25.5, 'Niskin Log': 42, 'Sample Issues': 25.5}

README = [
    'Discrete Sample Transcription Workbook',
    '',
    'One workbook per cruise: the hand-entered record from the paper Rosette Sampling Logs. CTD bottle data and lab '
    'results are read from their own files by the build tool.',
    '',
    'Cruise: one row.',
    'Cast Log: one row per CTD cast. Site is the OOI site as interpreted by the transcriber (e.g. CE09P is CE09). '
    'Start position as degrees + decimal minutes; longitude degrees are negative (west), e.g. -124 18.266. '
    'Start Water Depth is the bottom depth at the start position. Times are UTC, typed as HH:MM (the cells are '
    'formatted as times). If the log has no start time, use the "* NMEA UTC (Time)" line in the '
    '.btl header and say so in Notes.',
    'Niskin Log: one row per Niskin that was sampled or has a problem to record (leaked, empty, did not trip). '
    'Bottles fired but not sampled are left out. Each row is one row of the Discrete Summary and gets the trip '
    'time, trip depth, temperature and salinity written for its depth on the log.',
    'Sample numbers go on the Niskin row they were drawn from, as on the log: "49, 50, 51". A leaking or empty '
    'Niskin is never sampled; its samples go on the Niskin they were drawn from. Replicates are counted by the tool.',
    'Sample flags known at collection (e.g. a spilled flask) go on the Sample Issues sheet as a "flag" row: Cast, '
    'Niskin, Analysis, Sample ID, Sample Flag and Reason.',
    'Flags: leave blank when normal; pick from the list only when something went wrong and say why in Notes.',
    'Transcription Check: what the transcriber could not read or could not reconcile. The reviewer fixes the value '
    'and deletes the check.',
    'Sample Issues: one row per problem with a sample. flag = give it a Sample Flag (applied by the build); assign = '
    'put a lab result on a cast/Niskin/sample (for duplicate or wrong lab keys); exclude = ignore a lab row; review = '
    'undecided, blocks the build. Lab File and Lab Sample Key are only needed for assign/exclude; Lab File Row only '
    'to tell duplicate keys apart.',
    'Published in the summary README: Notes on any Cast Log or Niskin Log row that carries a flag, the Reason on '
    'Sample Issues "flag" rows, and every row of the Notes sheet. Notes on unflagged rows, Transcription Checks '
    'and the Reason on assign/exclude/review rows stay internal.',
    'Notes sheet: published text that does not belong to one flagged row, e.g. a cruise-wide event or one that '
    'affects a range of casts. Cast and Niskin take a number, a range (1-9) or All.',
    '',
    'Do not rename sheets or headers; the build tool reads them by name. Dropdown values are on the Lists sheet. '
    'Dropdown columns only accept values from their list. For a one-off site or value, add it directly under the '
    'last entry in its column on this workbook\'s Lists sheet (no blank rows); values used on many cruises are '
    'added to the template.',
]

_PLAIN = Font(name=FONT, size=SIZE)
_BOLD = Font(name=FONT, size=SIZE, bold=True)


def _sheet(wb: Workbook, name: str) -> None:
    ws = wb.create_sheet(name)
    for j, (_, header, list_name, _) in enumerate(SCHEMA[name], start=1):
        c = ws.cell(row=1, column=j, value=header)
        c.font, c.border = _BOLD, RULE
        if list_name:
            col = get_column_letter(list(LISTS).index(list_name) + 1)
            strict = list_name not in SOFT_LISTS   # list grows with entries added under it on Lists
            grow = f'=OFFSET(Lists!${col}$2,0,0,COUNTA(Lists!${col}:${col})-1,1)'
            dv = DataValidation(type='list', allow_blank=True, formula1=grow,
                                showErrorMessage=strict, errorStyle='stop', errorTitle=list_name,
                                error=f'Pick a value from the list. To add a new one, add it to the {list_name} '
                                      'column on the Lists sheet first.')
            letter = get_column_letter(j)
            dv.add(f'{letter}2:{letter}{MAX_ROWS}')
            ws.add_data_validation(dv)
        if TIME_TAG in header:
            letter = get_column_letter(j)
            dv = DataValidation(type='time', operator='between', formula1='0', formula2='0.999988426',
                                allow_blank=True, showErrorMessage=True, errorTitle='Time',
                                error='Enter a UTC time as HH:MM, e.g. 19:36')
            dv.add(f'{letter}2:{letter}{MAX_ROWS}')
            ws.add_data_validation(dv)
        if DATE_TAG in header:
            letter = get_column_letter(j)
            dv = DataValidation(type='date', operator='between', formula1='36526', formula2='73050',
                                allow_blank=True, showErrorMessage=True, errorTitle='Date',
                                error='Enter a UTC date as YYYY-MM-DD, e.g. 2026-10-03')
            dv.add(f'{letter}2:{letter}{MAX_ROWS}')
            ws.add_data_validation(dv)
    ws.freeze_panes = 'A2'


def make_workbook() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = 'README'
    for r, text in enumerate(README, start=1):
        ws.cell(row=r, column=1, value=text).font = _BOLD if r == 1 else _PLAIN
    ws.column_dimensions['A'].width = 115
    for name in SCHEMA:
        _sheet(wb, name)
    lists = wb.create_sheet('Lists')
    for j, (name, values) in enumerate(LISTS.items(), start=1):
        c = lists.cell(row=1, column=j, value=name)
        c.font, c.border = _BOLD, RULE
        for i, v in enumerate(values, start=2):
            lists.cell(row=i, column=j, value=v).font = _PLAIN
    finish(wb)
    wb.active = 0
    return wb


def finish(wb: Workbook) -> None:
    """Fonts, widths, number formats and alignment on every sheet (see LAYOUT)."""
    for name in [*SCHEMA, 'Lists']:
        ws = wb[name]
        centred = name in CENTERED
        wrap_cols = {j for j, s in enumerate(SCHEMA.get(name, []), start=1) if s[3]}
        for j in range(1, ws.max_column + 1):
            letter = get_column_letter(j)
            header = ws.cell(row=1, column=j)
            width, fmt = LAYOUT[name].get(header.value, (TEXT_W if j in wrap_cols else 13, 'General'))
            dim = ws.column_dimensions[letter]
            dim.width, dim.number_format = width, fmt
            if centred:
                header.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                cell_align = Alignment(horizontal='center', vertical='center', wrap_text=j in wrap_cols or None)
            else:
                cell_align = Alignment(wrap_text=j in wrap_cols, vertical='top')
            dim.font, dim.alignment = _PLAIN, cell_align     # rows typed later pick these up
            for c in ws[letter][1:]:
                c.font = _PLAIN
                c.alignment = cell_align
                c.number_format = fmt
        if name in HEADER_HEIGHT:
            ws.row_dimensions[1].height = HEADER_HEIGHT[name]


def to_time(value: str | time | datetime) -> time:
    """Return a time of day from HHMM, HH:MM, HH:MM:SS or a time/datetime."""
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    text = str(value).strip()
    m = re.fullmatch(r'(\d{1,2}):?(\d{2})(?::(\d{2}))?', text)
    if not m:
        raise ValueError(f'not a time: {value!r}')
    return time(int(m[1]), int(m[2]), int(m[3] or 0))


def to_date(value: str | date | datetime) -> datetime:
    """Return a date (as a midnight datetime for Excel) from YYYY-MM-DD or a date."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.strptime(str(value).strip()[:10], '%Y-%m-%d')


GROUP_FIELDS = ('trip_time_utc', 'temp_c', 'salinity_psu')


def fill_groups(rows: list[dict]) -> list[dict]:
    """Give every bottle in a group the values written on its first bottle.

    Rows are in log order. A blank Trip Depth, Temperature or Salinity
    takes the value of the previous row of the same cast (the first bottle
    of the group). Older logs give each duplicate its own trip depth but no
    temperature or salinity, so the fields are filled independently. Only
    valid on a complete log (every bottle of each group present).
    """
    prev = {}
    for row in rows:
        key = (row.get('cruise'), row.get('cast'))
        last = prev.get(key)
        if last:
            for f in ('trip_depth_m', *GROUP_FIELDS):
                if row.get(f) in (None, ''):
                    row[f] = last.get(f)
        prev[key] = row
    return rows


def prune_niskins(rows: list[dict]) -> list[dict]:
    """Fill each group from its first bottle, then keep only Niskins that
    were sampled or carry a Niskin Flag.

    Comments and checks on a dropped row move to the previous kept row of
    the same cast (or the next one if none precedes it).
    """
    rows = fill_groups(rows)
    keep = [any(r.get(c) for c in SAMPLE_COLS.values()) or bool(r.get('niskin_flag')) for r in rows]
    for i, row in enumerate(rows):
        if keep[i] or not (row.get('notes') or row.get('check')):
            continue
        same = [j for j in range(len(rows)) if keep[j] and rows[j].get('cast') == row.get('cast')
                and rows[j].get('cruise') == row.get('cruise')]
        before = [j for j in same if j < i]
        if not same:
            raise WorkbookError(f'cast {row.get("cast")}: nowhere to keep the note on Niskin {row.get("niskin")}')
        target = rows[before[-1] if before else same[0]]
        for k in ('notes', 'check'):
            if row.get(k):
                target[k] = _join([target.get(k), f'Niskin {row["niskin"]}: {row[k]}'], '; ')
    return [r for r, k in zip(rows, keep) if k]


NUMERIC_KEYS = {'volume_ml', 'draw_temp_c', 'trip_depth_m', 'temp_c', 'salinity_psu'}


def to_number(value: str) -> int | float:
    """Return a number typed as text (e.g. '100' in a text-formatted cell)."""
    v = float(value.strip())
    return int(v) if v.is_integer() else v


def write_rows(ws, rows: list[dict]) -> None:
    spec = SCHEMA[ws.title]
    for r, row in enumerate(rows, start=2):
        for j, (k, header, *_) in enumerate(spec, start=1):
            v = row.get(k)
            if v not in (None, ''):
                if k in NUMERIC_KEYS and isinstance(v, str):
                    v = to_number(v)
                if TIME_TAG in header:
                    v = to_time(v)
                elif DATE_TAG in header:
                    v = to_date(v)
                ws.cell(row=r, column=j, value=v)


# analysis -> Niskin Log column holding its comma separated sample numbers
SAMPLE_COLS = {'oxygen': 'oxygen_samples', 'dic_ta': 'dic_ta_samples', 'salinity': 'salinity_samples',
               'nutrients': 'nutrient_samples', 'chlorophyll': 'chl_filters'}
LIST_COLS = {*SAMPLE_COLS.values(), 'brown_bottle'}
# per-sample layout used before 2026-10-22 (read by migrate only)
OLD_SAMPLE_HEADERS = {'Cruise': 'cruise', 'Cast': 'cast', 'Niskin': 'niskin', 'Analysis': 'analysis',
                      'Sample ID': 'sample_id', 'Oxygen Draw Temperature [deg C]': 'draw_temp_c',
                      'Chlorophyll Brown Bottle': 'brown_bottle', 'Chlorophyll Volume Filtered [mL]': 'volume_ml',
                      'Sample Source': 'source', 'Sample Flag': 'sample_flag', 'Notes': 'notes',
                      'Transcription Check': 'check'}


def _join(values: list, sep: str = ', ') -> str:
    out = []
    for v in values:
        if v not in (None, '') and v not in out:
            out.append(v)
    return sep.join(str(v) for v in out)


def merge_samples(niskins: list[dict], samples: list[dict]) -> tuple[list[dict], list[dict]]:
    """Fold one-row-per-sample records into the Niskin rows.

    Returns the Niskin rows and Sample Issues "flag" rows for any sample
    flags. A sample on a Niskin that has no Niskin row stops the run.
    """
    by_key = {(r['cruise'], r['cast'], r['niskin']): r for r in niskins}
    grouped: dict[tuple, list[dict]] = {}
    flags = []
    for s in samples:
        key = (s['cruise'], s['cast'], s['niskin'])
        if key not in by_key:
            raise WorkbookError(f'sample {s["analysis"]} {s["sample_id"]} is on {key}, which has no Niskin row')
        grouped.setdefault(key, []).append(s)
        if s.get('sample_flag'):
            flags.append(dict(cruise=s['cruise'], analysis=s['analysis'], action='flag', cast=s['cast'],
                              niskin=s['niskin'], sample_id=s['sample_id'], sample_flag=s['sample_flag'],
                              reason=s.get('notes'), decided_by='Field (sampling log)'))
    for key, rows in grouped.items():
        n = by_key[key]
        for analysis, col in SAMPLE_COLS.items():
            ids = sorted((r['sample_id'] for r in rows if r['analysis'] == analysis), key=lambda v: (str(type(v)), v))
            if ids:
                n[col] = _join(ids)
        for col in ('draw_temp_c', 'volume_ml'):
            vals = [r.get(col) for r in rows if r.get(col) not in (None, '')]
            if len(set(vals)) > 1:
                n['check'] = _join([n.get('check'), f'{col} differs between samples: {_join(vals)}'], '; ')
            if vals:
                n[col] = vals[0]
        n['brown_bottle'] = _join([r.get('brown_bottle') for r in rows]) or None
        notes = [r.get('notes') for r in rows if not r.get('sample_flag')]
        n['notes'] = _join([n.get('notes'), *notes], '; ') or None
        by_check: dict[tuple, list] = {}
        for r in rows:
            if r.get('check'):
                by_check.setdefault((r['analysis'], r['check']), []).append(r['sample_id'])
        checks = [f'{a} {_join(ids)}: {text}' for (a, text), ids in by_check.items()]
        n['check'] = _join([n.get('check'), *checks], '; ') or None
    return niskins, flags


# Layout history: what migrate drops or renames when it reads an older workbook.
_DONE = {'Check Resolution', 'Resolved By'}
SHEET_RENAMED = {'Corrections': 'Sample Issues'}
RETIRED = {'Cast Log': {'Cast Purpose', 'Operator', 'Flow-Through Active [Y/N]', 'Site as Written',
                        'Start CTD Depth [m]', 'Altimeter [m]',
                        *(f'{p} {h}' for p in ('Bottom', 'End') for _, h in _POS), *_DONE},
           'Niskin Log': {'Target Depth [m, Btm or Sfc]', 'Chlorophyll Brown Bottle', *_DONE},
           'Cruise': {'Transcribed On', 'Source Document(s)', 'Transcribed By', 'Reviewed By'},
           'Sample Issues': {'Decided By', 'Decision Date'}, 'Lists': set()}
RENAMED = {'Sample Issues': {'Action': 'Issue'},
           'Cruise': {'Source Document': 'Source Document(s)', 'Start Date': 'Start Date [UTC YYYY-MM-DD]',
                     'End Date': 'End Date [UTC YYYY-MM-DD]'},
           'Cast Log': {'Start Longitude [deg W]': 'Start Longitude [deg]', 'Station': 'Site',
                        'Start Time [UTC HHMM]': 'Start Time [UTC HH:MM]',
                        'Cast Date [UTC]': 'Cast Date [UTC YYYY-MM-DD]'},
           'Niskin Log': {'Potential Temperature [deg C]': 'Temperature [deg C]', 'Comments': 'Notes',
                          'Trip Time [UTC HHMM]': 'Trip Time [UTC HH:MM]'}}


def migrate(src: str | Path) -> Workbook:
    """Move a filled workbook to the current layout, matching by header.

    Renamed headers follow RENAMED; headers in RETIRED are dropped. Any
    other header with no home stops the run rather than being dropped.
    """
    old = load_workbook(src)
    wb = make_workbook()
    sheets: dict[str, list[dict]] = {}
    samples: list[dict] = []
    for name in old.sheetnames:
        if name in ('README', 'Lists'):
            continue
        ows = old[name]
        name = SHEET_RENAMED.get(name, name)
        if name == 'Sample Log':
            headers = [c.value for c in ows[1]]
            lost = [h for h in headers if h is not None and h not in OLD_SAMPLE_HEADERS and h not in _DONE]
            if lost:
                raise WorkbookError(f'{name}: columns {lost} have no place in the new layout')
            for r in ows.iter_rows(min_row=2, values_only=True):
                old_row = dict(zip(headers, r))
                if not any(v not in (None, '') for v in r):
                    continue
                row = {OLD_SAMPLE_HEADERS[h]: v for h, v in old_row.items() if h in OLD_SAMPLE_HEADERS}
                if old_row.get('Check Resolution'):
                    text = f"{old_row.get('Transcription Check') or ''} {old_row['Check Resolution']}".strip()
                    row['notes'], row['check'] = _join([row.get('notes'), text], '; '), None
                samples.append(row)
            continue
        ren = RENAMED.get(name, {})
        headers = [ren.get(c.value, c.value) for c in ows[1]]
        by_header = {h: k for k, h, *_ in SCHEMA[name]}
        lost = [h for h in headers if h is not None and h not in by_header and h not in RETIRED.get(name, set())]
        if lost:
            raise WorkbookError(f'{name}: columns {lost} have no place in the new layout')
        rows = []
        for r in ows.iter_rows(min_row=2, values_only=True):
            if not any(v not in (None, '') for v in r):
                continue
            old_row = dict(zip(headers, r))
            row = {by_header[h]: v for h, v in old_row.items() if h in by_header}
            if old_row.get('Check Resolution'):
                # resolved check: keep the record in the notes, drop the open check
                note_key = 'notes'
                text = f"{old_row.get('Transcription Check') or ''} {old_row['Check Resolution']}".strip()
                row[note_key] = f"{row[note_key]} {text}" if row.get(note_key) else text
                row['check'] = None
            rows.append(row)
        sheets[name] = rows
    if samples:
        sheets['Niskin Log'], flags = merge_samples(sheets.get('Niskin Log', []), samples)
        sheets['Sample Issues'] = [*sheets.get('Sample Issues', []), *flags]
    if 'Niskin Log' in sheets:
        sheets['Niskin Log'] = prune_niskins(sheets['Niskin Log'])
    for name, rows in sheets.items():
        write_rows(wb[name], rows)
    finish(wb)
    wb.active = 0
    return wb


def read_workbook(path: str | Path) -> dict[str, list[dict]]:
    """Return every data sheet as a list of {header: value} rows.

    Raises
    ------
    WorkbookError
        If a sheet is missing or its headers differ from SCHEMA.
    """
    wb = load_workbook(path, data_only=True)
    out = {}
    for name, spec in SCHEMA.items():
        if name not in wb.sheetnames:
            raise WorkbookError(f'{Path(path).name}: sheet {name!r} is missing')
        ws = wb[name]
        headers = [c.value for c in ws[1] if c.value is not None]
        expected = [h for _, h, *_ in spec]
        if headers != expected:
            raise WorkbookError(f'{Path(path).name}, {name}: headers {headers} differ from {expected}; '
                                'run migrate first')
        out[name] = [dict(zip(headers, r)) for r in ws.iter_rows(min_row=2, max_col=len(headers), values_only=True)
                     if any(v not in (None, '') for v in r)]
    return out
