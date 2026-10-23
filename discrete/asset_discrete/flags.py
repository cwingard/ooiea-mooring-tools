"""Flag definitions (reference/flags.csv) and 16-bit flag strings.

A flag is written as '*' followed by 16 characters, bit 0 rightmost. The
text for each bit comes only from reference/flags.csv; nothing else defines
flag meanings.
"""
from __future__ import annotations

import csv
from functools import cache

from asset_discrete import REFERENCE

# flags.csv column -> heading used in the README and the xlsx flag sheet
FLAG_TYPES = {'castFlags': 'Cast Flags', 'CTDFileFlags': 'CTD File Flags',
              'CTDParameterFlags': 'CTD Parameter Flags', 'niskinFlags': 'Niskin Flags',
              'discreteSampleFlags': 'Discrete Sample Flags',
              'discreteReplicateFlags': 'Discrete Replicate Flags'}

# bits the build sets itself; they are never picked in the workbook
NOTES_BIT, NOT_RECEIVED_BIT, OK_BIT, OLD_CAL_BIT, MATCH_BIT, NOT_DRAWN_BIT = 0, 1, 2, 6, 7, 9
AUTOMATIC = {'discreteSampleFlags': {NOTES_BIT, NOT_RECEIVED_BIT, OK_BIT, NOT_DRAWN_BIT}}


@cache
def definitions() -> list[dict[str, str]]:
    """Rows of reference/flags.csv (bitPosition plus one column per type)."""
    with open(REFERENCE / 'flags.csv', newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def bits_by_text(flag_type: str) -> dict[str, int]:
    """Map flag text -> bit for one flag type, without placeholders."""
    return {row[flag_type]: int(row['bitPosition']) for row in definitions()
            if row[flag_type] not in ('Unassigned', 'Notes/Other')}


def choices(flag_type: str) -> list[str]:
    """Flag texts a person may pick in the workbook (problems only).

    Excludes Notes/Other, the 'acceptable' bit 2 (a blank cell means that)
    and bits the build sets itself.
    """
    skip = {NOTES_BIT, OK_BIT} | AUTOMATIC.get(flag_type, set())
    return [text for text, bit in bits_by_text(flag_type).items() if bit not in skip]


def flag(*bits: int) -> str:
    """Return the 16-bit flag string with the given bits set.

    Parameters
    ----------
    *bits : int
        Bit positions 0-15; bit 0 is the rightmost character.

    Returns
    -------
    str
        For example flag(2) -> '*0000000000000100'.
    """
    chars = ['0'] * 16
    for b in bits:
        if not 0 <= b <= 15:
            raise ValueError(f'flag bit out of range: {b}')
        chars[15 - b] = '1'
    return '*' + ''.join(chars)
