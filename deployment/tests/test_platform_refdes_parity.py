"""Cross-check every ported platform's REFDES_SENSOR table against the
real, historical *_Deploy.csv in the asset-management repo.

Every reference designator that has ever appeared in a real deployment
for that platform is either in our table or was retired from the current
instrument suite (and should therefore be absent from the *current*
MATLAB source too -- we can't tell those two cases apart without the
MATLAB source in front of us, so this test only asserts the direction we
can be confident about: nothing in our table should be a refdes that has
never actually been deployed on that platform).
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from asset_deploy.platforms import (
    ce01issm, ce02shsm, ce04ossm, ce06issm, ce07shsm, ce09ospm, ce09ossm,
)

_ASSET_MANAGEMENT_DIR = Path(os.environ.get(
    'ASSET_MANAGEMENT_DIR', r'C:\Users\chris\code\asset-management'))
_DEPLOY_DIR = _ASSET_MANAGEMENT_DIR / 'deployment'

PLATFORMS = [ce01issm, ce02shsm, ce04ossm, ce06issm, ce07shsm, ce09ossm]


def _historical_refdes(platform_code: str) -> set[str]:
    path = _DEPLOY_DIR / f'{platform_code}_Deploy.csv'
    with open(path, newline='', encoding='utf-8') as f:
        return {row['Reference Designator'] for row in csv.DictReader(f)}


@pytest.mark.skipif(not _DEPLOY_DIR.exists(),
                     reason='asset-management repo not mounted')
@pytest.mark.parametrize('platform', PLATFORMS, ids=lambda p: p.PLATFORM_CODE)
def test_refdes_table_matches_real_deploy_csv(platform):
    historical = _historical_refdes(platform.PLATFORM_CODE)
    table_refdes = {rd for rd, _ in platform.REFDES_SENSOR}
    only_in_table = table_refdes - historical
    assert not only_in_table, (
        f'{platform.PLATFORM_CODE}: refdes in REFDES_SENSOR that have '
        f'never appeared in the real deploy.csv: {sorted(only_in_table)}')


@pytest.mark.skipif(not _DEPLOY_DIR.exists(),
                     reason='asset-management repo not mounted')
def test_ce09ospm_refdes_table_matches_real_deploy_csv():
    historical = _historical_refdes(ce09ospm.PLATFORM_CODE)
    table_refdes = {rd for rd, _, _ in ce09ospm.REFDES_SENSOR}
    only_in_table = table_refdes - historical
    assert not only_in_table
