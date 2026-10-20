"""Shared csv writer for OOI Endurance/CGSN calibration coefficient files.

Every parser in this package produces the same four-column csv
format expected by ooi-integration: serial, name, value, notes.
This module owns that format so no per-instrument parser
reimplements it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CalCoefficient:
    """One row of a calibration csv file.

    Attributes
    ----------
    name : str
        Coefficient name, e.g. "CC_a0". Must already carry the
        "CC_" prefix expected by ooi-integration.
    value : str
        Coefficient value, pre-formatted as it should appear in the
        csv. Array values must already be JSON-formatted and
        wrapped in double quotes by the caller.
    notes : str
        Free-text notes column. Empty string for no notes.
    """

    name: str
    value: str
    notes: str = ""


def write_cal_csv(output_path: Path, serial: str, coefficients: list[CalCoefficient]) -> Path:
    """Write a calibration coefficient csv file.

    Parameters
    ----------
    output_path : Path
        Full path (including filename) of the csv file to write.
        Parent directory must already exist.
    serial : str
        Serial number string written into the first column of
        every row. Callers control formatting (zero-padding,
        prefixes, etc.) since conventions differ across instrument
        classes.
    coefficients : list[CalCoefficient]
        Rows to write, in order.

    Returns
    -------
    Path
        The path that was written (same as output_path).

    Notes
    -----
    Always written with LF line endings, on every platform: all
    OOI text files use Linux line endings. Without newline="\n",
    Path.write_text turns every "\n" into "\r\n" on Windows.
    """
    lines = ["serial,name,value,notes"]
    for coeff in coefficients:
        lines.append(f"{serial},{coeff.name},{coeff.value},{coeff.notes}")
    output_path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return output_path
