"""Build on a one-cast workbook, then check the result with the validator."""
import csv

import pytest

from asset_discrete.summary import BuildError, build, template_columns, write_outputs
from asset_discrete.validate_summary import Validator


def by_niskin(rows, k):
    return [r for r in rows if r['Niskin/Bottle Position'] == str(k)]


def test_rows_and_flags(workbook, btl_dir):
    rows = build(workbook, btl_dir).rows
    assert len(rows) == 4                                  # Niskin 1 + three oxygen replicates on Niskin 2
    n1, n2 = by_niskin(rows, 1), by_niskin(rows, 2)
    assert n1[0]['Niskin Flag'] == '*0000000000001001'    # leaking + published note
    assert n1[0]['Discrete Oxygen Flag'] == '*0000001000000000'   # not drawn
    assert [r['Discrete Oxygen Flag'] for r in n2] == ['*0000000000000010', '*0000000000001011',
                                                       '*0000000000000010']   # 50: questionable (bit 3) + note
    assert {r['Discrete Oxygen Replicate Flag'] for r in n2} == {'*0000000000010000'}
    assert n2[0]['Discrete Salinity Flag'] == '*0000000000000010'
    assert n2[1]['Discrete Salinity Flag'] == '*0000001000000000'
    assert n2[0]['CTD Conductivity 1 Flag'] == '*0000000010000100'   # corresponding discrete sample
    assert n2[1]['CTD Conductivity 1 Flag'] == '*0000000000000100'
    assert n2[0]['CTD Temperature 1 Flag'] == '*0000000001000100'    # calibration > 1 year
    assert n2[0]['Discrete Nutrients Flag'] == '*0000000000000011'   # drawn, not received + Notes sheet
    assert n2[0]['Start Latitude [degrees]'] == '44.64000'          # from the .btl NMEA header
    assert n2[0]['CTD Pressure [db]'] == '79.344'


def test_published_notes(workbook, btl_dir):
    notes = build(workbook, btl_dir).readme_notes
    assert 'SR2614, Cast 1, Bottle 1, Niskin Flag -- Air leak; sampled from Niskin 2' in notes
    assert any('Discrete Oxygen Flag -- Stopper popped out' in n for n in notes)
    assert any(n.startswith('SR2614, All Casts, All Bottles, Discrete Nutrients Flag') for n in notes)


def test_output_validates(workbook, btl_dir, tmp_path):
    rows = build(workbook, btl_dir).rows
    path = tmp_path / 'summary.csv'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=template_columns(), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    issues = Validator(cruises=None).check(path)
    assert [i for i in issues if i.severity == 'ERROR'] == []


def test_write_outputs_and_history(workbook, btl_dir, tmp_path):
    result = build(workbook, btl_dir)
    files = write_outputs(result, workbook, tmp_path, '1.00', 'Assembled.')
    assert [f.name for f in files] == ['Endurance-25_SR2614_Discrete_Summary.xlsx',
                                       'Endurance-25_SR2614_Discrete_Summary_README.txt',
                                       'Endurance-25_SR2614_Discrete_Summary_build_log.txt']
    readme = files[1].read_bytes()
    assert b'\r' not in readme
    write_outputs(build(workbook, btl_dir), workbook, tmp_path, '1.10', 'Added oxygen.')
    text = files[1].read_text()
    assert '1.00 (' in text and '1.10 (' in text
    with pytest.raises(BuildError, match='1.10'):
        write_outputs(build(workbook, btl_dir), workbook, tmp_path, '1.10', 'again')


def test_missing_btl(workbook, tmp_path):
    with pytest.raises(BuildError, match='not found'):
        build(workbook, tmp_path)
