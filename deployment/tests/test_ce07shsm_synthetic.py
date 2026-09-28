"""Synthetic round-trip test for asset_deploy.platforms.ce07shsm.

No config.xlsx fixture exists for this platform. This exercises the
'complex instrument suite + MFN section' code path (shared with
ce09ossm.py): 3-way buoy/nsif/mfn section split, METBK 7-char key
collapse, HYDGN DCL:Port # disambiguation, the PCO2A '-50A' fix, and the
dynamic MFN depth (== water_depth). See tests/_synthetic_config.py.
"""
from __future__ import annotations

from asset_deploy import serial_lookup as sl
from asset_deploy.platforms import ce07shsm

from _synthetic_config import build_synthetic_config


def test_round_trip_sensor_uids():
    config, expected = build_synthetic_config(
        ce07shsm, 'CE07SHSM-00099', water_depth='87',
        metbk_remap=sl.METBK_REFDES_REMAP,
    )
    result = ce07shsm.build_deployment(config, previous_version_number='1')
    rows_by_refdes = {r['Reference Designator']: r for r in result.rows}

    assert set(rows_by_refdes) == set(rd for rd, _ in ce07shsm.REFDES_SENSOR)
    for refdes, expected_uid in expected.items():
        assert rows_by_refdes[refdes]['sensor.uid'] == expected_uid, refdes


def test_hydgn_pair_gets_distinct_serials():
    config, expected = build_synthetic_config(
        ce07shsm, 'CE07SHSM-00099', metbk_remap=sl.METBK_REFDES_REMAP,
    )
    result = ce07shsm.build_deployment(config, previous_version_number='1')
    rows_by_refdes = {r['Reference Designator']: r for r in result.rows}
    hydgn_refdes = [rd for rd, _ in ce07shsm.REFDES_SENSOR if 'HYDGN' in rd]
    assert len(hydgn_refdes) == 2
    uids = [rows_by_refdes[rd]['sensor.uid'] for rd in hydgn_refdes]
    assert uids[0] != uids[1]


def test_mfn_depth_equals_water_depth():
    config, _ = build_synthetic_config(
        ce07shsm, 'CE07SHSM-00099', water_depth='87',
        metbk_remap=sl.METBK_REFDES_REMAP,
    )
    result = ce07shsm.build_deployment(config, previous_version_number='1')
    rows_by_refdes = {r['Reference Designator']: r for r in result.rows}
    mfn_refdes = next(
        rd for rd, _ in ce07shsm.REFDES_SENSOR if rd[9:11] == 'MF')
    assert rows_by_refdes[mfn_refdes]['deployment_depth'] == '87'
    assert rows_by_refdes[mfn_refdes]['water_depth'] == '87'


def test_deployment_number_and_mooring_uid():
    config, _ = build_synthetic_config(
        ce07shsm, 'CE07SHSM-00099', metbk_remap=sl.METBK_REFDES_REMAP,
    )
    result = ce07shsm.build_deployment(config, previous_version_number='3')
    assert result.dep_num == 99
    assert result.rows[0]['mooring.uid'] == 'CGMCE-07SHSM-00099'
    assert result.rows[0]['versionNumber'] == '3'
