"""Synthetic inputs: a small CE07SHSM-like config workbook, asset_management
deployment CSV, templates and ingestion-csvs folder under tmp_path."""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SITE = 'CE07SHSM'
HEADER = 'parser,filename_mask,reference_designator,data_source,status,notes'
OMC = f'/omc_data/whoi/OMC/{SITE}/{{deployment}}/cg_data'

TEMPLATE_D = [
    HEADER,
    f'# p.eng,{OMC}/dcl36/syslog/*.syslog.log,{SITE}-MFD35-00-DCLENG000,telemetered,Pending,eng',
    f'p.presf,{OMC}/dcl{{dcl}}/presf/*.presf.log,{SITE}-MFD35-02-PRESFB000,telemetered,Available,',
    f'p.hyd,{OMC}/dcl{{dcl}}/hyd1/*.hyd*.log,{SITE}-SBD11-02-HYDGN0000,telemetered,Available,',
    f'p.hyd,{OMC}/dcl{{dcl}}/hyd2/*.hyd*.log,{SITE}-SBD12-03-HYDGN0000,telemetered,Available,',
    f'p.ctd,{OMC}/dcl{{dcl}}/ctdbp1/*.ctdbp*.log,{SITE}-RID27-03-CTDBPC000,telemetered,Available,',
    f'p.flort,{OMC}/dcl{{dcl}}/flort/*.flort.log,{SITE}-RID27-02-FLORTD000,telemetered,Available,',
    f'p.metbk,{OMC}/dcl{{dcl}}/metbk/*.metbk.log,{SITE}-SBD11-06-METBKA000,telemetered,Available,',
]
TEMPLATE_R = [
    HEADER,
    f'p.presf_r,{OMC}/dcl{{dcl}}/presf/*.presf.log,{SITE}-MFD35-02-PRESFB000,recovered_host,Expected,',
    f'p.presf_i,/omc_data/whoi/OMC/{SITE}/{{deployment}}/instrmts/dcl{{dcl}}/PRESF*/*.hex,'
    f'{SITE}-MFD35-02-PRESFB000,recovered_inst,Expected,',
    f'p.flort_r,{OMC}/dcl{{dcl}}/flort/*.flort.log,{SITE}-RID27-02-FLORTD000,recovered_host,Expected,',
]

DEPLOYED = {
    'MFD35-00-DCLENG000': True, 'MFD35-02-PRESFB000': True, 'SBD11-02-HYDGN0000': True,
    'SBD12-03-HYDGN0000': True, 'RID27-03-CTDBPC000': True, 'RID27-02-FLORTD000': False,
    'SBD11-06-METBKA000': True, 'SBD11-06-METBKA002': True,
}

CONFIG_ROWS = [
    ('Reference Designator:', SITE, None),
    ('Mooring S/N:', f'{SITE}-00021', None),
    ('Platform Control', None, None),
    ('PlatCon Assm S/N', '50014', 'CPM1, DCL11, DCL12'),
    ('CPM-DCL Assm S/N', '0015', 'CPM2, DCL27'),
    ('DCL Assm S/N', '0031', 'DCL36'),
    ('Instruments Buoy', None, None),
    ('FDCHP DCL:Port #', '12:08', None),
    ('FDCHP S/N', '24', None),
    ('HYDGN DCL:Port #', '11:02', None),
    ('HYDGN S/N', 'A', None),
    ('HYDGN DCL:Port #', '12:03', None),
    ('HYDGN S/N', 'B', None),
    ('METBK DCL:Port #', '11:06', None),
    ('METBK S/N', '28', None),
    ('Instruments NSIF', None, None),
    ('CTDBP DCL:Port #', '27:03', None),
    ('CTDBP S/N', '16-50010', None),
    ('FLORT DCL:Port #', '27:02', None),
    ('FLORT S/N', 'N/A', None),
    ('Instruments MFN', None, None),
    ('PRESF DCL:Port #', '36:02', None),
    ('PRESF S/N', '26-1384', None),
]


def write_config(path: Path, rows: list[tuple]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return path


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, Path]:
    templates = tmp_path / 'templates'
    templates.mkdir()
    (templates / f'{SITE}_D_ingest.csv').write_text('\n'.join(TEMPLATE_D) + '\n')
    (templates / f'{SITE}_R_ingest.csv').write_text('\n'.join(TEMPLATE_R) + '\n')

    am = tmp_path / 'am'
    (am / 'deployment').mkdir(parents=True)
    lines = ['deploymentNumber,Reference Designator,CUID_Deploy']
    lines += [f'21,{SITE}-{rd},{"" if dep else "#"}SR2614' for rd, dep in DEPLOYED.items()]
    (am / 'deployment' / f'{SITE}_Deploy.csv').write_text('\n'.join(lines) + '\n')

    ic = tmp_path / 'ic'
    (ic / SITE).mkdir(parents=True)
    config = write_config(tmp_path / f'{SITE}-00021.xlsx', CONFIG_ROWS)
    return {'templates': templates, 'am': am, 'ic': ic, 'config': config, 'tmp': tmp_path}
