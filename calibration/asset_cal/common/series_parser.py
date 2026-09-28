"""Common interface for per-series calibration parsers.

An instrument class (parad, dosta, ...) may have more than one
series whose source-file format, coefficient set, or both differ
enough that they cannot share one parser function or one
calibration-record type. PARAD is the first example: series J reads
a factory dev file and reports CC_Im/CC_a0/CC_a1; series K reads a
PDF calibration certificate and reports a completely different pair
of coefficients (CC_dark_offset/CC_scale_wet).

Each (instrument class, series) combination gets its own
SeriesParser subclass and its own calibration-record dataclass. The
cli's PARSERS registry maps the exact "CLASS-SERIES" string (e.g.
"PARAD-J") to a SeriesParser instance, so dispatch never needs to
know what a given series' calibration record looks like internally
-- it only needs parse() and write_csv().

This does not replace the series_map.csv plan (Option A) for
instrument classes where series is purely a serial-number lookup
against an otherwise identical source format and coefficient set
(the CTDBP/DOSTA/FLORT/PRESF/OPTAA pattern). In that case a single
SeriesParser subclass can be registered under more than one
"CLASS-SERIES" key, with parse() determining the actual series
internally; the cli still checks parse()'s result against what the
caller asked for (see cli.generate_cal_csv).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Generic, TypeVar

CalRecordT = TypeVar("CalRecordT")


class SeriesParser(ABC, Generic[CalRecordT]):
    """Parse/write implementation for one instrument class and series.

    Subclasses are stateless -- parse() and write_csv() take
    everything they need as arguments -- so a single instance can
    be shared across every call and, where a class's series is
    determined by lookup rather than by format, registered under
    more than one "CLASS-SERIES" key.
    """

    class_code: ClassVar[str]
    requires_caldate: ClassVar[bool] = False
    """True when the source file does not contain the calibration date.

    Those parsers take parse(source_path, caldate=...) and the cli
    requires --caldate; every other parser reads the date from the
    file and the cli rejects --caldate for it.
    """
    accepts_qct: ClassVar[bool] = False
    """True when parse() can also take the QCT capture of the sensor.

    Those parsers take parse(source_path, qct_path=None | Path) and
    must raise ValueError if the vendor document and the capture
    disagree. The cli rejects --qct for every other parser.
    """

    @abstractmethod
    def parse(self, source_path: Path) -> CalRecordT:
        """Parse a vendor/QCT source file into a calibration record.

        The returned record must expose serial_number (int) and
        series (str) attributes; cli.generate_cal_csv reads both.
        """

    @abstractmethod
    def write_csv(
        self, cal: CalRecordT, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write cal's csv into calibration_root/output_dir_name.

        output_dir_name defaults to f"{class_code}{series}" when not
        given -- the folder that convention works for. Some classes
        (METCTD) have no such folder and must always be called with
        an explicit override.

        Must raise FileNotFoundError, not create the directory, if
        the resolved output directory does not already exist.
        """


def check_caldate(caldate: str | None, class_code: str) -> str:
    """Validate an operator-supplied calibration date.

    Parameters
    ----------
    caldate : str | None
        Calibration date as YYYYMMDD.
    class_code : str
        Instrument class, for the error message.

    Returns
    -------
    str
        The validated YYYYMMDD string.

    Raises
    ------
    ValueError
        If caldate is missing or is not a real YYYYMMDD date.
    """
    if caldate is None:
        raise ValueError(
            f"{class_code} source files do not contain the calibration date; "
            "supply it with --caldate YYYYMMDD (from the calibration certificate)."
        )
    try:
        datetime.strptime(caldate, "%Y%m%d")
    except ValueError:
        raise ValueError(f"caldate must be a valid YYYYMMDD date; got {caldate!r}") from None
    return caldate
