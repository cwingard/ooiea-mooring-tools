from __future__ import annotations

from conftest import HEADER, SITE

from asset_ingest.check import check_site
from asset_ingest.ingest_file import format_row, read_ingest_csv

OMC = f'/omc_data/whoi/OMC/{SITE}'


def write(folder, name, lines):
    (folder / name).write_text('\n'.join([HEADER] + lines) + '\n')


def messages(findings):
    return [f.message for f in findings]


def test_clean_pair_has_no_findings(inputs):
    folder = inputs['ic'] / SITE
    write(folder, f'{SITE}_D00021_ingest.csv', [
        f'p,{OMC}/D00021/cg_data/dcl36/presf/*.log,{SITE}-MFD35-02-PRESFB000,telemetered,Available,'])
    write(folder, f'{SITE}_R00021_ingest.csv', [
        f'p,{OMC}/R00021/instrmts/dcl36/PRESF*/*.hex,{SITE}-MFD35-02-PRESFB000,recovered_inst,Expected,'])
    assert check_site(inputs['ic'], SITE, deployment=21) == []


def test_row_level_findings(inputs):
    folder = inputs['ic'] / SITE
    write(folder, f'{SITE}_R00019_ingest.csv', [
        f'p,{OMC}/R00018/cg_data/dcl36/presf/*.log,{SITE}-MFD35-02-PRESFB000,recovered_host,Available,',
        f'p,{OMC}/R00019/cg_data/dcl37/optaa/*.log,{SITE}-MFD37-01-OPTAAD000,recovered_host,Not Available,x',
        f'p,{OMC}/R00019/cg_data/dcl37/zplsc/*.log,{SITE}-MFD37-07-ZPLSCC000,telemetered,Not Deployed,',
    ])
    found = messages(check_site(inputs['ic'], SITE))
    assert any('mask does not contain /CE07SHSM/R00019/' in m for m in found)
    assert any("status 'Not Available'" in m for m in found)
    assert any("data_source 'telemetered' in a R file" in m for m in found)
    assert any("active row marked 'Not Deployed'" in m for m in found)


def test_dcl_mismatch_between_d_and_r(inputs):
    # the R00019 MFD35-06 case: recovered_host on dcl37, everything else dcl36
    folder = inputs['ic'] / SITE
    rd = f'{SITE}-MFD35-06-PHSEND000'
    write(folder, f'{SITE}_D00019_ingest.csv', [
        f'p,{OMC}/D00019/cg_data/dcl36/phsen2/*.log,{rd},telemetered,Available,'])
    write(folder, f'{SITE}_R00019_ingest.csv', [
        f'p,{OMC}/R00019/cg_data/dcl37/phsen2/*.log,{rd},recovered_host,Available,',
        f'p,{OMC}/R00019/instrmts/dcl36/PHSEN*/*.txt,{rd},recovered_inst,Available,'])
    found = messages(check_site(inputs['ic'], SITE))
    assert len(found) == 1 and 'DCL differs' in found[0] and 'dcl37 at CE07SHSM_R00019_ingest.csv:2' in found[0]


def test_against_asset_management(inputs):
    folder = inputs['ic'] / SITE
    write(folder, f'{SITE}_D00021_ingest.csv', [
        f'p,{OMC}/D00021/cg_data/dcl27/flort/*.log,{SITE}-RID27-02-FLORTD000,telemetered,Available,'])
    # PRESF has a stream (row in an older file) but no row in 21
    write(folder, f'{SITE}_D00020_ingest.csv', [
        f'p,{OMC}/D00020/cg_data/dcl36/presf/*.log,{SITE}-MFD35-02-PRESFB000,telemetered,Available,'])
    found = messages(check_site(inputs['ic'], SITE, inputs['am']))
    assert any('FLORTD000: active but not deployed' in m for m in found)
    assert any('PRESFB000: deployed but has no ingestion row' in m for m in found)
    # METBKA002 is deployed but never has a row anywhere: not reported
    assert not any('METBKA002' in m for m in found)


def test_comment_round_trip(tmp_path):
    path = tmp_path / f'{SITE}_D00001_ingest.csv'
    line = f'# ,{OMC}/D00001/cg_data/dcl37/camds/*.png,{SITE}-MFD37-06-CAMDSA000,telemetered,Pending,No parser'
    path.write_text(HEADER + '\n' + line + '\n')
    header, rows = read_ingest_csv(path)
    assert not rows[0].active and rows[0].parser == ''
    assert format_row(rows[0]) == line


def test_ctd_recorded_instrument_on_other_dcl(inputs):
    # the CE09OSSM D00020 case: CTDBP on dcl36, its DOSTA on dcl37
    folder = inputs['ic'] / SITE
    write(folder, f'{SITE}_D00020_ingest.csv', [
        f'p,{OMC}/D00020/cg_data/dcl36/ctdbp*/*.log,{SITE}-MFD37-03-CTDBPE000,telemetered,Available,',
        f'p,{OMC}/D00020/cg_data/dcl37/ctdbp*/*.log,{SITE}-MFD37-03-DOSTAD000,telemetered,Available,'])
    found = messages(check_site(inputs['ic'], SITE))
    assert found == [f'{SITE}-MFD37-03-DOSTAD000: on dcl37 but its CTDBP {SITE}-MFD37-03-CTDBPE000 is on dcl36']
