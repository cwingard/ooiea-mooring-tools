"""Sea-Bird .btl parsing on SR2614 cast 1."""
from datetime import datetime
from pathlib import Path

import pytest

from asset_discrete.btl import BtlError, nmea_degrees, read_btl

BTL = Path(__file__).parent / 'data' / 'SR2614_01.btl'


def test_bottles_and_variables():
    b = read_btl(BTL)
    assert sorted(b.bottles) == list(range(1, 25))
    assert b.bottles[1]['PrDM'] == '79.454'
    assert b.bottles[1]['time'] == datetime(2026, 10, 3, 19, 47, 38)
    assert 'Ph' not in b.names


def test_nmea_and_calibrations():
    b = read_btl(BTL)
    assert b.start == pytest.approx((44.64, -124.3045))
    assert b.nmea_time == datetime(2026, 10, 3, 19, 37, 54)
    assert b.calibrations['T0'] == datetime(2025, 5, 8)
    assert b.calibrations['T1'] == datetime(2025, 5, 8)
    assert b.calibrations['C1'] == datetime(2025, 12, 23)
    assert b.calibrations['FL'] == datetime(2023, 10, 16)


def test_nmea_degrees():
    assert nmea_degrees('124 18.27 W') == pytest.approx(-124.3045)
    assert nmea_degrees('44 38.40 N') == pytest.approx(44.64)


def test_crlf_file(tmp_path):
    p = tmp_path / 'crlf.btl'
    p.write_bytes(BTL.read_bytes().replace(b'\n', b'\r\n'))
    assert len(read_btl(p).bottles) == 24


def test_missing_required_variable(tmp_path):
    p = tmp_path / 'bad.btl'
    p.write_text(BTL.read_text().replace(' PrDM ', ' PrXX '))
    with pytest.raises(BtlError, match='PrDM'):
        read_btl(p)
