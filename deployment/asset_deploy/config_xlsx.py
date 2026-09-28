"""Reader for per-deployment configuration workbooks (config.xlsx).

The workbook is read exactly as the technicians maintain it: column A =
label, column B = value, column C = notes (for the Platform Control rows,
the platcon bottle assignment, e.g. 'CPM1, DCL11, DCL12'). No hand
preparation of the sheet is required or supported.

Cells are returned as stripped strings. Integer-valued numeric cells are
written without a trailing '.0'. Date and time cells are rejected: Excel
silently coerces entries like '12:08' or '2026-09-30', and the resulting
values pass downstream string handling without error but are wrong.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import openpyxl

LABEL_COL = 1
VALUE_COL = 2
NOTE_COL = 3


class ConfigError(ValueError):
    """A config workbook cannot be used as-is."""


class ConfigTable:
    """1-indexed [row, col] accessor over a config sheet (columns A:C)."""

    def __init__(self, rows: list[list[str]]) -> None:
        self._rows = rows

    def get(self, row: int, col: int) -> str:
        return self._rows[row - 1][col - 1]

    def column(self, col: int) -> list[str]:
        return [r[col - 1] for r in self._rows]

    def find_row(self, label: str) -> int:
        """1-indexed row whose label equals `label`.

        Comparison ignores case and surrounding whitespace. Exactly one
        row must match.
        """
        target = label.strip().lower()
        matches = [i + 1 for i, r in enumerate(self._rows) if r[LABEL_COL - 1].lower() == target]
        if len(matches) != 1:
            raise ConfigError(f'Expected exactly one row labeled {label!r}, found {len(matches)}')
        return matches[0]

    @property
    def n_rows(self) -> int:
        return len(self._rows)


def _to_text(value: object, row: int, col: int, label: str) -> str:
    if value is None:
        return ''
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        raise ConfigError(
            f'Row {row} ({label!r}), column {col}: Excel stored {value!r} as a '
            f'{type(value).__name__}; re-enter the cell as text')
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def read_config(path: str | Path, sheet_name: str | None = None, max_row: int = 500) -> ConfigTable:
    """Read columns A:C of a config workbook into a ConfigTable.

    Parameters
    ----------
    path : str or Path
        Path to the config.xlsx file.
    sheet_name : str, optional
        Worksheet to read; defaults to the active sheet.
    max_row : int
        Last row to read.

    Returns
    -------
    ConfigTable
    """
    workbook = openpyxl.load_workbook(path, data_only=True)
    sheet = workbook[sheet_name] if sheet_name else workbook.active

    rows: list[list[str]] = []
    for r, cells in enumerate(
        sheet.iter_rows(min_row=1, max_row=max_row, max_col=NOTE_COL, values_only=True), start=1,
    ):
        label = '' if cells[0] is None else str(cells[0]).strip()
        rows.append([_to_text(v, r, c, label) for c, v in enumerate(cells, start=1)])
    return ConfigTable(rows)
