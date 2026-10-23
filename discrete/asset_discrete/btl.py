"""Sea-Bird .btl (Bottle Summary) parser.

Variables are read by their header names, never by position. Required
variables missing from the file stop the run: that is the cue to fix the
ship's SBE Data Processing setup, not to work around it here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# .btl variable -> (summary column, decimals written)
CTD_COLUMNS = {
    'PrDM': ('CTD Pressure [db]', 3), 'DepSM': ('CTD Depth [m]', 3), 'Latitude': ('CTD Latitude [deg]', 5),
    'Longitude': ('CTD Longitude [deg]', 5), 'T090C': ('CTD Temperature 1 [deg C]', 4),
    'T190C': ('CTD Temperature 2 [deg C]', 4), 'C0S/m': ('CTD Conductivity 1 [S/m]', 6),
    'C1S/m': ('CTD Conductivity 2 [S/m]', 6), 'Sal00': ('CTD Salinity 1 [psu]', 4),
    'Sal11': ('CTD Salinity 2 [psu]', 4), 'Sbeox0ML/L': ('CTD Oxygen [mL/L]', 4),
    'OxsolML/L': ('CTD Oxygen Saturation [mL/L]', 5), 'FlSP': ('CTD Fluorescence [mg/m^3]', 4),
    'CStarAt0': ('CTD Beam Attenuation [1/m]', 4), 'CStarTr0': ('CTD Beam Transmission [%]', 4),
    'Ph': ('CTD pH', 3)}
OPTIONAL = {'Ph'}
REQUIRED = [v for v in CTD_COLUMNS if v not in OPTIONAL]

# XMLCON sensor element -> short key; T and C get 0/1 in channel order
SENSOR_TAGS = {'TemperatureSensor': 'T', 'ConductivitySensor': 'C', 'PressureSensor': 'P',
               'OxygenSensor': 'O2', 'FluoroSeapointSensor': 'FL', 'WET_LabsCStar': 'TR'}
SENSOR_NAMES = {'P': 'pressure', 'T0': 'temperature 1', 'T1': 'temperature 2', 'C0': 'conductivity 1',
                'C1': 'conductivity 2', 'O2': 'oxygen', 'FL': 'fluorometer', 'TR': 'transmissometer',
                'PH': 'pH'}
CAL_FORMATS = ('%d-%b-%Y', '%d-%b-%y', '%b %d %Y', '%d %b %Y', '%m/%d/%Y')


class BtlError(ValueError):
    """The .btl file cannot be used as it is."""


@dataclass
class BtlFile:
    """One cast's bottle summary."""
    path: Path
    names: list[str]
    bottles: dict[int, dict[str, str | datetime]]
    calibrations: dict[str, datetime] = field(default_factory=dict)
    start: tuple[float, float] | None = None
    nmea_time: datetime | None = None


def nmea_degrees(text: str) -> float:
    """Convert an NMEA header position such as '44 38.40 N' to degrees.

    West and south are negative.
    """
    deg, minutes, hemi = text.split()
    value = int(deg) + float(minutes) / 60
    return -value if hemi.upper() in ('W', 'S') else value


def _cal_date(text: str, path: Path, sensor: str) -> datetime:
    for fmt in CAL_FORMATS:
        try:
            return datetime.strptime(text.strip().title(), fmt)
        except ValueError:
            pass
    raise BtlError(f'{path.name}: cannot read calibration date {text!r} for {SENSOR_NAMES.get(sensor, sensor)}')


def read_btl(path: str | Path) -> BtlFile:
    """Read a Sea-Bird .btl file.

    Parameters
    ----------
    path : str or Path
        The .btl file (any line endings).

    Returns
    -------
    BtlFile
        Bottle averages keyed by bottle position (values as text, plus
        'time'), sensor calibration dates from the embedded XMLCON, and the
        NMEA start position/time when the header has them.

    Raises
    ------
    BtlError
        If a required variable is missing or a calibration date is unreadable.
    """
    path = Path(path)
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    cal, nmea, kind, counts = {}, {}, None, {'T': 0, 'C': 0}
    for ln in lines:
        m = re.match(r'\* NMEA (Latitude|Longitude|UTC \(Time\)) = (.+)$', ln)
        if m:
            nmea[m[1]] = m[2].strip()
        m = re.search(r'<(\w+) SensorID=', ln)
        if m:
            kind = SENSOR_TAGS.get(m[1])
            if kind in counts:
                counts[kind] += 1
                kind = f'{kind}{counts[kind] - 1}'
        m = re.search(r'<CalibrationDate>([^<]*)</CalibrationDate>', ln)
        if m and kind:
            cal[kind] = _cal_date(m[1], path, kind)
            kind = None
    try:
        i = next(i for i, ln in enumerate(lines) if ln.strip().startswith('Bottle') and 'Date' in ln)
    except StopIteration:
        raise BtlError(f'{path.name}: no bottle table header') from None
    names = lines[i].split()[2:]
    missing = [v for v in REQUIRED if v not in names]
    if missing:
        raise BtlError(f'{path.name}: required variables missing: {", ".join(missing)}')
    bottles = {}
    body = lines[i + 2:]
    for j, ln in enumerate(body):
        if ln.rstrip().endswith('(avg)'):
            p = ln.split()
            vals: dict[str, str | datetime] = dict(zip(names, p[4:-1]))
            stamp = ' '.join(p[1:4]) + ' ' + body[j + 1].split()[0]
            vals['time'] = datetime.strptime(stamp, '%b %d %Y %H:%M:%S')
            bottles[int(p[0])] = vals
    start = None
    if 'Latitude' in nmea and 'Longitude' in nmea:
        start = (nmea_degrees(nmea['Latitude']), nmea_degrees(nmea['Longitude']))
    nmea_time = None
    if 'UTC (Time)' in nmea:
        nmea_time = datetime.strptime(' '.join(nmea['UTC (Time)'].split()), '%b %d %Y %H:%M:%S')
    return BtlFile(path, names, bottles, cal, start, nmea_time)
