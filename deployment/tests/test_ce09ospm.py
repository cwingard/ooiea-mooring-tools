"""Round-trip parity test for asset_deploy.platforms.ce09ospm.

No config.xlsx fixture exists for this platform, so instead of a static
fixture we reverse-engineer one from the real, historical
CE09OSPM_Deploy.csv: the latest deployment's own sensor.uid serials are
fed back in as the config-sheet S/N values (keyed by each instrument's
declared 8-character lookup key), and build_deployment() must reproduce
that exact same historical deployment row for row -- including the
McLane-specific node.uid quirk (MOPAK inherits the WFP's node.uid) and
the always-blank orbit column.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from asset_deploy.config_xlsx import ConfigTable
from asset_deploy.platforms import ce09ospm

_ASSET_MANAGEMENT_DIR = Path(os.environ.get(
    'ASSET_MANAGEMENT_DIR', r'C:\Users\chris\code\asset-management'))
_DEPLOY_CSV = _ASSET_MANAGEMENT_DIR / 'deployment' / 'CE09OSPM_Deploy.csv'


def _load_latest_real_deployment() -> dict[str, dict[str, str]]:
    with open(_DEPLOY_CSV, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    latest_dep = max(int(r['deploymentNumber']) for r in rows)
    return {
        r['Reference Designator']: r
        for r in rows if int(r['deploymentNumber']) == latest_dep
    }


def _build_synthetic_config(latest: dict[str, dict[str, str]]) -> ConfigTable:
    any_row = next(iter(latest.values()))
    dep_num = int(any_row['deploymentNumber'])
    mooring_sn = f'CE09OSPM-{dep_num:05d}'
    cruise_id = any_row['CUID_Deploy'].lstrip('#')

    rows: list[list[str]] = [
        ['Title', '', ''],
        ['Reference Designator:', 'CE09OSPM', ''],
        ['Type:', '', ''],
        ['Mooring S/N:', mooring_sn, ''],
        ['Anchor Launch Date:', '2026-01-01', ''],
        ['Anchor Launch Time:', '12:00', ''],
        ['Latitude:', any_row['lat'], ''],
        ['Longitude:', any_row['lon'], ''],
        ['Water Depth:', any_row['water_depth'], ''],
        ['Cruise #:', cruise_id, ''],
    ]
    for refdes, _, ikey in ce09ospm.REFDES_SENSOR:
        real_uid = latest[refdes]['sensor.uid']
        serial = real_uid.rsplit('-', 1)[-1] if real_uid else 'None'
        rows.append([ikey, serial, ''])

    return ConfigTable(rows)


@pytest.fixture(scope='module')
def latest_real():
    if not _DEPLOY_CSV.exists():
        pytest.skip('asset-management repo not mounted')
    return _load_latest_real_deployment()


@pytest.fixture(scope='module')
def result(latest_real):
    config = _build_synthetic_config(latest_real)
    return ce09ospm.build_deployment(config, previous_version_number='1')


@pytest.fixture(scope='module')
def rows_by_refdes(result):
    return {row['Reference Designator']: row for row in result.rows}


def test_reproduces_real_sensor_uids(latest_real, rows_by_refdes):
    for refdes, real_row in latest_real.items():
        assert rows_by_refdes[refdes]['sensor.uid'] == real_row['sensor.uid']


def test_reproduces_real_deployment_depths(latest_real, rows_by_refdes):
    for refdes, real_row in latest_real.items():
        assert (rows_by_refdes[refdes]['deployment_depth']
                == real_row['deployment_depth'])


def test_reproduces_real_node_uids(latest_real, rows_by_refdes):
    """Confirms the MOPAK-inherits-WFP-node.uid quirk is reproduced."""
    for refdes, real_row in latest_real.items():
        assert rows_by_refdes[refdes]['node.uid'] == real_row['node.uid']


def test_orbit_is_always_blank(rows_by_refdes):
    assert all(row['orbit'] == '' for row in rows_by_refdes.values())


def test_mooring_uid_matches(latest_real, rows_by_refdes):
    any_real = next(iter(latest_real.values()))
    any_computed = next(iter(rows_by_refdes.values()))
    assert any_computed['mooring.uid'] == any_real['mooring.uid']
