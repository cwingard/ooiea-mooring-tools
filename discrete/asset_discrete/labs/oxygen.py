"""Scripps ODF dissolved oxygen listing (.LST).

The ODF titrator software writes a fixed header (expedition, chemist, iodate
and thiosulfate standardisation, blank) followed by one line per flask:

    Sta Cst Bot Flask FlaskVol RawTiter Titer20 O2[ml/l] ThioTemp DrawTemp EndVolts TitrTime [comments]

O2 is already calculated in mL/L, the unit of the summary column, so the
reported text is used as is. Anything after the titration time is a lab
comment (for example 'OT 0.2810'); it is kept for the build log and not
interpreted.
"""
from __future__ import annotations

import re
from pathlib import Path

from asset_discrete.labs import LabError, LabFile, LabResult

VALUE_COLUMN = 'Discrete Oxygen [mL/L]'
ROW = re.compile(r'^(?P<sta>\d+)\s+(?P<cast>\d+)\s+(?P<bot>\d+)\s+(?P<flask>\d+)\s+(?P<vol>[\d.]+)\s+'
                 r'(?P<raw>[\d.]+)\s+(?P<titer>[\d.]+)\s+(?P<o2>-?[\d.]+)\s+(?P<thio_t>[\d.]+)\s+'
                 r'(?P<draw_t>[\d.]+)\s+(?P<volts>[\d.]+)\s+(?P<time>\d{6})\s*(?P<comment>.*)$')
HEADER = {'Expedition': re.compile(r'^Expedition:\s*(\S+)'),
          'Date': re.compile(r'^Date:\s*(\S+)'),
          'Chemist': re.compile(r'Chemist:\s*(\S+)'),
          'Thiosulfate normality (20 C)': re.compile(r'Thio \(20C\)\s*([\d.]+)'),
          'Blank': re.compile(r'Blk:\s*([\d.]+)')}


def read_oxygen(path: str | Path) -> LabFile:
    """Read an ODF oxygen .LST file.

    Parameters
    ----------
    path : str or Path
        The .LST file (any line endings).

    Returns
    -------
    LabFile
        One LabResult per flask, with cast, Niskin, station code, draw
        temperature and comment; header facts (expedition, date, chemist,
        thiosulfate normality, blank) in `header`.

    Raises
    ------
    LabError
        If no flask lines are found, a line after the column headings cannot
        be read, or a flask appears twice for the same cast.
    """
    path = Path(path)
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    header: dict[str, str] = {}
    results: list[LabResult] = []
    seen: dict[tuple[int, str], int] = {}
    in_table = False
    for i, ln in enumerate(lines, start=1):
        if not in_table:
            for key, rx in HEADER.items():
                m = rx.search(ln)
                if m and key not in header:
                    header[key] = m[1]
            if ln.startswith('ID '):            # second line of the column headings
                in_table = True
            continue
        if not ln.strip():
            continue
        m = ROW.match(ln.strip())
        if not m:
            raise LabError(f'{path.name} line {i}: cannot read flask line {ln.strip()!r}')
        cast, flask = int(m['cast']), str(int(m['flask']))
        if (cast, flask) in seen:
            raise LabError(f'{path.name} line {i}: cast {cast} flask {flask} already on line {seen[cast, flask]}')
        seen[cast, flask] = i
        results.append(LabResult(sample_id=flask, values={VALUE_COLUMN: m['o2']}, cast=cast, niskin=int(m['bot']),
                                 station=m['sta'], draw_temp=float(m['draw_t']), comment=m['comment'].strip(),
                                 line=i))
    if not results:
        raise LabError(f'{path.name}: no flask lines found')
    return LabFile(path, results, header)
