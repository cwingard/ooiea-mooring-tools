"""Config reader, label-based metadata, and bulk-record series resolution."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl
import pytest

from asset_deploy import bulk_records
from asset_deploy import serial_lookup as sl
from asset_deploy.config_xlsx import NOTE_COL, VALUE_COL, ConfigError, read_config
from asset_deploy.metadata import read_metadata

CONFIG = Path(__file__).parent / 'fixtures' / 'CE02SHSM-00021.xlsx'


def test_metadata_by_label():
    meta = read_metadata(read_config(CONFIG))
    assert meta.dep_num == 21
    assert meta.mooring_uid == 'CGMCE-02SHSM-00021'
    assert meta.cruise_id == 'SR2614'  # row 10 in the current template
    assert meta.start_date_time == '2026-09-30T12:00:00'
    assert meta.water_depth == '80'
    assert meta.platform_code == 'CE02SHSM'


def test_value_and_notes_columns():
    config = read_config(CONFIG)
    row = config.find_row('PlatCon Assm S/N')
    assert config.get(row, VALUE_COL) == '50013'
    assert config.get(row, NOTE_COL) == 'CPM1, DCL11, DCL12'


def test_date_cell_rejected(tmp_path: Path):
    wb = openpyxl.Workbook()
    wb.active.append(['Anchor Launch Date:', dt.datetime(2026, 9, 30)])
    path = tmp_path / 'bad.xlsx'
    wb.save(path)
    with pytest.raises(ConfigError, match='Anchor Launch Date'):
        read_config(path)


def _bulk(tmp_path: Path, uids: list[str]) -> Path:
    path = tmp_path / 'sensor_bulk_load-AssetRecord.csv'
    blank = ',' * (len(bulk_records.EXPECTED_BULK_HEADER) - 1)
    lines = [','.join(bulk_records.EXPECTED_BULK_HEADER)] + [u + blank for u in uids]
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def test_series_resolved(tmp_path: Path):
    bulk = _bulk(tmp_path, ['CGINS-PHSENG-02102', 'CGINS-OPTAAJ-00284'])
    out = bulk_records.resolve_sensor_uids(
        ['CGINS-PHSEND-02102', 'CGINS-OPTAAD-00284', 'CGCON-BCPM01-50013', ''], bulk)
    assert out == ['CGINS-PHSENG-02102', 'CGINS-OPTAAJ-00284', 'CGCON-BCPM01-50013', '']


def test_unresolvable_uids_raise(tmp_path: Path):
    bulk = _bulk(tmp_path, ['CGINS-DOSTAD-00134', 'CGINS-DOSTAJ-00134'])
    with pytest.raises(ValueError) as exc:
        bulk_records.resolve_sensor_uids(['CGINS-DOSTAD-00134', 'CGINS-MOPAK0-58515'], bulk)
    assert 'ambiguous' in str(exc.value)
    assert 'no match' in str(exc.value)


def test_ambiguous_serial_key_raises_only_when_looked_up():
    serials = sl.build_serial_dict(
        ['RIPHSEN', 'RIPHSEN', 'XEOS Kil', 'XEOS Kil', 'RIVELPT', 'RIVELPT'],
        ['02087', '02102', '11111', '22222', '11787', '11787'])
    assert serials['RIVELPT'] == '11787'  # duplicate row, same serial: fine
    with pytest.raises(ValueError, match='RIPHSEN'):
        serials['RIPHSEN']
