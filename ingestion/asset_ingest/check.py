"""Report internal-consistency problems in a site's ingestion CSVs.

Read-only. For each <SITE>_[DR]NNNNN_ingest.csv it checks:

* the header is the standard six columns;
* every mask points at this site and this file's D/R directory;
* each reference designator belongs to the site;
* data_source is telemetered (D files) or recovered_host, recovered_inst
  or recovered_wfp (R files);
* status is one of the ingestion-csvs README codes, and active rows are
  not marked 'Not Deployed' or 'Not Expected';
* all D and R rows for one reference designator in one deployment use the
  same DCL, and an instrument recorded by a CTDBP uses the CTDBP's DCL;
* when asset_management is given: active rows are deployed there, and
  every deployed reference designator has at least one row in that
  deployment. Only reference designators that appear somewhere in the
  site's files are held to this; ones that never do (METBK sub-sensors,
  instruments with no parser) have no stream to list.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from asset_ingest.deploy_state import read_deploy_state
from asset_ingest.ingest_file import FILE_RE, HEADER, STATUS_CODES, IngestFileError, ctd_host, read_ingest_csv

DATA_SOURCES = {'D': ('telemetered',), 'R': ('recovered_host', 'recovered_inst', 'recovered_wfp')}
DCL_RE = re.compile(r'/(?:cg_data|instrmts)/dcl(\d{2})/')


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f'{self.file}:{self.line}: {self.message}' if self.line else f'{self.file}: {self.message}'


def check_site(ingestion_csvs: str | Path, site: str, asset_management: str | Path | None = None,
               deployment: int | None = None) -> list[Finding]:
    """Check one site's ingestion CSVs.

    Parameters
    ----------
    ingestion_csvs : str or Path
        Root of the ingestion-csvs repo.
    site : str
        Eight-character site code, e.g. 'CE07SHSM'.
    asset_management : str or Path, optional
        Root of the asset-management repo; enables the deployed-state checks.
    deployment : int, optional
        Limit the check to one deployment number.

    Returns
    -------
    list of Finding
        Empty when nothing was found.
    """
    folder = Path(ingestion_csvs) / site
    state = read_deploy_state(asset_management, site) if asset_management else {}
    findings: list[Finding] = []
    # (deployment, refdes) -> {dcl: [(file, line)]}
    dcls: dict[tuple[int, str], dict[str, list[tuple[str, int]]]] = defaultdict(lambda: defaultdict(list))
    rows_by_dep: dict[int, set[str]] = defaultdict(set)

    for path in sorted(folder.glob(f'{site}_*_ingest.csv')):
        m = FILE_RE.match(path.name)
        if not m or m['site'] != site:
            findings.append(Finding(path.name, 0, 'file name is not <SITE>_[DR]NNNNN_ingest.csv'))
            continue
        kind, num = m['kind'], int(m['num'])
        if deployment is not None and num != deployment:
            continue
        name = path.name
        try:
            header, rows = read_ingest_csv(path)
        except IngestFileError as err:
            findings.append(Finding(name, 0, str(err)))
            continue
        if header != HEADER:
            findings.append(Finding(name, 1, f'header is {",".join(header)!r}'))
        dep_dir = f'/{site}/{kind}{num:05d}/'
        for row in rows:
            refdes = row.reference_designator

            def add(message: str) -> None:
                findings.append(Finding(name, row.line, f'{refdes}: {message}'))

            if not refdes.startswith(site + '-'):
                add('reference designator is not on this site')
            if dep_dir not in row.filename_mask:
                add(f'mask does not contain {dep_dir}')
            if row.data_source not in DATA_SOURCES[kind]:
                add(f'data_source {row.data_source!r} in a {kind} file')
            if row.status not in STATUS_CODES:
                add(f'status {row.status!r} is not a README code')
            elif row.active and row.status in ('Not Deployed', 'Not Expected'):
                add(f'active row marked {row.status!r}')
            dcl = DCL_RE.search(row.filename_mask)
            if dcl:
                dcls[(num, refdes)][dcl.group(1)].append((name, row.line))
            rows_by_dep[num].add(refdes)
            deployed = state.get(num, {}).get(refdes)
            if row.active and deployed is False:
                add('active but not deployed in asset_management')

    for (num, refdes), seen in sorted(dcls.items()):
        if len(seen) > 1:
            where = '; '.join(f'dcl{d} at ' + ', '.join(f'{f}:{n}' for f, n in locs)
                              for d, locs in sorted(seen.items()))
            findings.append(Finding(f'deployment {num}', 0, f'{refdes}: DCL differs between rows ({where})'))

    for num in sorted(rows_by_dep):
        for refdes in sorted(rows_by_dep[num]):
            host = ctd_host(refdes, rows_by_dep[num])
            own, theirs = set(dcls.get((num, refdes), {})), set(dcls.get((num, host), {})) if host else set()
            if host and own and theirs and own != theirs:
                findings.append(Finding(f'deployment {num}', 0, f'{refdes}: on dcl{",".join(sorted(own))} but its '
                                        f'CTDBP {host} is on dcl{",".join(sorted(theirs))}'))

    has_stream = set().union(*rows_by_dep.values()) if rows_by_dep else set()
    for num in sorted(rows_by_dep):
        for refdes, deployed in sorted(state.get(num, {}).items()):
            if deployed and refdes in has_stream and refdes not in rows_by_dep[num]:
                findings.append(Finding(f'deployment {num}', 0, f'{refdes}: deployed but has no ingestion row'))
    return findings
