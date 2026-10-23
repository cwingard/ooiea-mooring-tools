"""Flag strings and the reference flag table."""
import pytest

from asset_discrete.flags import bits_by_text, choices, flag


def test_flag_string():
    assert flag(2) == '*0000000000000100'
    assert flag(0, 1, 15) == '*1000000000000011'


def test_flag_bit_range():
    with pytest.raises(ValueError):
        flag(16)


def test_sample_not_drawn_is_a_discrete_sample_flag():
    # flags.csv as received had this text in the Niskin column (fixed 2026-10-22)
    assert bits_by_text('discreteSampleFlags')['Sample not drawn for this measurement from this bottle'] == 9
    assert 'Sample not drawn for this measurement from this bottle' not in bits_by_text('niskinFlags')


def test_choices_leave_out_automatic_bits():
    picks = choices('discreteSampleFlags')
    assert 'Questionable measurement' in picks
    assert not any(p.startswith(('Acceptable', 'Sample for this measurement', 'Sample not drawn')) for p in picks)
    assert 'No problems noted' not in choices('niskinFlags')
