"""Build and check the OOI Discrete Summary for an Endurance Array cruise.

`new` writes a blank transcription workbook, `migrate` moves a filled one to
the current layout, `build` turns a workbook plus the cruise's Sea-Bird .btl
files into the formatted summary xlsx and its README, and `validate` checks
any Discrete Summary CSV against the OOI-wide format. See README.md.
"""
from pathlib import Path

REFERENCE = Path(__file__).resolve().parent / 'reference'
