"""Tests for asset_cal.common.compare."""
from asset_cal.common.compare import values_agree


def test_different_precision_agrees() -> None:
    assert values_agree("-766.69", "-7.666900e+02")
    assert values_agree("3.6592e-004", "3.659160e-004")


def test_last_digit_of_coarser_value_may_differ() -> None:
    assert values_agree("-3.6088e-003", "-3.608700e-03")


def test_real_difference_disagrees() -> None:
    assert not values_agree("3.6592e-004", "3.801300e-04")
    assert not values_agree("-3.6090e-003", "-3.608700e-03")
