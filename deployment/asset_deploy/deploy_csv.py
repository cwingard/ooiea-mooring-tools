"""Read, update, and write OOI CI *_Deploy.csv files.

Ported from the shared read/write/recovery-backfill sections duplicated
across every append_deploy_*.m script (see e.g. append_deploy_ce02shsm.m lines
285-319 and 560-634).

Unlike the MATLAB source, this module does not need to alphabetically sort
and then re-order columns by hardcoded position: rows are kept as
dictionaries keyed by column name (via csv.DictReader/DictWriter), so the
on-disk column order is preserved automatically regardless of how CI has
ordered the header that turn.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# Column name constants, to avoid typos scattered through platform modules.
COL_CUID_DEPLOY = 'CUID_Deploy'
COL_CUID_RECOVER = 'CUID_Recover'
COL_REFDES = 'Reference Designator'
COL_DEPLOYMENT_NUMBER = 'deploymentNumber'
COL_START_DATETIME = 'startDateTime'
COL_STOP_DATETIME = 'stopDateTime'
COL_VERSION_NUMBER = 'versionNumber'


@dataclass
class DeployCsv:
    """In-memory representation of a *_Deploy.csv file."""

    fieldnames: list[str]
    rows: list[dict[str, str]]


def read_deploy_csv(path: str | Path) -> DeployCsv:
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return DeployCsv(fieldnames=fieldnames, rows=rows)


def write_deploy_csv(path: str | Path, deploy: DeployCsv) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f, fieldnames=deploy.fieldnames, lineterminator='\n',
        )
        writer.writeheader()
        writer.writerows(deploy.rows)


def previous_version_number(deploy: DeployCsv) -> str:
    """versionNumber to carry forward, taken from the last existing row.

    Matches `verNum = D(end, 17);` in the MATLAB source.
    """
    if not deploy.rows:
        raise ValueError('deploy.csv has no existing rows to read '
                          'versionNumber from')
    return deploy.rows[-1][COL_VERSION_NUMBER]


def deployment_rows(deploy: DeployCsv, dep_num: int) -> list[dict[str, str]]:
    """Existing rows whose deploymentNumber equals `dep_num`."""
    rows = []
    for row in deploy.rows:
        try:
            if int(row[COL_DEPLOYMENT_NUMBER]) == dep_num:
                rows.append(row)
        except (KeyError, ValueError):
            continue
    return rows


def record_recovery(
    deploy: DeployCsv,
    dep_num: int,
    stop_date_time: str,
    cuid_recover: str,
    force: bool = False,
) -> list[dict[str, str]]:
    """Write recovery info into every row of one deployment.

    Rows flagged not-deployed (a '#' prefix on CUID_Deploy) get the same '#'
    prefix on CUID_Recover, matching the MATLAB source.

    Raises
    ------
    ValueError
        If the deployment has no rows, or already has recovery info and
        `force` is False.
    """
    rows = deployment_rows(deploy, dep_num)
    if not rows:
        raise ValueError(f'No rows with deploymentNumber {dep_num}')
    recovered = [r for r in rows if r.get(COL_STOP_DATETIME) or r.get(COL_CUID_RECOVER)]
    if recovered and not force:
        r = recovered[0]
        raise ValueError(
            f'Deployment {dep_num} already has recovery info on {len(recovered)} of {len(rows)} rows '
            f'(stopDateTime={r.get(COL_STOP_DATETIME)!r}, CUID_Recover={r.get(COL_CUID_RECOVER)!r}); '
            'use --force to overwrite.')
    for row in rows:
        prefix = '#' if '#' in row.get(COL_CUID_DEPLOY, '') else ''
        row[COL_STOP_DATETIME] = stop_date_time
        row[COL_CUID_RECOVER] = prefix + cuid_recover
    return rows


def replace_deployment(
    deploy: DeployCsv, dep_num: int, new_rows: list[dict[str, str]],
) -> list[tuple[str, str, str, str]]:
    """Overwrite one deployment's rows in place with regenerated rows.

    Rows are matched by reference designator and updated field by field, so
    the file keeps its row order and the git diff shows only real changes.

    Returns
    -------
    list[tuple[str, str, str, str]]
        (reference designator, column, old value, new value) for every
        field that changed.

    Raises
    ------
    ValueError
        If the existing and regenerated rows do not cover the same set of
        reference designators.
    """
    old = deployment_rows(deploy, dep_num)
    old_by_refdes = {r[COL_REFDES]: r for r in old}
    new_by_refdes = {r[COL_REFDES]: r for r in new_rows}
    if len(old_by_refdes) != len(old) or set(old_by_refdes) != set(new_by_refdes):
        raise ValueError(
            f'Deployment {dep_num} rows do not match the platform table: '
            f'only in file {sorted(set(old_by_refdes) - set(new_by_refdes))}, '
            f'only in table {sorted(set(new_by_refdes) - set(old_by_refdes))}')
    changes = []
    for refdes, new in new_by_refdes.items():
        row = old_by_refdes[refdes]
        for field in deploy.fieldnames:
            if field in new and row.get(field, '') != new[field]:
                changes.append((refdes, field, row.get(field, ''), new[field]))
                row[field] = new[field]
    return changes


def append_new_deployment(
    deploy: DeployCsv, new_rows: list[dict[str, str]],
) -> None:
    """Append this turn's deployment rows to the existing deploy.csv rows.

    Each row in `new_rows` must already be keyed by the same column names
    as `deploy.fieldnames`; missing keys are written out as '' by
    DictWriter's restval-free default (KeyError otherwise), so platform
    modules should pre-fill every column.
    """
    deploy.rows.extend(new_rows)
