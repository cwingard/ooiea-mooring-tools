"""Oxygen .LST reader and the lab join in the build."""
from pathlib import Path

import pytest

from asset_discrete.labs import LabError
from asset_discrete.labs.oxygen import read_oxygen
from asset_discrete.summary import BuildError, build

LST = Path(__file__).parent / 'data' / 'SR2614_O2_cast1.LST'


def write_lst(tmp_path: Path, *rows: str) -> Path:
    head = LST.read_text().splitlines()[:9]
    path = tmp_path / 'o2.LST'
    path.write_text('\n'.join([*head, *rows]) + '\n')
    return path


def test_read_oxygen():
    lab = read_oxygen(LST)
    assert [r.sample_id for r in lab.results] == ['49', '50', '51']
    first = lab.results[0]
    assert (first.cast, first.niskin, first.station, first.draw_temp) == (1, 2, '0001', 10.15)
    assert first.values == {'Discrete Oxygen [mL/L]': '2.328'}
    assert first.comment == 'OT 0.2810'
    assert lab.header['Expedition'] == 'SR2614'
    assert lab.header['Chemist'] == 'MA'


def test_duplicate_flask(tmp_path):
    row = '0001 01 02 0049 140.81  0.27374  0.27376  2.328 19.64 10.15 2.152 221127'
    with pytest.raises(LabError, match='already on line'):
        read_oxygen(write_lst(tmp_path, row, row))


def by_niskin(rows, k):
    return [r for r in rows if r['Niskin/Bottle Position'] == str(k)]


def test_build_with_oxygen(workbook, btl_dir):
    result = build(workbook, btl_dir, {'oxygen': LST})
    n2 = by_niskin(result.rows, 2)
    assert [r['Discrete Oxygen [mL/L]'] for r in n2] == ['2.328', '2.393', '2.327']
    assert [r['Discrete Oxygen Flag'] for r in n2] == ['*0000000000000100',   # received
                                                       '*0000000000001001',   # questionable + note, no bit 2
                                                       '*0000000000000100']
    assert n2[0]['Discrete Salinity Flag'] == '*0000000000000010'             # no salinity file: not received
    log = '\n'.join(result.log)
    assert 'lab comment "OT 0.2810"' in log
    assert 'lab station code is 0001' in log                                   # cast 1 is CE02


def test_lab_niskin_disagrees(workbook, btl_dir, tmp_path):
    lst = write_lst(tmp_path, '0002 01 03 0049 140.81  0.27374  0.27376  2.328 19.64 10.15 2.152 221127')
    with pytest.raises(BuildError, match='Niskin 3'):
        build(workbook, btl_dir, {'oxygen': lst})


def test_lab_result_not_drawn(workbook, btl_dir, tmp_path):
    lst = write_lst(tmp_path, '0002 01 02 0099 140.81  0.27374  0.27376  2.328 19.64 10.15 2.152 221127')
    with pytest.raises(BuildError, match='sample 99'):
        build(workbook, btl_dir, {'oxygen': lst})


def test_lab_for_other_cruise(workbook, btl_dir, tmp_path):
    lst = tmp_path / 'other.LST'
    lst.write_text(LST.read_text().replace('Expedition: SR2614', 'Expedition: SR2699'))
    with pytest.raises(BuildError, match='SR2699'):
        build(workbook, btl_dir, {'oxygen': lst})
