"""Calibration parsers for the PARAD instrument class.

PARAD's series don't share a source format or coefficient set, so
each series gets its own SeriesParser subclass and its own
calibration-record dataclass, all living in this one module:

- ParadJParser / ParadJCal: factory dev file, CC_Im/CC_a0/CC_a1.
  Ported from
  tools/matlab/Endurance_cal_scripts/parad/write_parad_dev_to_csv.m.
- ParadKParser / ParadKCal: Biospherical QSP-2200 calibration
  certificate, CC_dark_offset/CC_scale_wet. No Matlab source exists
  (README_parad.txt: "I now do these by hand"). The certificates are
  scanned images with no text layer, and OCR misreads them (serial
  20611 as 20641, dark 0.45 mV as "045"), so the operator transcribes
  the serial, calibration date, probe dark (mV) and wet calibration
  factor. The certificate file is still required, for the provenance
  note. Values are range-checked against every PARADK file in
  asset-management (dark 0.45-1.5 mV, wet 8.14e-18 to 1.13e-17 as of
  2026-09) with margin, which catches a dropped decimal point or a
  wrong exponent; review() warns when the wet factor moved more than
  WET_CHANGE_WARNING from the sensor's previous calibration.

Other instrument classes may not need this split at all: where a
class's series is purely a serial-number lookup against an
otherwise identical source format and coefficient set (the
CTDBP/DOSTA/FLORT/PRESF/OPTAA pattern), one class in that module's
parser.py can serve every series -- see common/series_parser.py.

Coefficient values in ParadJCal are carried through as the exact
strings found in the dev file, not round-tripped through float, so
that formatting (trailing zeros, significant figures) matches the
source document exactly -- the Matlab source does the same; it
never converts these fields to numeric type before writing them
back out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar

from asset_cal.common.csv_writer import CalCoefficient, write_cal_csv
from asset_cal.common.series_parser import SeriesParser, check_caldate

_CALDATE_PROVENANCE = "date in filename comes from factory devfile"

_SERIAL_PATTERN = re.compile(r"PARS-(\d+)")
_CALDATE_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2})")


@dataclass(frozen=True)
class ParadJCal:
    """Calibration coefficients parsed from a PARAD-J dev file.

    Attributes
    ----------
    serial_number : int
        Instrument serial number, parsed from the "PARS-nnn" token.
    series : str
        Always "J" for this parser.
    caldate : str
        Calibration date as YYYYMMDD, parsed from the "Created on:"
        line. Two-digit years are assumed to be 20xx.
    im : str
        Immersion coefficient, exact string as read from the file.
    a0 : str
        Dark offset coefficient, exact string as read from the file.
    a1 : str
        Scaling coefficient, exact string as read from the file.
    """

    serial_number: int
    series: str
    caldate: str
    im: str
    a0: str
    a1: str


class ParadJParser(SeriesParser[ParadJCal]):
    """Parses PARAD-J factory dev files."""

    class_code: ClassVar[str] = "PARAD"
    series: ClassVar[str] = "J"

    def parse(self, source_path: Path) -> ParadJCal:
        """Parse a PARAD-J factory dev file into a ParadJCal.

        Raises
        ------
        ValueError
            If the serial number, cal date, or any coefficient
            cannot be found in the file.
        """
        lines = source_path.read_text(encoding="ascii").splitlines()

        serial_number = _find_serial_number(lines)
        caldate = _find_caldate(lines)
        im = _find_coefficient(lines, "im=")
        a1 = _find_coefficient(lines, "a1=")
        a0 = _find_coefficient(lines, "a0=")

        return ParadJCal(
            serial_number=serial_number,
            series=self.series,
            caldate=caldate,
            im=im,
            a0=a0,
            a1=a1,
        )

    def write_csv(
        self, cal: ParadJCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a PARAD-J calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/PARADJ does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; PARAD-J calibration csvs "
                "are never written into a directory this script creates itself."
            )

        sn_str = f"{cal.serial_number:05d}"
        filename = f"CGINS-{self.class_code}{self.series}-{sn_str}__{cal.caldate}.csv"
        output_path = output_dir / filename

        coefficients = [
            CalCoefficient("CC_Im", cal.im, _CALDATE_PROVENANCE),
            CalCoefficient("CC_a0", cal.a0, "digital"),
            CalCoefficient("CC_a1", cal.a1, "digital"),
        ]
        return write_cal_csv(output_path, str(cal.serial_number), coefficients)


def _find_serial_number(lines: list[str]) -> int:
    for line in lines:
        match = _SERIAL_PATTERN.search(line)
        if match:
            return int(match.group(1))
    raise ValueError("Could not find 'PARS-<serial>' token in dev file.")


def _find_caldate(lines: list[str]) -> str:
    for line in lines:
        if "created" in line.lower():
            match = _CALDATE_PATTERN.search(line)
            if match:
                mm, dd, yy = match.groups()
                return f"20{yy}{int(mm):02d}{int(dd):02d}"
    raise ValueError("Could not find 'Created on:' date in dev file.")


def _find_coefficient(lines: list[str], label: str) -> str:
    for line in lines:
        fields = line.split("\t")
        if fields and fields[0].strip() == label:
            for field in fields[1:]:
                field = field.strip()
                if field:
                    float(field)  # validate it is actually numeric
                    return field
    raise ValueError(f"Could not find coefficient labeled '{label}' in dev file.")


# Plausible ranges, from every PARADK file in asset-management (dark 0.45-1.5 mV,
# wet 8.14e-18 to 1.13e-17) with margin.
DARK_OFFSET_RANGE_MV = (Decimal("0.1"), Decimal("3.0"))
SCALE_WET_RANGE = (Decimal("5e-18"), Decimal("2e-17"))
WET_CHANGE_WARNING = Decimal("0.10")

_PARADK_FILE = re.compile(r"^CGINS-PARADK-(\d+)__(\d{8})\.csv$")


@dataclass(frozen=True)
class ParadKCal:
    """Calibration values transcribed from a PARAD-K certificate.

    Attributes
    ----------
    serial_number : int
        Sensor serial number.
    series : str
        Always "K".
    caldate : str
        Calibration date, YYYYMMDD.
    dark_offset : str
        Probe dark (mV), as typed.
    scale_wet : str
        Wet calibration factor (V/(quanta/cm2-sec)), as typed.
    source_filename : str
        Certificate file name, for the provenance note.
    """

    serial_number: int
    series: str
    caldate: str
    dark_offset: str
    scale_wet: str
    source_filename: str


class ParadKParser(SeriesParser[ParadKCal]):
    """Builds PARAD-K csvs from values transcribed off a scanned certificate."""

    class_code: ClassVar[str] = "PARAD"
    series: ClassVar[str] = "K"
    requires_caldate: ClassVar[bool] = True
    transcribed_fields: ClassVar[tuple[str, ...]] = ("serial", "dark_offset", "scale_wet")

    def parse(
        self, source_path: Path, caldate: str | None = None, transcribed: dict[str, str] | None = None
    ) -> ParadKCal:
        """Validate transcribed PARAD-K values.

        Parameters
        ----------
        source_path : Path
            The certificate the values were typed from (not read).
        caldate : str | None
            Calibration date, YYYYMMDD.
        transcribed : dict[str, str] | None
            "serial", "dark_offset" (mV) and "scale_wet".

        Raises
        ------
        ValueError
            If a value is missing, not a number, or out of range.
        """
        caldate = check_caldate(caldate, "PARAD-K")
        values = transcribed or {}
        missing = [name for name in self.transcribed_fields if name not in values]
        if missing:
            raise ValueError(f"PARAD-K values missing: {missing}")
        serial = values["serial"]
        if not re.fullmatch(r"\d{4,6}", serial):
            raise ValueError(f"PARAD-K serial must be 4-6 digits; got {serial!r}")
        dark = _in_range("dark_offset", values["dark_offset"], DARK_OFFSET_RANGE_MV, "mV")
        wet = _in_range("scale_wet", values["scale_wet"], SCALE_WET_RANGE, "V/(quanta/cm2-sec)")
        return ParadKCal(
            serial_number=int(serial),
            series=self.series,
            caldate=caldate,
            dark_offset=dark,
            scale_wet=wet,
            source_filename=source_path.name,
        )

    def review(
        self, cal: ParadKCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> list[str]:
        """Warn when the wet factor moved a lot since the previous calibration."""
        folder = calibration_root / (output_dir_name or f"{self.class_code}{self.series}")
        earlier = []
        for path in folder.glob(f"CGINS-PARADK-*{cal.serial_number}__*.csv"):
            match = _PARADK_FILE.match(path.name)
            if match and int(match.group(1)) == cal.serial_number and match.group(2) < cal.caldate:
                earlier.append((match.group(2), path))
        if not earlier:
            return []
        date, path = max(earlier)
        previous = _read_value(path, "CC_scale_wet")
        if previous is None:
            return []
        change = abs(Decimal(cal.scale_wet) - previous) / previous
        if change <= WET_CHANGE_WARNING:
            return []
        return [
            f"scale_wet {cal.scale_wet} differs by {change:.0%} from {previous} in {path.name}; "
            "check the transcription against the certificate."
        ]

    def write_csv(
        self, cal: ParadKCal, calibration_root: Path, output_dir_name: str | None = None
    ) -> Path:
        """Write a PARAD-K calibration csv file into calibration_root.

        Raises
        ------
        FileNotFoundError
            If calibration_root/PARADK does not exist.
        """
        output_dir = calibration_root / (
            output_dir_name if output_dir_name is not None else f"{self.class_code}{self.series}"
        )
        if not output_dir.is_dir():
            raise FileNotFoundError(
                f"Expected existing directory {output_dir}; PARAD-K calibration csvs "
                "are never written into a directory this script creates itself."
            )
        filename = f"CGINS-{self.class_code}{self.series}-{cal.serial_number:05d}__{cal.caldate}.csv"
        coefficients = [
            CalCoefficient(
                "CC_dark_offset", cal.dark_offset, f"probe dark [mV]; transcribed from {cal.source_filename}"
            ),
            CalCoefficient("CC_scale_wet", cal.scale_wet, "[V/(quanta/cm2-sec)]"),
        ]
        return write_cal_csv(output_dir / filename, str(cal.serial_number), coefficients)


def _in_range(name: str, value: str, bounds: tuple[Decimal, Decimal], unit: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"PARAD-K {name} is not a number: {value!r}") from None
    low, high = bounds
    if not low <= number <= high:
        raise ValueError(
            f"PARAD-K {name} {value} {unit} is outside the plausible range {low} to {high}; "
            "check for a missing decimal point or a wrong exponent."
        )
    return value


def _read_value(path: Path, name: str) -> Decimal | None:
    for line in path.read_text(encoding="latin-1").splitlines()[1:]:
        fields = line.split(",")
        if len(fields) >= 3 and fields[1] == name:
            try:
                return Decimal(fields[2])
            except InvalidOperation:
                return None
    return None
