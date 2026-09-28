"""Read the logger wiring from a deployment configuration workbook.

Only the rows ingestion needs are read, from columns A:C exactly as the
technicians maintain the sheet:

* 'Reference Designator:' and 'Mooring S/N:' -> site and deployment number
* 'Instruments <Buoy|NSIF|MFN>' section headers -> node prefix SB/RI/MF
* '<CLASS> DCL:Port #' rows (value 'NN:PP') -> where each instrument is
  actually plugged in
* Platform Control rows (notes such as 'CPM2, DCL27') -> loggers present

Profiler moorings (e.g. CE09OSPM) have no DCL:Port rows; their templates
use no '{dcl}' token, so only the site and deployment number are needed.
Rows under any other 'Instruments ...' header are ignored.

Instruments are matched to reference designators by section and class; the
port breaks ties when a class appears more than once in a section (e.g.
the two buoy HYDGNs). The DCL comes from the sheet, never from the
reference designator (MFD35 instruments log on DCL36).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import openpyxl

SECTION_PREFIX = {'buoy': 'SB', 'nsif': 'RI', 'mfn': 'MF'}
WIRING_RE = re.compile(r'^(\d{2}):(\d{2})$')


class ConfigError(ValueError):
    """The configuration workbook cannot be used as-is."""


@dataclass
class WiringEntry:
    section: str      # node prefix: SB, RI or MF
    cls: str          # instrument class as labeled, e.g. 'CTDBP'
    dcl: int | None   # None when the DCL:Port cell is blank
    port: int | None
    row: int
    used: bool = False


@dataclass
class ConfigWiring:
    site: str
    dep_num: int
    entries: list[WiringEntry]
    loggers: set[int]

    def find(self, refdes: str) -> WiringEntry | None:
        """Wiring entry for an instrument reference designator.

        Returns None when the sheet has no DCL:Port row for it. Raises
        ConfigError when the match is ambiguous.
        """
        section, cls, port = refdes[9:11], refdes[18:23], int(refdes[15:17])
        candidates = [e for e in self.entries if e.section == section and e.cls == cls]
        if len(candidates) > 1:
            candidates = [e for e in candidates if e.port == port]
        if len(candidates) > 1:
            rows = ', '.join(str(e.row) for e in candidates)
            raise ConfigError(f'{refdes}: DCL:Port rows {rows} all match; cannot tell them apart')
        return candidates[0] if candidates else None


def _text(value: object, row: int) -> str:
    if value is None:
        return ''
    if isinstance(value, (dt.datetime, dt.date, dt.time, dt.timedelta)):
        raise ConfigError(f'Row {row}: Excel stored {value!r} as a date/time; re-enter the cell as text')
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def read_config_wiring(path: str | Path) -> ConfigWiring:
    """Read site, deployment number, DCL:Port wiring and loggers.

    Parameters
    ----------
    path : str or Path
        Deployment configuration workbook (.xlsx).

    Returns
    -------
    ConfigWiring
    """
    sheet = openpyxl.load_workbook(path, data_only=True).active
    site = mooring_sn = ''
    section: str | None = None
    entries: list[WiringEntry] = []
    loggers: set[int] = set()

    for r, cells in enumerate(sheet.iter_rows(min_row=1, max_col=3, values_only=True), start=1):
        label = '' if cells[0] is None else str(cells[0]).strip()
        low = label.lower()
        if low == 'reference designator:':
            site = _text(cells[1], r)
        elif low == 'mooring s/n:':
            mooring_sn = _text(cells[1], r)
        elif low.startswith('instruments'):
            section = SECTION_PREFIX.get(low.removeprefix('instruments').strip())
        elif low.endswith('dcl:port #') and section is not None:
            value = _text(cells[1], r)
            dcl = port = None
            if value:
                m = WIRING_RE.match(value)
                if not m:
                    raise ConfigError(f'Row {r}: {label!r} value {value!r} is not DCL:Port (NN:PP)')
                dcl, port = int(m.group(1)), int(m.group(2))
            cls = label[:-len('dcl:port #')].strip().upper()
            entries.append(WiringEntry(section, cls, dcl, port, r))
        elif 'assm s/n' in low:
            loggers.update(int(n) for n in re.findall(r'DCL(\d{2})', _text(cells[2], r).upper()))

    m = re.match(r'^([A-Z0-9]{8})-(\d{5})$', mooring_sn)
    if not m:
        raise ConfigError(f'Mooring S/N {mooring_sn!r} is not <SITE>-NNNNN')
    if site and site != m.group(1):
        raise ConfigError(f'Reference Designator {site!r} does not match Mooring S/N {mooring_sn!r}')
    return ConfigWiring(m.group(1), int(m.group(2)), entries, loggers)
