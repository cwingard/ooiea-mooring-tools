from __future__ import annotations

import pytest
from conftest import CONFIG_ROWS, SITE, write_config

from asset_ingest.cli import main
from asset_ingest.config_wiring import ConfigError
from asset_ingest.generate import GenerateError, generate
from asset_ingest.ingest_file import read_ingest_csv


def rows_by_refdes(rows):
    return {r.reference_designator[9:]: r for r in rows}


def test_fills_tokens_from_config(inputs):
    result = generate(inputs['config'], inputs['am'], inputs['templates'])
    d = rows_by_refdes(result.files[f'{SITE}_D00021_ingest.csv'])
    # MFD35 instrument logs on DCL36, taken from the sheet not the refdes
    assert '/D00021/cg_data/dcl36/presf/' in d['MFD35-02-PRESFB000'].filename_mask
    # two HYDGNs in one section are told apart by port
    assert '/dcl11/hyd1/' in d['SBD11-02-HYDGN0000'].filename_mask
    assert '/dcl12/hyd2/' in d['SBD12-03-HYDGN0000'].filename_mask
    # engineering row keeps its literal logger and its template state
    eng = d['MFD35-00-DCLENG000']
    assert not eng.active and eng.status == 'Pending' and '/dcl36/syslog/' in eng.filename_mask
    r = result.files[f'{SITE}_R00021_ingest.csv']
    assert all('/R00021/' in row.filename_mask for row in r)


def test_not_deployed_is_commented(inputs):
    result = generate(inputs['config'], inputs['am'], inputs['templates'])
    for rows in result.files.values():
        flort = rows_by_refdes(rows)['RID27-02-FLORTD000']
        assert not flort.active and flort.status == 'Not Deployed' and flort.notes == ''
    assert result.not_deployed == [f'{SITE}-RID27-02-FLORTD000']


def test_info_lists(inputs):
    result = generate(inputs['config'], inputs['am'], inputs['templates'])
    assert result.no_stream == [f'{SITE}-SBD11-06-METBKA002']
    assert [s.split()[0] for s in result.ignored_config] == ['FDCHP']


def test_moved_instrument_follows_config(inputs):
    rows = [('CTDBP DCL:Port #', '26:03', None) if r[0] == 'CTDBP DCL:Port #' else r for r in CONFIG_ROWS]
    rows = [('DCL Assm S/N', '0002', 'DCL26') if r[0] == 'DCL Assm S/N' else r for r in rows]
    rows.append(('DCL Assm S/N', '0031', 'DCL36'))
    config = write_config(inputs['tmp'] / 'moved.xlsx', rows)
    result = generate(config, inputs['am'], inputs['templates'])
    ctd = rows_by_refdes(result.files[f'{SITE}_D00021_ingest.csv'])['RID27-03-CTDBPC000']
    assert '/dcl26/ctdbp1/' in ctd.filename_mask


def test_dcl_not_a_logger_stops(inputs):
    rows = [('CTDBP DCL:Port #', '63:03', None) if r[0] == 'CTDBP DCL:Port #' else r for r in CONFIG_ROWS]
    config = write_config(inputs['tmp'] / 'typo.xlsx', rows)
    with pytest.raises(GenerateError, match='DCL63'):
        generate(config, inputs['am'], inputs['templates'])


def test_deployed_without_wiring_stops(inputs):
    rows = [r for r in CONFIG_ROWS if r[0] != 'PRESF DCL:Port #']
    config = write_config(inputs['tmp'] / 'nowire.xlsx', rows)
    with pytest.raises(GenerateError, match='MFD35-02-PRESFB000'):
        generate(config, inputs['am'], inputs['templates'])


def test_template_refdes_missing_from_am_stops(inputs):
    path = inputs['templates'] / f'{SITE}_D_ingest.csv'
    path.write_text(path.read_text() + f'p.x,/x/{{deployment}}/y,{SITE}-RID26-08-SPKIRB000,telemetered,Available,\n')
    with pytest.raises(GenerateError, match='SPKIRB000: in the templates but not'):
        generate(inputs['config'], inputs['am'], inputs['templates'])


def test_missing_deployment_in_am_stops(inputs):
    rows = [(a, f'{SITE}-00022', c) if a == 'Mooring S/N:' else (a, b, c) for a, b, c in CONFIG_ROWS]
    config = write_config(inputs['tmp'] / 'dep22.xlsx', rows)
    with pytest.raises(GenerateError, match='no deployment 22'):
        generate(config, inputs['am'], inputs['templates'])


def test_excel_time_cell_rejected(inputs):
    import datetime as dt
    rows = [(a, dt.time(12, 8), c) if a == 'FDCHP DCL:Port #' else (a, b, c) for a, b, c in CONFIG_ROWS]
    config = write_config(inputs['tmp'] / 'time.xlsx', rows)
    with pytest.raises(ConfigError, match='date/time'):
        generate(config, inputs['am'], inputs['templates'])


def test_cli_test_mode_and_replace(inputs, capsys):
    args = ['generate', '--config', str(inputs['config']), '--asset-management', str(inputs['am']),
            '--ingestion-csvs', str(inputs['ic']), '--templates', str(inputs['templates'])]
    folder = inputs['ic'] / SITE
    assert main(args + ['--mode', 'test']) == 0
    assert (folder / f'{SITE}_D00021_ingest_preview.csv').exists()
    assert not (folder / f'{SITE}_D00021_ingest.csv').exists()
    assert main(args) == 0
    header, rows = read_ingest_csv(folder / f'{SITE}_D00021_ingest.csv')
    assert len(rows) == 7
    assert main(args) == 2                      # refuses to overwrite
    assert 'use --replace' in capsys.readouterr().err
    assert main(args + ['--replace']) == 0


def test_profiler_without_wiring(tmp_path):
    """Profiler sheets have no DCL:Port rows and other section names."""
    site = 'CE09OSPM'
    templates = tmp_path / 'templates'
    templates.mkdir()
    omc = f'/omc_data/whoi/OMC/{site}/{{deployment}}'
    header = 'parser,filename_mask,reference_designator,data_source,status,notes'
    (templates / f'{site}_D_ingest.csv').write_text(
        f'{header}\np.ctd,{omc}/imm/mmp/C*.DAT,{site}-WFP01-03-CTDPFK000,telemetered,Available,\n')
    (templates / f'{site}_R_ingest.csv').write_text(
        f'{header}\np.ctd,{omc}/instrmts/CWFP*/*/C*.DAT,{site}-WFP01-03-CTDPFK000,recovered_wfp,Expected,\n')
    am = tmp_path / 'am'
    (am / 'deployment').mkdir(parents=True)
    (am / 'deployment' / f'{site}_Deploy.csv').write_text(
        f'deploymentNumber,Reference Designator,CUID_Deploy\n23,{site}-WFP01-03-CTDPFK000,SR2614\n')
    config = write_config(tmp_path / 'p.xlsx', [
        ('Reference Designator:', site, None), ('Mooring S/N:', f'{site}-00023', None),
        ('Instruments MMP', None, None), ('SBE52-MP S/N', '110', None)])
    result = generate(config, am, templates)
    (row,) = result.files[f'{site}_R00023_ingest.csv']
    assert row.active and row.filename_mask.startswith(f'/omc_data/whoi/OMC/{site}/R00023/instrmts/')


def _ctd_inputs(tmp_path, dosta_wiring: str, dosta_deployed: bool = True, ctd_deployed: bool = True):
    site = 'CE06ISSM'
    templates = tmp_path / 'templates'
    templates.mkdir()
    omc = f'/omc_data/whoi/OMC/{site}/{{deployment}}/cg_data/dcl{{dcl}}'
    header = 'parser,filename_mask,reference_designator,data_source,status,notes'
    rows = [f'p.ctd,{omc}/ctdbp2/*.ctdbp*.log,{site}-MFD37-03-CTDBPC000,telemetered,Available,',
            f'p.do,{omc}/ctdbp2/*.ctdbp*.log,{site}-MFD37-03-DOSTAD000,telemetered,Available,']
    for kind in 'DR':
        (templates / f'{site}_{kind}_ingest.csv').write_text('\n'.join([header] + rows) + '\n')
    am = tmp_path / 'am'
    (am / 'deployment').mkdir(parents=True)
    (am / 'deployment' / f'{site}_Deploy.csv').write_text(
        'deploymentNumber,Reference Designator,CUID_Deploy\n'
        f'22,{site}-MFD37-03-CTDBPC000,{"" if ctd_deployed else "#"}SR2614\n'
        f'22,{site}-MFD37-03-DOSTAD000,{"" if dosta_deployed else "#"}SR2614\n')
    config = write_config(tmp_path / 'c.xlsx', [
        ('Reference Designator:', site, None), ('Mooring S/N:', f'{site}-00022', None),
        ('DCL Assm S/N', '1', 'DCL36'), ('CPM-DCL Assm S/N', '2', 'CPM3, DCL37'),
        ('Instruments MFN', None, None),
        ('CTDBP DCL:Port #', '36:03', None),
        ('DOSTA DCL:Port #', dosta_wiring, 'Connected to CTDBP')])
    return config, am, templates, site


def test_dosta_follows_its_ctd(tmp_path):
    config, am, templates, site = _ctd_inputs(tmp_path, '37:03')
    result = generate(config, am, templates)
    rows = rows_by_refdes(result.files[f'{site}_D00022_ingest.csv'])
    assert '/dcl36/ctdbp2/' in rows['MFD37-03-DOSTAD000'].filename_mask
    assert len(result.follows_ctd) == 1 and 'DCL37' in result.follows_ctd[0]
    assert result.ignored_config == []


def test_dosta_without_own_wiring_row(tmp_path):
    config, am, templates, site = _ctd_inputs(tmp_path, '')
    result = generate(config, am, templates)
    assert '/dcl36/' in rows_by_refdes(result.files[f'{site}_R00022_ingest.csv'])['MFD37-03-DOSTAD000'].filename_mask
    assert result.follows_ctd == []


def test_dosta_deployed_without_its_ctd_stops(tmp_path):
    config, am, templates, site = _ctd_inputs(tmp_path, '36:03', ctd_deployed=False)
    with pytest.raises(GenerateError, match='its CTDBP'):
        generate(config, am, templates)
