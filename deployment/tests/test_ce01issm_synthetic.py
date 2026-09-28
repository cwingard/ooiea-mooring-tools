"""Synthetic round-trip test for asset_deploy.platforms.ce01issm.

No config.xlsx fixture exists for this platform. This exercises the
'simple instrument suite + MFN section' code path (shared with
ce06issm.py): no METBK/HYDGN/PCO2A special cases, 3-way buoy/nsif/mfn
section split, the ADCPT-M/WAVSS-M key collision (both resolve via the
same 5-char instrument-class slice, no remap needed), and the inshore
buoy depth overrides (CTDBP/FLORT/VELPT). See tests/_synthetic_config.py.
"""
from __future__ import annotations

import pytest

from asset_deploy.platforms import ce01issm

from _synthetic_config import build_synthetic_config


def test_round_trip_sensor_uids():
    config, expected = build_synthetic_config(
        ce01issm, 'CE01ISSM-00099', water_depth='87',
    )
    result = ce01issm.build_deployment(config, previous_version_number='1')
    rows_by_refdes = {r['Reference Designator']: r for r in result.rows}

    assert set(rows_by_refdes) == set(rd for rd, _ in ce01issm.REFDES_SENSOR)
    for refdes, expected_uid in expected.items():
        assert rows_by_refdes[refdes]['sensor.uid'] == expected_uid, refdes


def test_inshore_buoy_depth_overrides():
    config, _ = build_synthetic_config(ce01issm, 'CE01ISSM-00099')
    result = ce01issm.build_deployment(config, previous_version_number='1')
    rows_by_refdes = {r['Reference Designator']: r for r in result.rows}

    ctdbp = next(rd for rd, _ in ce01issm.REFDES_SENSOR
                 if rd[9:11] == 'SB' and 'CTDBP' in rd)
    flort = next(rd for rd, _ in ce01issm.REFDES_SENSOR
                 if rd[9:11] == 'SB' and 'FLORT' in rd)
    velpt = next(rd for rd, _ in ce01issm.REFDES_SENSOR
                 if rd[9:11] == 'SB' and 'VELPT' in rd)
    assert rows_by_refdes[ctdbp]['deployment_depth'] == '1.0'
    assert rows_by_refdes[flort]['deployment_depth'] == '1.5'
    assert rows_by_refdes[velpt]['deployment_depth'] == '1.6'


def test_mfn_depth_equals_water_depth():
    config, _ = build_synthetic_config(
        ce01issm, 'CE01ISSM-00099', water_depth='87')
    result = ce01issm.build_deployment(config, previous_version_number='1')
    rows_by_refdes = {r['Reference Designator']: r for r in result.rows}
    mfn_refdes = next(
        rd for rd, _ in ce01issm.REFDES_SENSOR if rd[9:11] == 'MF')
    assert rows_by_refdes[mfn_refdes]['deployment_depth'] == '87'


def test_missing_wavss_row_raises_helpful_error():
    config, _ = build_synthetic_config(ce01issm, 'CE01ISSM-00099')
    # sabotage: rename the WAVSSM refdes's expected key out of the table
    # by building a config missing that row entirely
    bad_rows = [list(r) for r in config._rows]  # noqa: SLF001 (test-only)
    bad_rows = [r for r in bad_rows if r[0] != 'WAVSS S/N']
    from asset_deploy.config_xlsx import ConfigTable
    bad_config = ConfigTable(bad_rows)
    with pytest.raises(ValueError, match='WAVSS'):
        ce01issm.build_deployment(bad_config, previous_version_number='1')


def test_deployment_number_and_mooring_uid():
    config, _ = build_synthetic_config(ce01issm, 'CE01ISSM-00099')
    result = ce01issm.build_deployment(config, previous_version_number='2')
    assert result.dep_num == 99
    assert result.rows[0]['mooring.uid'] == 'CGMCE-01ISSM-00099'
    assert result.rows[0]['versionNumber'] == '2'
