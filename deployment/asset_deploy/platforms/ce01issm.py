"""CE01ISSM (Oregon Inshore Surface Mooring) deployment-row builder.

Ported from append_deploy_ce01issm.m. Simpler instrument suite than the
shelf/offshore moorings (no METBK, no HYDGN, no PCO2A) but with an extra
multi-function node (MFN) section, so the sensor.uid lookup uses a 3-way
buoy/nsif/mfn split instead of ce02shsm.py's 2-way buoy/nsif split. See
asset_deploy.serial_lookup for the shared lookup algorithm.

CONFIG.XLSX NOTE (from the MATLAB source): the ADCPT-M and WAVSS-M
instruments share one physical unit and one S/N, but need two separate
config-sheet rows (duplicate the ADCPT S/N row in the MFN section, and
relabel the copy 'WAVSS S/N') so that both CGINS-ADCPTM and CGINS-WAVSSM
sensor.uid lookups resolve. If that row is missing, build_deployment
raises a KeyError-wrapping ValueError naming the missing lookup key.
"""
from __future__ import annotations

from dataclasses import dataclass

from asset_deploy import serial_lookup as sl
from asset_deploy.config_xlsx import VALUE_COL, ConfigTable
from asset_deploy.metadata import read_metadata

PLATFORM_CODE = 'CE01ISSM'

REFDES_SENSOR: list[tuple[str, str]] = [
    ('CE01ISSM-SBC11-00-CPMENG000', 'CGCON-ECPM01-xxxxx'),
    ('CE01ISSM-SBD17-00-DCLENG000', 'CGCON-EDCL17-xxxxx'),
    ('CE01ISSM-RID16-00-DCLENG000', 'CGCON-NDCL16-xxxxx'),
    ('CE01ISSM-MFC31-00-CPMENG000', 'CGCON-MCPM03-xxxxx'),
    ('CE01ISSM-MFD37-00-DCLENG000', 'CGCON-MDCL37-xxxxx'),
    ('CE01ISSM-MFD35-00-DCLENG000', 'CGCON-MDCL36-xxxxx'),
    ('CE01ISSM-SBD17-06-CTDBPC000', 'CGINS-CTDBPC-xxxxx'),
    ('CE01ISSM-SBD17-06-FLORTD000', 'CGINS-FLORTD-xxxxx'),
    ('CE01ISSM-SBD17-01-MOPAK0000', 'CGINS-MOPAK0-xxxxx'),
    ('CE01ISSM-SBD17-04-VELPTA000', 'CGINS-VELPTA-xxxxx'),
    ('CE01ISSM-RID16-03-CTDBPC000', 'CGINS-CTDBPC-xxxxx'),
    ('CE01ISSM-RID16-03-DOSTAD000', 'CGINS-DOSTAD-xxxxx'),
    ('CE01ISSM-RID16-02-FLORTD000', 'CGINS-FLORTD-xxxxx'),
    ('CE01ISSM-RID16-07-NUTNRB000', 'CGINS-NUTNRB-xxxxx'),
    ('CE01ISSM-RID16-01-OPTAAD000', 'CGINS-OPTAAD-xxxxx'),
    ('CE01ISSM-RID16-05-PCO2WB000', 'CGINS-PCO2WB-xxxxx'),
    ('CE01ISSM-RID16-06-PHSENG000', 'CGINS-PHSENG-xxxxx'),
    ('CE01ISSM-RID16-08-SPKIRB000', 'CGINS-SPKIRB-xxxxx'),
    ('CE01ISSM-RID16-04-VELPTA000', 'CGINS-VELPTA-xxxxx'),
    ('CE01ISSM-MFD35-04-ADCPTM000', 'CGINS-ADCPTM-xxxxx'),
    ('CE01ISSM-MFD35-04-WAVSSM000', 'CGINS-WAVSSM-xxxxx'),
    ('CE01ISSM-MFD37-06-CAMDSA000', 'CGINS-CAMDSA-xxxxx'),
    ('CE01ISSM-MFD37-03-CTDBPC000', 'CGINS-CTDBPC-xxxxx'),
    ('CE01ISSM-MFD37-03-DOSTAD000', 'CGINS-DOSTAD-xxxxx'),
    ('CE01ISSM-MFD37-01-OPTAAD000', 'CGINS-OPTAAD-xxxxx'),
    ('CE01ISSM-MFD35-05-PCO2WB000', 'CGINS-PCO2WB-xxxxx'),
    ('CE01ISSM-MFD35-06-PHSEND000', 'CGINS-PHSEND-xxxxx'),
    ('CE01ISSM-MFD35-02-PRESFA000', 'CGINS-PRESFA-xxxxx'),
    ('CE01ISSM-MFD35-01-VEL3DD000', 'CGINS-VEL3DD-xxxxx'),
    ('CE01ISSM-MFD37-07-ZPLSCC000', 'CGINS-ZPLSCC-xxxxx'),
]

PLATCON = ['CPM1', 'DCL17', 'DCL16', 'CPM3', 'DCL37', 'DCL36']
N_PLATCON = len(PLATCON)

DEPTH_BUOY_WELL = '0'
DEPTH_BUOY_INSHORE_CTDBP = '1.0'
DEPTH_BUOY_INSHORE_FLORT = '1.5'
DEPTH_BUOY_INSHORE_VELPT = '1.6'
DEPTH_NSIF = '7'
# depth on the MFN == water_depth, computed per deployment

ORBIT = 100  # watch circle orbit [m]; inshore (ISSM) convention
ASSEMBLY_TEMPLATE_REVISION = 'B'

SECTIONS = [('instruments', 'SB'), ('nsif', 'RI'), ('mfn', 'MF')]


@dataclass
class DeploymentResult:
    dep_num: int
    rows: list[dict[str, str]]
    sensor_uids: list[str]


def _prepare_keys_values(config: ConfigTable) -> tuple[list[str], list[str]]:
    n = config.n_rows
    keys = [
        config.get(r, 1).replace(' S/N', '') for r in range(1, n + 1)
    ]
    values = [config.get(r, VALUE_COL) for r in range(1, n + 1)]
    values = ['' if sl.is_not_deployed(v) else v for v in values]
    values = [sl.fix_serial(v) for v in values]
    return keys, values


def _instrument_serial_dict(
    keys: list[str], values: list[str],
) -> dict[str, str]:
    keys, start = sl.assign_section_prefixes(keys, SECTIONS)
    return sl.build_serial_dict(keys[start:], values[start:])


def _deployment_depth(refdes: str, water_depth: str) -> str:
    platform_code = refdes[9:11].upper()
    if platform_code == 'RI':
        depth = DEPTH_NSIF
    elif platform_code == 'MF':
        depth = water_depth
    else:
        depth = DEPTH_BUOY_WELL

    pc_instr = (refdes[9:11] + refdes[18:23]).upper()
    if pc_instr == 'SBCTDBP':
        depth = DEPTH_BUOY_INSHORE_CTDBP
    elif pc_instr == 'SBFLORT':
        depth = DEPTH_BUOY_INSHORE_FLORT
    elif pc_instr == 'SBVELPT':
        depth = DEPTH_BUOY_INSHORE_VELPT

    return depth


def build_deployment(
    config: ConfigTable, previous_version_number: str,
) -> DeploymentResult:
    meta = read_metadata(config)

    keys, values = _prepare_keys_values(config)
    serial_dict = _instrument_serial_dict(keys, values)
    platcon_serials = sl.platcon_serials(config, values, PLATCON)

    instrument_refdes = [rd for rd, _ in REFDES_SENSOR[N_PLATCON:]]
    ikeys = sl.refdes_ikeys(instrument_refdes)

    sensor_uids: list[str] = []
    for i, (refdes, template) in enumerate(REFDES_SENSOR):
        if i < N_PLATCON:
            serial = platcon_serials[i]
        else:
            ikey = ikeys[i - N_PLATCON]
            try:
                serial = serial_dict[ikey]
            except KeyError:
                raise ValueError(
                    f"Missing lookup key {ikey!r} for {refdes!r}. Check "
                    "config.xlsx: has the WAVSS row been inserted into "
                    "the MFN section (duplicate of the ADCPT S/N row, "
                    "relabeled 'WAVSS S/N')?") from None
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
