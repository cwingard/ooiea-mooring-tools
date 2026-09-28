"""Agreement check between two printed values of the same coefficient.

Vendor documents and instrument captures print the same coefficient
at different precision (e.g. "-766.69" on a certificate and
"-7.666900e+02" on the instrument), and the last printed digit can
differ between them. Two values agree when they differ by no more
than one unit in the last printed place of the coarser of the two.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


def last_place(value: str) -> Decimal:
    """Size of one unit in the last printed place of value.

    Parameters
    ----------
    value : str
        A number as printed, e.g. "3.6592e-004" or "-766.69".

    Returns
    -------
    Decimal
        e.g. Decimal("1E-8") for "3.6592e-004".
    """
    try:
        exponent = Decimal(value.strip()).as_tuple().exponent
    except InvalidOperation:
        raise ValueError(f"Not a number: {value!r}") from None
    return Decimal(1).scaleb(exponent)


def values_agree(a: str, b: str) -> bool:
    """True when a and b differ by at most one unit in the coarser last place."""
    tolerance = max(last_place(a), last_place(b))
    return abs(Decimal(a.strip()) - Decimal(b.strip())) <= tolerance
