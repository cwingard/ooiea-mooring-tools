"""Shared fixtures: a one-cast transcription workbook built on SR2614 cast 1."""
from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

import pytest

from asset_discrete.workbook import make_workbook, write_rows

DATA = Path(__file__).parent / 'data'


@pytest.fixture
def btl_dir() -> Path:
    return DATA


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    """SR2614 cast 1 (CE02) with a leaking Niskin 1 and samples on Niskin 2."""
    wb = make_workbook()
    write_rows(wb['Cruise'], [dict(cruise='SR2614', expedition='Endurance 25', ship='R/V Sally Ride',
                                   start_date='2026-10-03', end_date='2026-10-05')])
    write_rows(wb['Cast Log'], [dict(cruise='SR2614', cast=1, site='CE02', target_assets='CE02SHSM-00021',
                                     ctd_file='SR2614_01.hex', date_utc=datetime(2026, 10, 3),
                                     start_time_utc=time(19, 36), start_lat_deg=44, start_lat_min=38.403,
                                     start_lon_deg=-124, start_lon_min=18.266, start_water_depth_m=79.2)])
    write_rows(wb['Niskin Log'], [
        dict(cruise='SR2614', cast=1, niskin=1, trip_time_utc='19:47', trip_depth_m=78.6, temp_c=9.41,
             salinity_psu=33.76, niskin_flag='Leaking', notes='Air leak; sampled from Niskin 2'),
        dict(cruise='SR2614', cast=1, niskin=2, trip_time_utc='19:48', trip_depth_m=78.6, temp_c=9.41,
             salinity_psu=33.76, oxygen_samples='49, 50, 51', draw_temp_c=10.15, salinity_samples='1',
             nutrient_samples='1, 2')])
    write_rows(wb['Sample Issues'], [dict(cruise='SR2614', cast=1, niskin=2, analysis='oxygen', sample_id=50,
                                          action='flag', sample_flag='Questionable measurement',
                                          reason='Stopper popped out during the draw')])
    write_rows(wb['Notes'], [dict(cruise='SR2614', cast='All', niskin='All', applies_to='Discrete Nutrients Flag',
                                  note='Test note for all nutrients')])
    path = tmp_path / 'SR2614_Transcription.xlsx'
    wb.save(path)
    return path
