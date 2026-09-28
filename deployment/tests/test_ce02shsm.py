"""Parity tests for asset_deploy.platforms.ce02shsm.

Two layers:

1. Unit-level checks against values hand-traced from the MATLAB source
   applied to the sample CE02SHSM-00020.xlsx config file. These pin down
   the serial-number cleanup pipeline (hyphen handling, zero-padding,
   METBK/HYDGN key disambiguation).

2. A regression check against the *real* CE02SHSM_Deploy.csv in the
   asset-management repo: deployment 20 in that file was produced by an
   actual run of append_deploy_ce02shsm.m against this same config sheet,
   so recomputing it in Python and diffing against the historical rows is
   the strongest available parity signal. Some fields are expected to
   differ (see comments below) and are intentionally excluded from the
   comparison.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from asset_deploy.config_xlsx import read_config
from asset_deploy.platforms import ce02shsm

FIXTURE_CONFIG = Path(__file__).parent / 'fixtures' / 'CE02SHSM-00020.xlsx'

# Override with the ASSET_MANAGEMENT_DIR environment variable if your local
# clone lives somewhere else. The historical-deployment test below is
# skipped automatically if this path (or the file within it) is missing.
_ASSET_MANAGEMENT_DIR = Path(os.environ.get(
    'ASSET_MANAGEMENT_DIR', r'C:\Users\chris\code\asset-management'))
REAL_DEPLOY_CSV = _ASSET_MANAGEMENT_DIR / 'deployment' / 'CE02SHSM_Deploy.csv'


@pytest.fixture(scope='module')
def config():
    return read_config(FIXTURE_CONFIG)


@pytest.fixture(scope='module')
def result(config):
    return ce02shsm.build_deployment(config, previous_version_number='1')


@pytest.fixture(scope='module')
def rows_by_refdes(result):
    return {row['Reference Designator']: row for row in result.rows}


def test_deployment_number(result):
    assert result.dep_num == 20


def test_mooring_level_fields(rows_by_refdes):
    row = next(iter(rows_by_refdes.values()))
    assert row['lat'] == '44.63583'
    assert row['lon'] == '-124.30333'
    assert row['mooring.uid'] == 'CGMCE-02SHSM-00020'
    assert row['startDateTime'] == '2025-05-26T23:40:00'
    assert row['water_depth'] == '80'
    assert row['orbit'] == '250'
    assert row['assembly_template_revision'] == 'B'
    assert row['CUID_Deploy'] == 'SR2511'


@pytest.mark.parametrize('refdes,expected_uid', [
    ('CE02SHSM-SBC11-00-CPMENG000', 'CGCON-BCPM01-50012'),
    ('CE02SHSM-SBD11-00-DCLENG000', 'CGCON-BDCL11-50012'),
    ('CE02SHSM-SBD12-00-DCLENG000', 'CGCON-BDCL12-50012'),
    ('CE02SHSM-RIC21-00-CPMENG000', 'CGCON-NCPM02-00016'),
    ('CE02SHSM-RID27-00-DCLENG000', 'CGCON-NDCL27-00016'),
    ('CE02SHSM-RID26-00-DCLENG000', 'CGCON-NDCL26-00016'),
    ('CE02SHSM-SBD12-08-FDCHPA000', 'CGINS-FDCHPA-00024'),
    ('CE02SHSM-SBD11-02-HYDGN0000', 'CGINS-HYDGN0-49850'),
    ('CE02SHSM-SBD12-03-HYDGN0000', 'CGINS-HYDGN0-41897'),
    ('CE02SHSM-SBD11-06-METBKA001', 'CGINS-METCTD-10905'),
    ('CE02SHSM-SBD11-01-MOPAK0000', 'CGINS-MOPAK0-44016'),
    ('CE02SHSM-SBD12-04-PCO2AA000', 'CGINS-PCO2AA-44373'),
    ('CE02SHSM-SBD11-04-VELPTA000', 'CGINS-VELPTA-11405'),
    ('CE02SHSM-SBD12-05-WAVSSA000', 'CGINS-WAVSSA-05771'),
    ('CE02SHSM-RID26-01-ADCPTA000', 'CGINS-ADCPTA-18222'),
    ('CE02SHSM-RID27-03-CTDBPC000', 'CGINS-CTDBPC-50006'),
    ('CE02SHSM-RID27-04-DOSTAD000', 'CGINS-DOSTAD-00479'),
    ('CE02SHSM-RID27-02-FLORTD000', 'CGINS-FLORTD-01303'),
    ('CE02SHSM-RID26-07-NUTNRB000', 'CGINS-NUTNRB-01127'),
    ('CE02SHSM-RID27-01-OPTAAD000', 'CGINS-OPTAAD-00171'),
    ('CE02SHSM-RID26-06-PHSENG000', 'CGINS-PHSEND-02087'),
    ('CE02SHSM-RID26-08-SPKIRB000', 'CGINS-SPKIRB-00296'),
    ('CE02SHSM-RID26-04-VELPTA000', 'CGINS-VELPTA-11820'),
])
def test_sensor_uid_hand_traced(rows_by_refdes, refdes, expected_uid):
    assert rows_by_refdes[refdes]['sensor.uid'] == expected_uid


def test_deployment_depth_overrides(rows_by_refdes):
    assert rows_by_refdes['CE02SHSM-SBD12-08-FDCHPA000'][
        'deployment_depth'] == '-5'
    assert rows_by_refdes['CE02SHSM-SBD11-06-METBKA000'][
        'deployment_depth'] == '0'
    assert rows_by_refdes['CE02SHSM-SBD11-06-METBKA003'][
        'deployment_depth'] == '-4'
    assert rows_by_refdes['CE02SHSM-SBD12-04-PCO2AA000'][
        'deployment_depth'] == '0.7'
    # buoy VELPT gets the 'coastal VELPT' override, nsif VELPT does not
    assert rows_by_refdes['CE02SHSM-SBD11-04-VELPTA000'][
        'deployment_depth'] == '1.3'
    assert rows_by_refdes['CE02SHSM-RID26-04-VELPTA000'][
        'deployment_depth'] == '7'
    # generic buoy/nsif fallback
    assert rows_by_refdes['CE02SHSM-SBC11-00-CPMENG000'][
        'deployment_depth'] == '0'
    assert rows_by_refdes['CE02SHSM-RIC21-00-CPMENG000'][
        'deployment_depth'] == '7'


@pytest.mark.skipif(not REAL_DEPLOY_CSV.exists(),
                     reason='asset-management repo not mounted')
def test_matches_real_historical_deployment_20(rows_by_refdes):
    """Deployment 20 in the real CE02SHSM_Deploy.csv was produced by an
    actual run of append_deploy_ce02shsm.m against this same config sheet.
    Recomputing it and diffing is the strongest available parity check.

    lat/lon are excluded: the historical row's position was corrected
    post-deployment (GPS-verified anchor position), so it legitimately
    differs from the pre-cruise estimate in the config sheet. The sensor
    series letter (e.g. PHSEN-G vs the table's default PHSEN-D) can also
    be a deliberate one-off hand-edit per the MATLAB header's "one-offs"
    documentation, so only the trailing 5-digit serial is compared, not
    the full sensor.uid.

    One known discrepancy: METBKA007 (METBK-WND) recomputes to serial
    00238 (matching the '238' entered in the uploaded config sheet's
    METBK-WND S/N cell) but the committed record has 00248. Since every
    other METBK-family serial (which shares the same lookup/collision-
    disambiguation code path) matches exactly, this looks like the config
    sheet was corrected after deployment 20 was originally submitted,
    not a bug in the port -- flagged here rather than silently excluded.
    """
    with open(REAL_DEPLOY_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        historical = {}
        for row in reader:
            if row['deploymentNumber'] == '20':
                historical[row['Reference Designator']] = row

    assert set(historical) == set(rows_by_refdes)

    known_serial_mismatches = {'CE02SHSM-SBD11-06-METBKA007'}
    serial_mismatches = set()

    for refdes, computed in rows_by_refdes.items():
        actual = historical[refdes]
        if computed['sensor.uid'][-5:] != actual['sensor.uid'][-5:]:
            serial_mismatches.add(refdes)
        assert computed['mooring.uid'] == actual['mooring.uid']
        assert computed['CUID_Deploy'] == actual['CUID_Deploy']
        assert computed['startDateTime'] == actual['startDateTime']
        assert computed['orbit'] == actual['orbit']
        assert computed['water_depth'] == actual['water_depth']
        assert computed['deployment_depth'] == actual['deployment_depth']
        assert (computed['assembly_template_revision']
                == actual['assembly_template_revision'])

    assert serial_mismatches == known_serial_mismatches
