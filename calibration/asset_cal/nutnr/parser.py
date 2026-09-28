"""Calibration parser for the NUTNR instrument class (Satlantic ISUS/SUNA).

Ported from tools/matlab/Endurance_cal_scripts/nutnr/write_nutnr_cal_to_csv.m
and .../nutnr/rad_read_nutnr_calfile.m.

ISUS and SUNA calfiles share exactly the same format (per the Matlab
source's own comment), and B and J only differ in which series
letter lands in the output filename -- so this is one NutnrParser
class, registered under "NUTNR-B" and "NUTNR-J" with the series
fixed at construction time, same pattern as CTDBP/FLORT/PRESF. No
serial-number lookup or ISUS-vs-SUNA branching: the Matlab source's
seriesB/seriesJ lists (used only for SUNA; ISUS is always B) are NOT
ported, by the same reasoning as every other multi-series class.

IMPORTANT, confirmed against the real archive rather than assumed:
rad_read_nutnr_calfile.m returns two structs -- "cal" (all 256
wavelength channels) and "fit" (only the ~217-240nm channels used in
the actual nitrate-concentration fitting routine) -- and the write
script only captures "cal", using the FULL 256-channel arrays for
CC_wl/CC_eno3/CC_eswa/CC_di. This looks like it could be a bug (using
cal instead of fit) but is not: calibration/NUTNRB/
CGINS-NUTNRB-01056__20170923.csv's CC_wl array runs from 189.86 to
394+ nm, far outside the fitting window, confirming the full range is
genuinely what gets written. CC_lower/upper_wavelength_limit_for_
spectra_fit (217/240) are just metadata for downstream processing,
not a filter applied here.

Like OPTAA (and unlike most other classes), values are NOT passed
through as original-file text: they are parsed into floats and
re-serialized through fixed-precision formatting (%.2f for
wavelengths and cal_temp, %.8f for eno3/eswa/di) -- that's what the
Matlab source does, so NutnrCal stores floats.

parse() is a structural port and UNVERIFIED/UNTESTED: no real
calfile sample exists anywhere, including in the Matlab source's
comments. The wavelength-table read in particular (a
scientific-notation-stripping "E" replacement whose exact purpose is
unclear without a real file, followed by a giant vectorized token
read) is a best-effort translation, not validated behavior.

write_csv() is tested against small synthetic arrays (formatting and
alphabetical-ordering logic only -- the real archived file's arrays
are 256 elements long, impractical to embed in a test verbatim), but
the general shape (order, formatting, provenance placement) was
visually confirmed against the real 1056 file before writing this.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_HEADER_ROW = "h,wavelength,no3,swa,tswa,reference"
_WAVELENGTH_CHANNELS = 256


@dataclass(frozen=True)
class NutnrCal:
    """Calibration coefficients parsed from a NUTNR (ISUS/SUNA) calfile.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, from the first line of the
        calfile.
    series : str
        "B" or "J", as supplied by the caller -- not derived from
        instrument type or serial number.
    caldate : str
        Calibration date as YYYYMMDD, from the calfile's 4th line.
    cal_temp : float
        Factory calibration water temperature (T_CAL_SWA if
        present, else T_CAL), rounded to the millidegree.
    wvl, eno3, eswa, di : list[float]
        All 256 wavelength-channel values -- wavelengths, nitrate
        extinction coefficients, seawater extinction coefficients,
        and the reference distilled-water spectrum, respectively.
        NOT restricted to the fitting range -- see module docstring.
    source_filename : str
        Name of the source calfile, used in the CC_cal_temp
        provenance note.
    """

    serial_number: int
    series: str
    caldate: str
    cal_temp: float
    wvl: list[float] = field(default_factory=list)
    eno3: list[float] = field(default_factory=list)
    eswa: list[float] = field(default_factory=list)
    di: list[float] = field(default_factory=list)
    source_filename: str = ""


class NutnrParser(SeriesParser[NutnrCal]):
    """Parses NUTNR (Satlantic ISUS/SUNA) calfiles for a fixed series."""

    class_code: ClassVar[str] = "NUTNR"

    def __init__(self, series: str) -> None:
        self.series = series

    def parse(self, source_path: Path) -> NutnrCal:
        """Parse a NUTNR calfile into a NutnrCal.

        UNVERIFIED, UNTESTED -- see module docstring.

        Raises
        ------
        ValueError
            If the serial number, caldate, cal temp, or wavelength
            table cannot be parsed.
        """
        lines = source_path.read_text(encoding="ascii").splitlines()
        if len(lines) < 4:
            raise ValueError("Calfile has fewer than the expected 4 header lines.")

        serial_number = int(lines[0][7:11])
        caldate = _find_caldate(lines)
        cal_temp = _find_cal_temp(lines)
        wvl, eno3, eswa, di = _parse_wavelength_table(lines)

        return NutnrCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            cal_temp=cal_temp,
            wvl=wvl,
            eno3=eno3,
            eswa=eswa,
            di=di,
            source_filename=source_path.name,
        )

    def write_csv(
        self, cal: NutnrCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a NUTNR calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/NUTNR<series> does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; NUTNR calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_4char = f"{cal.serial_number:04d}"
        filename = f"CGINS-{self.class_code}{self.series}-0{sn_4char}__{cal.caldate}.csv"
        output_path = output_dir / filename

        provenance = f"date in filename comes from latest caldate within calfile {cal.source_filename}"
        values: dict[str, tuple[str, str]] = {
            "cal_temp": (f"{cal.cal_temp:.2f}", provenance),
            "di": (_format_array(cal.di, 8), ""),
            "eno3": (_format_array(cal.eno3, 8), ""),
            "eswa": (_format_array(cal.eswa, 8), ""),
            "lower_wavelength_limit_for_spectra_fit": ("217", ""),
            "upper_wavelength_limit_for_spectra_fit": ("240", ""),
            "wl": (_format_array(cal.wvl, 2), ""),
        }
        coefficients = [CalCoefficient(f"CC_{name}", value, note) for name, (value, note) in sorted(values.items())]

        return write_cal_csv(output_path, str(cal.serial_number), coefficients)


def _format_array(values: list[float], precision: int) -> str:
    formatted = ", ".join(f"{v:.{precision}f}" for v in values)
    return f'"[{formatted}]"'


def _find_caldate(lines: list[str]) -> str:
    """UNVERIFIED -- see module docstring."""
    date_str = lines[3][21:32]  # 'dd-mmm-yyyy', 11 chars
    if len(date_str) < 11:
        raise ValueError(f"Calfile line 4 too short to contain a caldate: {lines[3]!r}")
    day = date_str[0:2]
    month_abbr = date_str[3:6].lower()
    year = date_str[7:11]
    if month_abbr not in _MONTHS:
        raise ValueError(f"Unrecognized month abbreviation in caldate: {date_str!r}")
    month_num = _MONTHS.index(month_abbr) + 1
    return f"{year}{month_num:02d}{day}"


def _find_cal_temp(lines: list[str]) -> float:
    """UNVERIFIED -- see module docstring. Prefers T_CAL_SWA, falls
    back to T_CAL, matching the Matlab source."""
    tcal_swa = _find_labeled_temp(lines, "H,T_CAL_SWA", start=12, length=7)
    if tcal_swa is not None:
        return round(tcal_swa, 3)
    tcal = _find_labeled_temp(lines, "H,T_CAL ", start=8, length=7)
    if tcal is not None:
        return round(tcal, 3)
    raise ValueError("No T_CAL nor T_CAL_SWA value found in calfile.")


def _find_labeled_temp(lines: list[str], label: str, start: int, length: int) -> float | None:
    matches = [line for line in lines if line[: len(label)].lower() == label.lower()]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f"Too many {label!r} lines found in calfile.")
    text = matches[0].replace(",", " ") + " " * 8
    return float(text[start: start + length])


def _parse_wavelength_table(
    lines: list[str],
) -> tuple[list[float], list[float], list[float], list[float]]:
    """UNVERIFIED -- see module docstring."""
    header_idx = next((i for i, line in enumerate(lines) if line.strip().lower() == _HEADER_ROW), None)
    if header_idx is None:
        raise ValueError("Could not find the 'H,Wavelength,NO3,SWA,TSWA,Reference' header row.")

    data_lines = lines[header_idx + 1: header_idx + 1 + _WAVELENGTH_CHANNELS]
    if len(data_lines) < _WAVELENGTH_CHANNELS:
        raise ValueError(f"Expected {_WAVELENGTH_CHANNELS} wavelength table rows, found {len(data_lines)}.")

    cleaned = " ".join(line.replace("E", " ").replace(",", " ") for line in data_lines)
    tokens = cleaned.split()
    expected_count = _WAVELENGTH_CHANNELS * 5
    if len(tokens) != expected_count:
        raise ValueError(f"Expected {expected_count} numeric values in wavelength table, found {len(tokens)}.")

    values = [float(t) for t in tokens]
    wvl = values[0::5]
    eno3 = values[1::5]
    eswa = values[2::5]
    di = values[4::5]
    return wvl, eno3, eswa, di
