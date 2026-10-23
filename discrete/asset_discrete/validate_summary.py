"""Format/content validator for OOI Discrete Summary CSV files.

Checks a finished summary file against the OOI-wide template, flag
definitions (reference/) and a set of physical/consistency rules,
independent of how the file was produced: ours, historic ones, or another
array's. Each finding is an Issue (file, line, column, severity, code,
value, message); the CLI writes them to a CSV.
"""
from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from asset_discrete import REFERENCE

FILL = '-9999999'
FILL_LIKE = {'-9.999', '-9.99', '-99', '-999', '-9999', '-99999', '-999999', '-99999999', '-9999999.0', 'NaN',
             'nan', 'NA', 'N/A'}
FLAG_RE = re.compile(r'^\*[01]{16}$')
TIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
LAT_BOUNDS, LON_BOUNDS = (40.0, 50.0), (-130.0, -120.0)
MAX_NISKIN = 36

TEXT_COLS = {'Cruise', 'Station', 'Target Asset', 'Start Time [UTC]', 'Cast', 'CTD File',
             'CTD Bottle Closure Time [UTC]'}
META_COLS = ['Cruise', 'Station', 'Target Asset', 'Start Latitude [degrees]', 'Start Longitude [degrees]',
             'Start Time [UTC]', 'Cast', 'Cast Flag', 'Bottom Depth at Start Position [m]', 'CTD File',
             'CTD File Flag']

# flag column -> value columns it qualifies
FLAG_VALUES = {
    'CTD Pressure Flag': ['CTD Pressure [db]'],
    'CTD Temperature 1 Flag': ['CTD Temperature 1 [deg C]'],
    'CTD Temperature 2 Flag': ['CTD Temperature 2 [deg C]'],
    'CTD Conductivity 1 Flag': ['CTD Conductivity 1 [S/m]'],
    'CTD Conductivity 2 Flag': ['CTD Conductivity 2 [S/m]'],
    'CTD Oxygen Flag': ['CTD Oxygen [mL/L]'],
    'CTD Fluorescence Flag': ['CTD Fluorescence [mg/m^3]'],
    'CTD Transmissometer Flag': ['CTD Beam Attenuation [1/m]', 'CTD Beam Transmission [%]'],
    'CTD pH Flag': ['CTD pH'],
    'Discrete Oxygen Flag': ['Discrete Oxygen [mL/L]'],
    'Discrete Fluorescence Flag': ['Discrete Chlorophyll [ug/L]', 'Discrete Phaeopigment [ug/L]',
                                   'Discrete Fo/Fa Ratio'],
    'Discrete Nutrients Flag': ['Discrete Phosphate [uM]', 'Discrete Silicate [uM]', 'Discrete Nitrate [uM]',
                                'Discrete Nitrite [uM]', 'Discrete Ammonium [uM]'],
    'Discrete Salinity Flag': ['Discrete Salinity [psu]'],
    'Discrete Alkalinity Flag': ['Discrete Alkalinity [umol/kg]'],
    'Discrete DIC Flag': ['Discrete DIC [umol/kg]'],
    'Discrete pCO2 Flag': ['Discrete pCO2 [uatm]'],
    'Discrete pH Flag': ['Discrete pH [Total scale]'],
}
FLAG_VALUE_OF = {v: f for f, vs in FLAG_VALUES.items() for v in vs}
FLAG_VALUE_OF['Calculated pH'] = 'Discrete pH Flag'
REPLICATE = {f'Discrete {k} Replicate Flag': f'Discrete {k} Flag'
             for k in ('Oxygen', 'Fluorescence', 'Nutrients', 'Salinity', 'Alkalinity', 'DIC', 'pCO2', 'pH')}
# discrete value -> CTD flags that should carry bit 7 (corresponding discrete sample), per row
CTD_MATCH = {'Discrete Salinity [psu]': ['CTD Conductivity 1 Flag', 'CTD Conductivity 2 Flag'],
             'Discrete Oxygen [mL/L]': ['CTD Oxygen Flag'],
             'Discrete Chlorophyll [ug/L]': ['CTD Fluorescence Flag'],
             'Discrete pH [Total scale]': ['CTD pH Flag'],
             'Calculated pH': ['CTD pH Flag']}

RANGES = {
    'Bottom Depth at Start Position [m]': (1, 6000), 'CTD Pressure [db]': (0, 6000), 'CTD Depth [m]': (0, 6000),
    'CTD Temperature 1 [deg C]': (-2, 30), 'CTD Temperature 2 [deg C]': (-2, 30),
    'CTD Conductivity 1 [S/m]': (0, 7), 'CTD Conductivity 2 [S/m]': (0, 7),
    'CTD Salinity 1 [psu]': (0, 40), 'CTD Salinity 2 [psu]': (0, 40),
    'CTD Oxygen [mL/L]': (0, 12), 'CTD Oxygen Saturation [mL/L]': (0, 12),
    'CTD Fluorescence [mg/m^3]': (-0.5, 60), 'CTD Beam Attenuation [1/m]': (0, 20),
    'CTD Beam Transmission [%]': (1, 100), 'CTD pH': (6.5, 9),
    'Discrete Oxygen [mL/L]': (0, 12), 'Discrete Chlorophyll [ug/L]': (-0.05, 60),
    'Discrete Phaeopigment [ug/L]': (-0.5, 30), 'Discrete Fo/Fa Ratio': (0.5, 2.5),
    'Discrete Phosphate [uM]': (-0.1, 4), 'Discrete Silicate [uM]': (-0.5, 200), 'Discrete Nitrate [uM]': (-0.1, 50),
    'Discrete Nitrite [uM]': (-0.1, 5), 'Discrete Ammonium [uM]': (-0.2, 20), 'Discrete Salinity [psu]': (0, 40),
    'Discrete Alkalinity [umol/kg]': (1500, 2600), 'Discrete DIC [umol/kg]': (1500, 2600),
    'Discrete pCO2 [uatm]': (50, 3000), 'pCO2 Analysis Temp [deg C]': (10, 35),
    'Discrete pH [Total scale]': (7, 8.6), 'pH Analysis Temp [deg C]': (10, 35),
    'Calculated Alkalinity [umol/kg]': (1500, 2600), 'Calculated DIC [umol/kg]': (1500, 2600),
    'Calculated pCO2 [uatm]': (50, 3000), 'Calculated pH': (7, 8.6), 'Calculated CO2aq [umol/kg]': (0, 150),
    'Calculated Bicarb [umol/kg]': (1000, 2600), 'Calculated CO3 [umol/kg]': (0, 400),
    'Calculated Omega-C': (0, 10), 'Calculated Omega-A': (0, 10),
}


@dataclass
class Issue:
    file: str
    line: int
    column: str
    severity: str
    code: str
    value: str
    message: str


def bits(flag: str) -> set[int]:
    """Set bit positions (0 = rightmost) of a '*0101...' flag string."""
    return {15 - i for i, ch in enumerate(flag[1:]) if ch == '1'}


def num(v: str) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def present(v: str) -> bool:
    return v not in (None, '', FILL)


def parse_time(v: str) -> datetime | None:
    try:
        return datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%fZ')
    except (TypeError, ValueError):
        return None


def sig_digits(v: str) -> int:
    s = v.lstrip('-+').lower().split('e')[0].replace('.', '').lstrip('0')
    return len(s)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


class Validator:
    """Checks summary files against the reference tables and a cruise list.

    Parameters
    ----------
    cruises : dict or None
        CUID -> (start, stop) datetimes, normally from asset-management
        cruise/CruiseInformation.csv (see `read_cruises`). None skips the
        cruise checks.
    ref : Path
        Folder with discreteSummary_template.csv, flags.csv, flagMap.csv
        and stations.csv; the package's reference/ folder by default.
    """

    def __init__(self, cruises: dict[str, tuple[datetime, datetime]] | None, ref: Path = REFERENCE):
        with open(ref / 'discreteSummary_template.csv', encoding='utf-8-sig', newline='') as f:
            self.template = next(csv.reader(f))
        flag_names: dict[str, dict[int, str]] = defaultdict(dict)
        with open(ref / 'flags.csv', encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                pos = int(r.pop('bitPosition'))
                for k, v in r.items():
                    flag_names[k][pos] = v
        with open(ref / 'flagMap.csv', encoding='utf-8-sig', newline='') as f:
            self.flag_type = {r['header']: r['flagType'] for r in csv.DictReader(f)}
        self.flag_names = flag_names
        with open(ref / 'stations.csv', encoding='utf-8-sig', newline='') as f:
            self.stations = {r['station'].strip() for r in csv.DictReader(f) if r['station'].strip()}
        self.cruises = cruises

    def check(self, path: Path) -> list[Issue]:
        name = path.name
        out: list[Issue] = []

        def add(line: int, col: str, sev: str, code: str, val: str, msg: str) -> None:
            out.append(Issue(name, line, col, sev, code, str(val)[:60], msg))

        raw = path.read_bytes()
        if raw.startswith(b'\xef\xbb\xbf'):
            add(1, '', 'INFO', 'ENC_BOM', '', 'file starts with a UTF-8 byte order mark')
        if b'\r\n' in raw:
            add(1, '', 'INFO', 'ENC_CRLF', '', 'CRLF line endings')
        with open(path, encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = [r for r in reader]

        if header != self.template:
            missing = [h for h in self.template if h not in header]
            extra = [h for h in header if h not in self.template]
            add(1, '', 'ERROR', 'HEADER', '', f'header differs from template; missing={missing} extra={extra}')
            if missing:
                return out
        recs = []
        for i, r in enumerate(rows):
            line = i + 2
            if len(r) != len(header):
                add(line, '', 'ERROR', 'ROW_LENGTH', len(r), f'{len(r)} fields, header has {len(header)}')
                continue
            if not any(c.strip() for c in r):
                add(line, '', 'WARN', 'BLANK_ROW', '', 'empty row')
                continue
            recs.append((line, dict(zip(header, r))))

        for line, rec in recs:
            self._row(line, rec, add)
        self._casts(recs, add)
        self._replicates(recs, add)
        c = Counter(tuple(rec.values()) for _, rec in recs)
        for line, rec in recs:
            if c[tuple(rec.values())] > 1:
                add(line, '', 'WARN', 'DUP_ROW', '', 'row is an exact duplicate of another row')
        return out

    # ------------------------------------------------------------------ rows
    def _row(self, line: int, rec: dict, add) -> None:
        for col, v in rec.items():
            if v is None or v.strip() == '':
                add(line, col, 'ERROR', 'EMPTY', v, 'empty cell (use -9999999)')
                continue
            if v != v.strip():
                add(line, col, 'WARN', 'WHITESPACE', v, 'leading/trailing whitespace')
            v = v.strip()
            is_flag = col.endswith('Flag')
            if v in FILL_LIKE or (v.startswith('-99') and v != FILL):
                add(line, col, 'ERROR', 'FILL_FORMAT', v, 'fill-like value is not exactly -9999999')
                continue
            if v == FILL:
                continue
            if is_flag:
                self._flag(line, col, v, add)
            elif FLAG_RE.match(v):
                add(line, col, 'ERROR', 'FLAG_MISPLACED', v, 'flag string in a non-flag column')
            elif col not in TEXT_COLS:
                x = num(v)
                if x is None:
                    add(line, col, 'ERROR', 'NOT_NUMBER', v, 'value does not parse as a number')
                    continue
                lo_hi = RANGES.get(col)
                if lo_hi and not lo_hi[0] <= x <= lo_hi[1] and not self._flagged_bad(rec, col):
                    add(line, col, 'WARN', 'RANGE', v, f'outside plausible range {lo_hi}')
                if sig_digits(v) > 8:
                    add(line, col, 'WARN', 'PRECISION', v, f'{sig_digits(v)} significant digits')

        cruise = rec['Cruise']
        window = self.cruises.get(cruise) if self.cruises is not None else None
        if self.cruises is not None and window is None:
            add(line, 'Cruise', 'ERROR', 'CRUISE_UNKNOWN', cruise, 'cruise not in CruiseInformation.csv')
        st = rec['Station'].strip()
        if present(st) and st not in self.stations:
            add(line, 'Station', 'WARN', 'STATION_UNKNOWN', st, 'station not in reference/stations.csv')
        n = rec['Niskin/Bottle Position']
        if present(n) and not (n.isdigit() and 1 <= int(n) <= MAX_NISKIN):
            add(line, 'Niskin/Bottle Position', 'ERROR', 'NISKIN', n, f'not an integer 1-{MAX_NISKIN}')

        times = {}
        for col in ('Start Time [UTC]', 'CTD Bottle Closure Time [UTC]'):
            v = rec[col]
            if not present(v):
                continue
            if not TIME_RE.match(v):
                add(line, col, 'ERROR', 'TIME_FORMAT', v, 'not YYYY-MM-DDTHH:MM:SS.sssZ')
            t = parse_time(v)
            if t is None:
                add(line, col, 'ERROR', 'TIME_PARSE', v, 'unparseable time')
                continue
            times[col] = t
            if window and not window[0] - timedelta(hours=12) <= t <= window[1] + timedelta(hours=12):
                add(line, col, 'ERROR', 'TIME_WINDOW', v, f'outside cruise window {window[0]} - {window[1]}')
        t0, t1 = times.get('Start Time [UTC]'), times.get('CTD Bottle Closure Time [UTC]')
        if t0 and t1:
            if t1 < t0:
                add(line, 'CTD Bottle Closure Time [UTC]', 'ERROR', 'CLOSE_BEFORE_START', rec['CTD Bottle Closure '
                    'Time [UTC]'], 'bottle closed before cast start')
            elif t1 - t0 > timedelta(hours=8):
                add(line, 'CTD Bottle Closure Time [UTC]', 'WARN', 'CLOSE_LATE', str(t1 - t0),
                    'bottle closed more than 8 h after cast start')

        lat, lon = num(rec['Start Latitude [degrees]']), num(rec['Start Longitude [degrees]'])
        for col, x, (lo, hi) in (('Start Latitude [degrees]', lat, LAT_BOUNDS), ('Start Longitude [degrees]', lon,
                                                                                  LON_BOUNDS),
                                 ('CTD Latitude [deg]', num(rec['CTD Latitude [deg]']), LAT_BOUNDS),
                                 ('CTD Longitude [deg]', num(rec['CTD Longitude [deg]']), LON_BOUNDS)):
            if x is not None and present(rec[col]) and not lo <= x <= hi:
                add(line, col, 'ERROR', 'POSITION', rec[col], f'outside {lo}..{hi}')
        clat, clon = num(rec['CTD Latitude [deg]']), num(rec['CTD Longitude [deg]'])
        if None not in (lat, lon, clat, clon) and all(present(rec[c]) for c in ('Start Latitude [degrees]',
                                                                                'CTD Latitude [deg]')):
            d = haversine_km(lat, lon, clat, clon)
            if d > 5:
                add(line, 'CTD Latitude [deg]', 'WARN', 'POSITION_DRIFT', f'{d:.1f} km',
                    'bottle position more than 5 km from cast start')

        p, z = num(rec['CTD Pressure [db]']), num(rec['CTD Depth [m]'])
        if present(rec['CTD Pressure [db]']) and present(rec['CTD Depth [m]']) and p and z and p > 5:
            if not 0.975 <= z / p <= 0.999:
                add(line, 'CTD Depth [m]', 'WARN', 'DEPTH_PRESSURE', f'{z}/{p}', 'depth/pressure ratio implausible')
        bd = num(rec['Bottom Depth at Start Position [m]'])
        if z is not None and bd is not None and present(rec['CTD Depth [m]']) and present(
                rec['Bottom Depth at Start Position [m]']) and bd > 0 and z > bd + 10:
            add(line, 'CTD Depth [m]', 'WARN', 'BELOW_BOTTOM', f'{z} > {bd}', 'bottle deeper than bottom depth')

        c_att, tr = rec['CTD Beam Attenuation [1/m]'], rec['CTD Beam Transmission [%]']
        if present(c_att) and present(tr):
            a, t = num(c_att), num(tr)
            if a is not None and t is not None and t > 0:
                expect = -4.0 * math.log(t / 100.0)
                if abs(a - expect) > max(0.05, 0.05 * expect):
                    add(line, 'CTD Beam Attenuation [1/m]', 'ERROR', 'BEAM_INCONSISTENT', f'c={a} T={t}',
                        f'attenuation should be about {expect:.3f} for T={t}% (25 cm path); columns swapped?')

        ds, cs = num(rec['Discrete Salinity [psu]']), num(rec['CTD Salinity 1 [psu]'])
        if present(rec['Discrete Salinity [psu]']) and present(rec['CTD Salinity 1 [psu]']) and None not in (ds, cs):
            if abs(ds - cs) > 0.1:
                add(line, 'Discrete Salinity [psu]', 'WARN', 'SAL_VS_CTD', f'{ds} vs {cs}',
                    'discrete salinity differs from CTD by > 0.1')
        do, co = num(rec['Discrete Oxygen [mL/L]']), num(rec['CTD Oxygen [mL/L]'])
        if present(rec['Discrete Oxygen [mL/L]']) and present(rec['CTD Oxygen [mL/L]']) and None not in (do, co):
            if abs(do - co) > max(0.5, 0.15 * co):
                add(line, 'Discrete Oxygen [mL/L]', 'WARN', 'O2_VS_CTD', f'{do} vs {co}',
                    'discrete oxygen differs from CTD by > max(0.5 mL/L, 15%)')

        # value <-> flag consistency
        for fcol, vcols in FLAG_VALUES.items():
            fv = rec[fcol].strip()
            has_val = any(present(rec[c].strip()) for c in vcols)
            if not FLAG_RE.match(fv):
                if has_val and fv == FILL:
                    add(line, fcol, 'ERROR', 'FLAG_MISSING', fv, 'value present but flag is fill')
                continue
            b = bits(fv)
            disc = fcol.startswith('Discrete')
            if has_val and disc and 1 in b:
                add(line, fcol, 'ERROR', 'FLAG_SAYS_NOT_RECEIVED', fv,
                    'value present but flag says analysis not received')
            if has_val and disc and 9 in b:
                add(line, fcol, 'ERROR', 'FLAG_SAYS_NOT_DRAWN', fv, 'value present but flag says sample not drawn')
            if not has_val and 2 in b:
                add(line, fcol, 'ERROR', 'FLAG_WITHOUT_VALUE', fv, 'flag says acceptable but value is fill')
            if 2 in b and b & {3, 4}:
                add(line, fcol, 'ERROR', 'FLAG_CONTRADICTION', fv, 'acceptable and questionable/bad both set')
            if 2 not in b and not b & {1, 3, 4, 5, 6, 7, 9} and has_val:
                add(line, fcol, 'WARN', 'FLAG_NO_QUALITY', fv, 'value present but no quality bit set')


    @staticmethod
    def _flagged_bad(rec: dict, col: str) -> bool:
        """True when the flag column qualifying ``col`` marks it questionable/bad."""
        for fcol, vcols in FLAG_VALUES.items():
            if col in vcols:
                fv = rec[fcol].strip()
                return bool(FLAG_RE.match(fv) and bits(fv) & {3, 4})
        return False

    def _flag(self, line: int, col: str, v: str, add) -> None:
        if not FLAG_RE.match(v):
            add(line, col, 'ERROR', 'FLAG_FORMAT', v, 'not * followed by 16 zeros/ones')
            return
        b = bits(v)
        if not b:
            add(line, col, 'ERROR', 'FLAG_BLANK', v, 'no bits set')
            return
        ftype = self.flag_type.get(col)
        if ftype is None:
            add(line, col, 'ERROR', 'FLAG_UNMAPPED', v, 'column not in flagMap.csv')
            return
        for pos in sorted(b):
            if 'Unassigned' in self.flag_names[ftype].get(pos, 'Unassigned'):
                add(line, col, 'ERROR', 'FLAG_UNASSIGNED_BIT', v, f'bit {pos} is unassigned for {ftype}')

    # ----------------------------------------------------------------- casts
    def _casts(self, recs: list, add) -> None:
        groups = defaultdict(list)
        for line, rec in recs:
            groups[(rec['Cruise'], rec['Cast'], rec['CTD File'].strip())].append((line, rec))
        seen = defaultdict(set)
        for (cruise, cast, ctd) in groups:
            seen[(cruise, cast)].add(ctd)
        for (cruise, cast), files in seen.items():
            if len(files) > 1:
                add(0, 'Cast', 'WARN', 'CAST_NUMBER_REUSED', cast,
                    f'{cruise} cast {cast} used for {len(files)} CTD files: {sorted(files)}')
        for (cruise, cast, _), rows in groups.items():
            for col in META_COLS:
                norm = (lambda v: v.strip()) if col in TEXT_COLS or col.endswith('Flag') else (
                    lambda v: repr(num(v)) if num(v) is not None else v.strip())
                vals = Counter(norm(r[col]) for _, r in rows)
                if len(vals) > 1:
                    common = vals.most_common(1)[0][0]
                    for line, r in rows:
                        if norm(r[col]) != common:
                            add(line, col, 'ERROR', 'CAST_META_DIFFERS', r[col],
                                f'cast {cruise}/{cast}: most rows have {common!r}')
            fl = rows[0][1]['CTD File Flag'].strip()
            if FLAG_RE.match(fl) and 1 in bits(fl):
                for line, r in rows:
                    for col, v in r.items():
                        if col not in META_COLS and present(v.strip()):
                            add(line, col, 'ERROR', 'DATA_ONLY_HAS_VALUES', v,
                                'CTD file flag says no Niskins triggered')
                            break
            closures = defaultdict(set)
            for line, r in rows:
                closures[r['Niskin/Bottle Position']].add(r['CTD Bottle Closure Time [UTC]'])
            for n, ts in closures.items():
                if len(ts) > 1:
                    add(rows[0][0], 'CTD Bottle Closure Time [UTC]', 'ERROR', 'NISKIN_CTD_DIFFERS', '|'.join(ts),
                        f'cast {cast} Niskin {n} rows disagree on closure time')

    def _ctd_match(self, groups: dict, add) -> None:
        """Bit 7 (corresponding discrete sample) on CTD flags, per Niskin.

        The row holding the discrete value must carry bit 7. Other rows of the
        same Niskin may carry it or not (both conventions exist). A Niskin
        with no discrete value at all must not carry it.
        """
        fcols = sorted({f for fs in CTD_MATCH.values() for f in fs})
        for key, rows in groups.items():
            for fcol in fcols:
                dcols = [d for d, fs in CTD_MATCH.items() if fcol in fs]
                dflags = {FLAG_VALUE_OF[d] for d in dcols}
                niskin_has = any(present(r[d].strip()) for _, r in rows for d in dcols) or any(
                    FLAG_RE.match(r[f].strip()) and bits(r[f].strip()) & {1, 3, 4} for _, r in rows for f in dflags)
                for line, r in rows:
                    fv = r[fcol].strip()
                    if not FLAG_RE.match(fv):
                        continue
                    row_has = any(present(r[d].strip()) for d in dcols)
                    if row_has and 7 not in bits(fv):
                        add(line, fcol, 'ERROR', 'CTD_MATCH_MISSING', fv,
                            f'{"/".join(dcols)} present on this row but bit 7 not set')
                    if not niskin_has and 7 in bits(fv):
                        add(line, fcol, 'ERROR', 'CTD_MATCH_EXTRA', fv,
                            'bit 7 set but this Niskin has no discrete sample (no value, not-received or bad flag)')

    def _replicates(self, recs: list, add) -> None:
        groups = defaultdict(list)
        for line, rec in recs:
            groups[(rec['Cruise'], rec['Cast'], rec['CTD File'].strip(), rec['Niskin/Bottle Position'])].append(
                (line, rec))
        self._ctd_match(groups, add)
        for rcol, fcol in REPLICATE.items():
            vcols = FLAG_VALUES[fcol]
            for key, rows in groups.items():
                with_val = [(line, r) for line, r in rows if any(present(r[c].strip()) for c in vcols)]
                n = len(with_val)
                for line, r in with_val:
                    fv = r[rcol].strip()
                    if not FLAG_RE.match(fv):
                        add(line, rcol, 'ERROR', 'REPL_FLAG_MISSING', fv, 'value present but replicate flag missing')
                        continue
                    b = bits(fv)
                    expect = {1: 2, 2: 3, 3: 4}.get(n)
                    if 1 in b:      # duplicate analysis on same sample: accept any count
                        continue
                    if expect is None or expect not in b:
                        add(line, rcol, 'ERROR', 'REPL_COUNT', fv,
                            f'{n} value row(s) for cast {key[1]} Niskin {key[3]}; expected bit {expect}')


def read_cruises(asset_management: str | Path) -> dict[str, tuple[datetime, datetime]]:
    """CUID -> (start, stop) from asset-management cruise/CruiseInformation.csv."""
    path = Path(asset_management) / 'cruise' / 'CruiseInformation.csv'
    with open(path, encoding='utf-8-sig', newline='') as f:
        return {r['CUID']: (datetime.fromisoformat(r['cruiseStartDateTime']),
                            datetime.fromisoformat(r['cruiseStopDateTime']))
                for r in csv.DictReader(f)}


def write_issues(issues: list[Issue], out: str | Path) -> None:
    """Write findings as CSV (file, line, column, severity, code, value, message)."""
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['file', 'line', 'column', 'severity', 'code', 'value', 'message'])
        for i in issues:
            w.writerow([i.file, i.line, i.column, i.severity, i.code, i.value, i.message])
