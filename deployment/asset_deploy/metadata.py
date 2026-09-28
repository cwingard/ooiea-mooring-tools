"""
Mooring-level deployment metadata, looked up by row label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from asset_deploy.config_xlsx import VALUE_COL, ConfigError, ConfigTable

LABEL_PLATFORM = 'Reference Designator:'
LABEL_MOORING_SN = 'Mooring S/N:'
LABEL_LAUNCH_DATE = 'Anchor Launch Date:'
LABEL_LAUNCH_TIME = 'Anchor Launch Time:'
LABEL_LAT = 'Latitude:'
LABEL_LON = 'Longitude:'
LABEL_WATER_DEPTH = 'Water Depth:'
LABEL_CRUISE_ID = 'Cruise #:'


@dataclass(frozen=True)
class DeploymentMetadata:
    platform_code: str  # e.g. 'CE07SHSM'; selects the platform module
    mooring_sn: str
    dep_num: int
    mooring_uid: str
    lat: str
    lon: str
    start_date_time: str
    water_depth: str
    cruise_id: str


def _cell(config: ConfigTable, label: str, col: int = VALUE_COL) -> str:
    return config.get(config.find_row(label), col)


def _required(config: ConfigTable, label: str) -> str:
    value = _cell(config, label)
    if not value:
        raise ConfigError(f'{label!r} is blank')
    return value


def _coord(config: ConfigTable, label: str) -> str:
    raw = _required(config, label)
    try:
        return f'{float(raw):.5f}'
    except ValueError:
        raise ConfigError(f'{label!r} is not a decimal degree value: {raw!r}') from None


def read_metadata(config: ConfigTable) -> DeploymentMetadata:
    """Read the mooring-level fields shared by every platform module.

    Parameters
    ----------
    config : ConfigTable
        Config sheet as read by config_xlsx.read_config.

    Returns
    -------
    DeploymentMetadata
    """
    platform_code = _required(config, LABEL_PLATFORM).upper()
    mooring_sn = _required(config, LABEL_MOORING_SN)
    if not mooring_sn.upper().startswith(platform_code + '-'):
        raise ConfigError(
            f'{LABEL_PLATFORM!r} ({platform_code}) and {LABEL_MOORING_SN!r} ({mooring_sn}) do not agree')
    tokens = re.split(r'[-_]', mooring_sn)
    try:
        dep_num = int(tokens[1])
    except (IndexError, ValueError):
        raise ConfigError(f'Cannot parse a deployment number from {mooring_sn!r}') from None
    upper = mooring_sn.upper()
    mooring_uid = 'CGM' + upper[:2] + '-' + upper[2:]

    lat = _coord(config, LABEL_LAT)
    lon = _coord(config, LABEL_LON)
    if float(lon) > 0:
        raise ConfigError('Positive decimal degree longitude submitted for Endurance!')

    date = _required(config, LABEL_LAUNCH_DATE)
    if '/' in date:  # mm/dd/yyyy -> yyyy-mm-dd
        date = f'{date[6:10]}-{date[0:2]}-{date[3:5]}'
    time = _required(config, LABEL_LAUNCH_TIME)
    if len(time) == 5:
        time += ':00'

    return DeploymentMetadata(
        platform_code=platform_code,
        mooring_sn=mooring_sn,
        dep_num=dep_num,
        mooring_uid=mooring_uid,
        lat=lat,
        lon=lon,
        start_date_time=f'{date}T{time}',
        water_depth=re.sub(r'[A-Za-z\s]', '', _required(config, LABEL_WATER_DEPTH)),
        cruise_id=_required(config, LABEL_CRUISE_ID),
    )
