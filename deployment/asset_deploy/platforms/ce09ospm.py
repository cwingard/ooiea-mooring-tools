"""CE09OSPM (Washington Offshore Wire-Following Profiler Mooring) builder.

Ported from append_deploy_ce09ospm.m. Structurally different from the
surface mooring platforms: the sensor.uid lookup key for each reference
designator is given explicitly as a 3rd column in the refdes_sensor
table (an 8-character prefix of the config sheet's row label, e.g.
'MOPAK S/N' -> 'MOPAK S/') rather than derived positionally from the
reference designator, and there is no buoy/nsif/mfn section split --
every row (platcons included) is looked up through one flat dictionary.

Per the sub_append_platconUID_to_engAssetRecord.m docstring, profiler
mooring CGCON uids are not auto-appended to the eng bulk asset record
(SUPPORTS_PLATCON_APPEND = False) -- new profiler controller entries are
still added to asset management by hand.

Unlike every surface mooring platform, there is no watch-circle orbit
value for a profiler mooring; the deploy.csv 'orbit' column is left
blank, matching the MATLAB source (no orbit variable is ever defined,
and the 'orbit' column comment there literally says "no action needed").
"""
from __future__ import annotations

from dataclasses import dataclass

from asset_deploy import serial_lookup as sl
from asset_deploy.config_xlsx import VALUE_COL, ConfigTable
from asset_deploy.metadata import read_metadata

PLATFORM_CODE = 'CE09OSPM'
SUPPORTS_PLATCON_APPEND = False

REFDES_SENSOR: list[tuple[str, str, str]] = [
    ('CE09OSPM-SBS01-00-STCENG000', 'CGCON-BSTC01-xxxxx', 'End Cap '),
    ('CE09OSPM-SBS01-01-MOPAK0000', 'CGINS-MOPAK0-xxxxx', 'MOPAK S/'),
    ('CE09OSPM-WFP01-00-WFPENG000', 'CGCON-CWFPCE-xxxxx', 'CWFP MMP'),
    ('CE09OSPM-WFP01-01-VEL3DK000', 'CGINS-VEL3DK-xxxxx', 'Aquadopp'),
    ('CE09OSPM-WFP01-02-DOFSTK000', 'CGINS-DOFSTK-xxxxx', 'SBE43F S'),
    ('CE09OSPM-WFP01-03-CTDPFK000', 'CGINS-CTDPFK-xxxxx', 'SBE52-MP'),
    ('CE09OSPM-WFP01-04-FLORTK000', 'CGINS-FLORTK-xxxxx', 'BB2F S/N'),
    ('CE09OSPM-WFP01-05-PARADK000', 'CGINS-PARADK-xxxxx', 'PAR Sens'),
]

DEPTH_BUOY = '0'  # platcon STC1 and MOPAK (rows 1-2); all other rows use
                  # water_depth

ASSEMBLY_TEMPLATE_REVISION = 'B'


@dataclass
class DeploymentResult:
    dep_num: int
    rows: list[dict[str, str]]
    sensor_uids: list[str]


def _build_serial_dict(config: ConfigTable) -> dict[str, str]:
    """Ported from append_deploy_ce09ospm.m lines ~352-372.

    Note the final hyphen cleanup here removes hyphens outright (unlike
    the surface mooring platforms, which map a hyphen to a literal '0')
    -- that's how the McLane MMP-style serials ('SWE1234-G' etc.) end up
    formatted, and is reproduced verbatim from the MATLAB source.
    """
    n = config.n_rows
    keys = [(config.get(r, 1) + '00000000')[:8] for r in range(1, n + 1)]
    values = [config.get(r, VALUE_COL) for r in range(1, n + 1)]
    values = ['' if sl.is_not_deployed(v) else v for v in values]
    values = [
        v.replace('SWE', '').replace('-G', '').replace(' Rev G', '')
         .replace('43-', '0').replace('52-', '0').replace('-', '')
        for v in values
    ]
    values = [sl.fix_serial(v) for v in values]
    return sl.build_serial_dict(keys, values)


def build_deployment(
    config: ConfigTable, previous_version_number: str,
) -> DeploymentResult:
    meta = read_metadata(config)

    serial_dict = _build_serial_dict(config)

    sensor_uids: list[str] = []
    for refdes, template, ikey in REFDES_SENSOR:
        try:
            serial = serial_dict[ikey]
        except KeyError:
            raise ValueError(
                f'Missing lookup key {ikey!r} for {refdes!r}. Check that '
                'the config.xlsx row label matches exactly (first 8 '
                'characters).') from None
        sensor_uids.append(template.replace('xxxxx', serial))

    not_deployed = ['00000' in uid for uid in sensor_uids]
    sensor_uids = [
        '' if nd else uid for nd, uid in zip(not_deployed, sensor_uids)
    ]

    # node.uid: derived from the WFP platcon's sensor.uid (3rd row,
    # CGCON-CWFPCE-xxxxx -> CGVEH-CWFPCE-xxxxx), written out for every
    # row except the STC platcon (1st row) -- including MOPAK, which is
    # physically on the buoy, not the WFP. Reproduced verbatim from the
    # MATLAB source (C(2:length(RefDes), 10) = node.uid).
    wfp_platcon_uid = sensor_uids[2]
    node_uid = (wfp_platcon_uid.replace('CON', 'VEH')
                if wfp_platcon_uid else '')

    rows: list[dict[str, str]] = []
    for i, (refdes, _, _) in enumerate(REFDES_SENSOR):
        cuid_deploy = ('#' if not_deployed[i] else '') + meta.cruise_id
        depth = DEPTH_BUOY if i < 2 else meta.water_depth
        rows.append({
            'CUID_Deploy': cuid_deploy,
            'CUID_Recover': '',
            'Reference Designator': refdes,
            'deployedBy': '',
            'deploymentNumber': str(meta.dep_num),
            'deployment_depth': depth,
            'lat': meta.lat,
            'lon': meta.lon,
            'mooring.uid': meta.mooring_uid,
            'node.uid': node_uid if i >= 1 else '',
            'notes': 'Not Deployed' if not_deployed[i] else '',
            'orbit': '',
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
