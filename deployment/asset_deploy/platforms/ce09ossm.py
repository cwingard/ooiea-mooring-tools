"""CE09OSSM (Washington Offshore Surface Mooring) deployment-row builder.

Ported from append_deploy_ce09ossm.m. Structurally identical to
CE07SHSM.py (buoy + nsif + MFN sections, 9 platcons), just orbit=500 and a
different MFN instrument lineup (ADCPS-J, CTDBP-E, OPTAA-C, PRESF-C). See
asset_deploy.serial_lookup for the shared lookup algorithm.
"""
from __future__ import annotations

from dataclasses import dataclass

from asset_deploy import serial_lookup as sl
from asset_deploy.config_xlsx import VALUE_COL, ConfigTable
from asset_deploy.metadata import read_metadata

PLATFORM_CODE = 'CE09OSSM'

REFDES_SENSOR: list[tuple[str, str]] = [
    ('CE09OSSM-SBC11-00-CPMENG000', 'CGCON-BCPM01-xxxxx'),
    ('CE09OSSM-SBD11-00-DCLENG000', 'CGCON-BDCL11-xxxxx'),
    ('CE09OSSM-SBD12-00-DCLENG000', 'CGCON-BDCL12-xxxxx'),
    ('CE09OSSM-RIC21-00-CPMENG000', 'CGCON-NCPM02-xxxxx'),
    ('CE09OSSM-RID27-00-DCLENG000', 'CGCON-NDCL27-xxxxx'),
    ('CE09OSSM-RID26-00-DCLENG000', 'CGCON-NDCL26-xxxxx'),
    ('CE09OSSM-MFC31-00-CPMENG000', 'CGCON-MCPM03-xxxxx'),
    ('CE09OSSM-MFD37-00-DCLENG000', 'CGCON-MDCL37-xxxxx'),
    ('CE09OSSM-MFD35-00-DCLENG000', 'CGCON-MDCL36-xxxxx'),
    ('CE09OSSM-SBD11-02-HYDGN0000', 'CGINS-HYDGN0-xxxxx'),
    ('CE09OSSM-SBD12-03-HYDGN0000', 'CGINS-HYDGN0-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA000', 'CGINS-METLGR-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA001', 'CGINS-METCTD-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA002', 'CGINS-METBPR-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA003', 'CGINS-METHRH-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA004', 'CGINS-METLWR-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA005', 'CGINS-METPRC-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA006', 'CGINS-METSWR-xxxxx'),
    ('CE09OSSM-SBD11-06-METBKA007', 'CGINS-METWND-xxxxx'),
    ('CE09OSSM-SBD11-01-MOPAK0000', 'CGINS-MOPAK0-xxxxx'),
    ('CE09OSSM-SBD12-04-PCO2AA000', 'CGINS-PCO2AA-xxxxx'),
    ('CE09OSSM-SBD11-04-VELPTA000', 'CGINS-VELPTA-xxxxx'),
    ('CE09OSSM-SBD12-05-WAVSSA000', 'CGINS-WAVSSA-xxxxx'),
    ('CE09OSSM-RID26-01-ADCPTC000', 'CGINS-ADCPTC-xxxxx'),
    ('CE09OSSM-RID27-03-CTDBPC000', 'CGINS-CTDBPC-xxxxx'),
    ('CE09OSSM-RID27-04-DOSTAD000', 'CGINS-DOSTAD-xxxxx'),
    ('CE09OSSM-RID27-02-FLORTD000', 'CGINS-FLORTD-xxxxx'),
    ('CE09OSSM-RID26-07-NUTNRB000', 'CGINS-NUTNRB-xxxxx'),
    ('CE09OSSM-RID27-01-OPTAAD000', 'CGINS-OPTAAD-xxxxx'),
    ('CE09OSSM-RID26-06-PHSEND000', 'CGINS-PHSEND-xxxxx'),
    ('CE09OSSM-RID26-08-SPKIRB000', 'CGINS-SPKIRB-xxxxx'),
    ('CE09OSSM-RID26-04-VELPTA000', 'CGINS-VELPTA-xxxxx'),
    ('CE09OSSM-MFD35-04-ADCPSJ000', 'CGINS-ADCPSJ-xxxxx'),
    ('CE09OSSM-MFD37-06-CAMDSA000', 'CGINS-CAMDSA-xxxxx'),
    ('CE09OSSM-MFD37-03-CTDBPE000', 'CGINS-CTDBPE-xxxxx'),
    ('CE09OSSM-MFD37-03-DOSTAD000', 'CGINS-DOSTAD-xxxxx'),
    ('CE09OSSM-MFD37-01-OPTAAC000', 'CGINS-OPTAAC-xxxxx'),
    ('CE09OSSM-MFD35-05-PCO2WB000', 'CGINS-PCO2WB-xxxxx'),
    ('CE09OSSM-MFD35-06-PHSEND000', 'CGINS-PHSEND-xxxxx'),
    ('CE09OSSM-MFD35-02-PRESFC000', 'CGINS-PRESFC-xxxxx'),
    ('CE09OSSM-MFD35-01-VEL3DD000', 'CGINS-VEL3DD-xxxxx'),
    ('CE09OSSM-MFD37-07-ZPLSCC000', 'CGINS-ZPLSCC-xxxxx'),
]

PLATCON = ['CPM1', 'DCL11', 'DCL12', 'CPM2', 'DCL27', 'DCL26',
           'CPM3', 'DCL37', 'DCL36']
N_PLATCON = len(PLATCON)

# no FDCHP on this platform; MFN depth is dynamic (== water_depth)
DEPTH_BUOY_WELL = '0'
DEPTH_BUOY_METLGR = '0'
DEPTH_BUOY_METCTD = '1'
DEPTH_BUOY_METBPR = '-4'
DEPTH_BUOY_METHRH = '-4'
DEPTH_BUOY_METLWR = '-4'
DEPTH_BUOY_METPRC = '-4'
DEPTH_BUOY_METSWR = '-4'
DEPTH_BUOY_METWND = '-5'
DEPTH_BUOY_PCO2A = '0.7'
DEPTH_BUOY_COASTAL_VELPT = '1.3'
DEPTH_NSIF = '7'

ORBIT = 500  # watch circle orbit [m]; offshore (OSSM) convention
ASSEMBLY_TEMPLATE_REVISION = 'B'

SECTIONS = [('instruments', 'SB'), ('nsif', 'RI'), ('mfn', 'MF')]


@dataclass
class DeploymentResult:
    dep_num: int
    rows: list[dict[str, str]]
    sensor_uids: list[str]


def _prepare_keys_values(config: ConfigTable) -> tuple[list[str], list[str]]:
    n = config.n_rows
    labels = [
        config.get(r, 1).replace('METBK S/N', 'METBK-LGR S/N')
        for r in range(1, n + 1)
    ]
    keys = [label.replace(' S/N', '') for label in labels]
    values = [config.get(r, VALUE_COL) for r in range(1, n + 1)]
    values = ['' if sl.is_not_deployed(v) else v for v in values]
    values = sl.apply_pco2a_fix(values)
    values = [sl.fix_serial(v, strip_lgr=True) for v in values]
    keys = sl.disambiguate_port_keys(keys, values, ('11:02', '12:03'))
    return keys, values


def _instrument_serial_dict(
    keys: list[str], values: list[str],
) -> dict[str, str]:
    keys, start = sl.assign_section_prefixes(keys, SECTIONS)
    keys, values = sl.strip_location_rows(keys[start:], values[start:])
    keys = sl.collapse_metbk_keys(keys)
    return sl.build_serial_dict(keys, values)


def _refdes_ikeys(instrument_refdes: list[str]) -> list[str]:
    ikeys = sl.refdes_ikeys(instrument_refdes, sl.METBK_REFDES_REMAP)
    return sl.disambiguate_hydgn_ikeys(ikeys)


def _deployment_depth(refdes: str, water_depth: str) -> str:
    platform_code = refdes[9:11].upper()
    if platform_code == 'RI':
        depth = DEPTH_NSIF
    elif platform_code == 'MF':
        depth = water_depth
    else:
        depth = DEPTH_BUOY_WELL

    if 'METBKA000' in refdes:
        depth = DEPTH_BUOY_METLGR
    elif 'METBKA001' in refdes:
        depth = DEPTH_BUOY_METCTD
    elif 'METBKA002' in refdes:
        depth = DEPTH_BUOY_METBPR
    elif 'METBKA003' in refdes:
        depth = DEPTH_BUOY_METHRH
    elif 'METBKA004' in refdes:
        depth = DEPTH_BUOY_METLWR
    elif 'METBKA005' in refdes:
        depth = DEPTH_BUOY_METPRC
    elif 'METBKA006' in refdes:
        depth = DEPTH_BUOY_METSWR
    elif 'METBKA007' in refdes:
        depth = DEPTH_BUOY_METWND
    elif 'PCO2A' in refdes:
        depth = DEPTH_BUOY_PCO2A

    if (refdes[9:11] + refdes[18:23]).upper() == 'SBVELPT':
        depth = DEPTH_BUOY_COASTAL_VELPT

    return depth


def build_deployment(
    config: ConfigTable, previous_version_number: str,
) -> DeploymentResult:
    meta = read_metadata(config)

    keys, values = _prepare_keys_values(config)
    serial_dict = _instrument_serial_dict(keys, values)
    platcon_serials = sl.platcon_serials(config, values, PLATCON)

    instrument_refdes = [rd for rd, _ in REFDES_SENSOR[N_PLATCON:]]
    ikeys = _refdes_ikeys(instrument_refdes)

    sensor_uids: list[str] = []
    for i, (_, template) in enumerate(REFDES_SENSOR):
        if i < N_PLATCON:
            serial = platcon_serials[i]
        else:
            serial = serial_dict[ikeys[i - N_PLATCON]]
        sensor_uids.append(template.replace('xxxxx', serial))

    not_deployed = ['00000' in uid for uid in sensor_uids]
    sensor_uids = [
        '' if nd else uid for nd, uid in zip(not_deployed, sensor_uids)
    ]

    rows: list[dict[str, str]] = []
    for i, (refdes, _) in enumerate(REFDES_SENSOR):
        cuid_deploy = ('#' if not_deployed[i] else '') + meta.cruise_id
        rows.append({
            'CUID_Deploy': cuid_deploy,
            'CUID_Recover': '',
            'Reference Designator': refdes,
            'deployedBy': '',
            'deploymentNumber': str(meta.dep_num),
            'deployment_depth': _deployment_depth(refdes, meta.water_depth),
            'lat': meta.lat,
            'lon': meta.lon,
            'mooring.uid': meta.mooring_uid,
            'node.uid': '',
            'notes': 'Not Deployed' if not_deployed[i] else '',
            'orbit': str(ORBIT),
            'recoveredBy': '',
            'sensor.uid': sensor_uids[i],
            'startDateTime': meta.start_date_time,
            'stopDateTime': '',
            'versionNumber': previous_version_number,
            'water_depth': meta.water_depth,
            'electrical.uid': '',
            'assembly_template_revision': ASSEMBLY_TEMPLATE_REVISION,
        })

    return DeploymentResult(
        dep_num=meta.dep_num,
        rows=rows,
        sensor_uids=sensor_uids,
    )
