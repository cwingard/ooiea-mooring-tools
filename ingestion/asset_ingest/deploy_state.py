"""Which reference designators asset_management says were deployed.

Reads <asset-management>/deployment/<SITE>_Deploy.csv by column name. A row
is not deployed when any cell starts with '#' (the deploy tool comments out
CUID_Deploy for instruments that were not deployed).
"""
from __future__ import annotations

import csv
from pathlib import Path


class DeployStateError(ValueError):
    """The asset_management deployment CSV cannot be used."""


def deploy_csv_path(asset_management: str | Path, site: str) -> Path:
    return Path(asset_management) / 'deployment' / f'{site}_Deploy.csv'


def read_deploy_state(asset_management: str | Path, site: str) -> dict[int, dict[str, bool]]:
    """Deployed flag per reference designator, per deployment number.

    Parameters
    ----------
    asset_management : str or Path
        Root of the asset-management repo.
    site : str
        Eight-character site code, e.g. 'CE07SHSM'.

    Returns
    -------
    dict
        {deployment number: {reference designator: deployed}}
    """
    path = deploy_csv_path(asset_management, site)
    if not path.exists():
        raise DeployStateError(f'{path} not found')
    state: dict[int, dict[str, bool]] = {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for name in ('Reference Designator', 'deploymentNumber'):
            if name not in (reader.fieldnames or []):
                raise DeployStateError(f'{path.name}: no {name!r} column')
        for row in reader:
            cells = [v or '' for v in row.values() if isinstance(v, str)]
            commented = any(c.strip().startswith('#') for c in cells)
            num = row['deploymentNumber'].lstrip('#').strip()
            refdes = row['Reference Designator'].lstrip('#').strip()
            if not num or not refdes:
                continue
            state.setdefault(int(num), {})[refdes] = not commented
    return state
