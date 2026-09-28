"""Read and write ingestion CSV files (and the templates, which share the
same format).

Format: a header line, then one row per ingestion stream with the columns
parser, filename_mask, reference_designator, data_source, status, notes.
A row is commented out (ignored by ingestion) when a cell begins with '#';
this code always writes the marker as '# ' in front of the parser cell, as
the existing EA files do.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, replace
from pathlib import Path

HEADER = ['parser', 'filename_mask', 'reference_designator', 'data_source', 'status', 'notes']

# status codes defined in the ingestion-csvs README
STATUS_CODES = ('Not Deployed', 'Not Expected', 'Missing', 'Expected', 'Pending', 'Available')

FILE_RE = re.compile(r'^(?P<site>[A-Z0-9]{8})_(?P<kind>[DR])(?P<num>\d{5})_ingest\.csv$')


class IngestFileError(ValueError):
    """An ingestion CSV or template cannot be parsed."""


@dataclass(frozen=True)
class IngestRow:
    """One stream row; `active` is False for a commented-out row."""
    active: bool
    parser: str
    filename_mask: str
    reference_designator: str
    data_source: str
    status: str
    notes: str
    line: int = 0

    def with_(self, **changes: object) -> IngestRow:
        return replace(self, **changes)


def _parse_line(text: str, line: int, path: Path) -> IngestRow:
    active = True
    if text.lstrip().startswith('#'):
        active = False
        text = re.sub(r'^\s*#\s?', '', text)
    cells = next(csv.reader([text]))
    if any(c.lstrip().startswith('#') for c in cells):
        active = False
        cells = [re.sub(r'^\s*#\s?', '', c) for c in cells]
    if len(cells) < len(HEADER):
        cells += [''] * (len(HEADER) - len(cells))
    if len(cells) > len(HEADER):
        raise IngestFileError(f'{path.name} line {line}: {len(cells)} columns, expected {len(HEADER)}')
    return IngestRow(active, *(c.strip() for c in cells), line=line)


def read_ingest_csv(path: str | Path) -> tuple[list[str], list[IngestRow]]:
    """Read an ingestion CSV or template.

    Parameters
    ----------
    path : str or Path
        File to read.

    Returns
    -------
    header : list of str
        The header cells as found (not validated here).
    rows : list of IngestRow
        Data rows in file order; blank lines are skipped.
    """
    path = Path(path)
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    if not lines:
        raise IngestFileError(f'{path.name} is empty')
    header = [c.strip() for c in next(csv.reader([lines[0]]))]
    rows = [_parse_line(text, n, path) for n, text in enumerate(lines[1:], start=2) if text.strip()]
    return header, rows


def format_row(row: IngestRow) -> str:
    """Format one row as a CSV line (no line terminator)."""
    buf = io.StringIO()
    csv.writer(buf, lineterminator='').writerow(
        [row.parser, row.filename_mask, row.reference_designator, row.data_source, row.status, row.notes])
    text = buf.getvalue()
    return text if row.active else '# ' + text


def write_ingest_csv(path: str | Path, rows: list[IngestRow]) -> None:
    """Write rows under the standard header, LF line endings."""
    lines = [','.join(HEADER)] + [format_row(r) for r in rows]
    Path(path).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')


def ctd_host(refdes: str, candidates: set[str]) -> str | None:
    """CTDBP that records `refdes`, if any.

    An instrument plugged into and recorded by a CTDBP (the DOSTA on an MFN
    or NSIF CTDBP, the FLORT on an inshore buoy CTDBP) shares the CTDBP's
    node and port in its reference designator, e.g. MFD37-03-DOSTAD000 and
    MFD37-03-CTDBPC000. Its data are in the CTDBP's log, so it is on the
    CTDBP's DCL.

    Parameters
    ----------
    refdes : str
        Reference designator to look up.
    candidates : set of str
        Reference designators to search for the host CTDBP.

    Returns
    -------
    str or None
        The host CTDBP's reference designator, or None.
    """
    if refdes[18:23] == 'CTDBP':
        return None
    prefix = refdes[:18] + 'CTDBP'
    hosts = sorted(c for c in candidates if c.startswith(prefix))
    return hosts[0] if hosts else None
