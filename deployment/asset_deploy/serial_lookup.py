"""
Shared sensor-uid/serial-number lookup logic for surface moorings.

Every append_deploy_CEnnXXXX.m script builds a {instrument key: serial}
dictionary from the config.xlsx sheet, and a matching key for each
reference designator, then joins them. The steps are the same across
platforms; only the data (which sections exist, whether METBK/HYDGN/PCO2A
special cases apply, which reference designators/platcons are involved) is
platform-specific. This module holds the shared steps; platform modules in
asset_deploy/platforms/ supply the data and call these functions in the
same order the original MATLAB scripts did.

Each function is a direct port of one numbered step from
append_deploy_ce02shsm.m's sensor.uid section (~lines 425-532); see that
file's comments for the original rationale, especially around the METBK
7-character join-key collapse and the HYDGN DCL:Port # disambiguation.
"""
from __future__ import annotations

from asset_deploy.config_xlsx import NOTE_COL, ConfigTable

_NOT_DEPLOYED_MARKERS = ('none', 'n/a', 'not deployed')

# position 10-11 (platform code) + 19-23 (5-char instrument class),
# 1-indexed in the MATLAB source -- the slice used throughout to build a
# join key from a reference designator.
_IKEY_SLICE = (9, 11, 18, 23)


def is_not_deployed(value: str) -> bool:
    return value.strip().lower() in _NOT_DEPLOYED_MARKERS


def fix_serial(value: str, strip_lgr: bool = False) -> str:
    """Normalize a raw config-sheet S/N entry to a 5-character suffix.

    Hyphens map to a literal '0' (so '16-50006' -> last 5 chars '50006');
    the value is then zero-padded and the last 5 characters are taken, so
    an instrument that was not deployed (blanked to '') ends up as
    '00000'. `strip_lgr` additionally removes 'LGR-'/'LGR' first, needed
    only on platforms with a METBK logger S/N entry.
    """
    if strip_lgr:
        value = value.replace('LGR-', '').replace('LGR', '')
    value = value.replace('-', '0')
    value = '00000' + value
    return value[-5:]


def apply_pco2a_fix(values: list[str]) -> list[str]:
    """Strip the '-50A' pump-model suffix from the PCO2A S/N entry.

    Must run before fix_serial(). Only call this for platforms whose
    refdes_sensor table includes a PCO2A instrument.
    """
    values = list(values)
    pco2a_idx = [i for i, v in enumerate(values) if '-50A' in v]
    if len(pco2a_idx) != 1:
        raise ValueError(
            f'Expected exactly one PCO2A S/N entry, found {len(pco2a_idx)}')
    i = pco2a_idx[0]
    values[i] = values[i].replace('-', '').replace('50A', '')
    return values


def disambiguate_port_keys(
    keys: list[str], values: list[str], ports: tuple[str, ...],
) -> list[str]:
    """Append a DCL:Port # tag (e.g. '11:02') to the key on the row below
    each matching port-assignment row, to disambiguate two sensors that
    would otherwise share the same instrument-class key (the two HYDGN
    sensors on Endurance surface moorings). `values` must already be
    through fix_serial() (a bare port tag like '11:02' survives that
    pipeline unchanged, since it's already exactly 5 characters).
    """
    keys = list(keys)
    for i, v in enumerate(values):
        for port in ports:
            if port in v:
                keys[i + 1] += port
    return keys


def find_section(keys: list[str], label: str) -> int:
    """First row whose key contains `label` (case-insensitive), e.g.
    'nsif' matches both the old 'NSIF' and the current 'Instruments NSIF'
    section headers.
    """
    target = label.lower()
    for i, key in enumerate(keys):
        if target in key.lower():
            return i
    raise ValueError(f'Could not find a {label!r} section row in config')


def assign_section_prefixes(
    keys: list[str], sections: list[tuple[str, str]],
) -> tuple[list[str], int]:
    """Prefix each instrument key with its section's code (e.g. 'SB' for
    everything between the 'Instruments' and 'NSIF' section headers).

    `sections` is an ordered list of (section_label, prefix) pairs, e.g.
    [('Instruments', 'SB'), ('NSIF', 'RI')] or
    [('Instruments', 'SB'), ('NSIF', 'RI'), ('MFN', 'MF')].

    Returns the mutated keys and the row index of the first instrument
    row (immediately after the first section header), which is where the
    lookup dictionary should start.
    """
    keys = list(keys)
    boundaries = [find_section(keys, label) for label, _ in sections]
    boundaries.append(len(keys))

    for (_, prefix), start, end in zip(
        sections, boundaries, boundaries[1:],
    ):
        for i in range(start + 1, end):
            keys[i] = prefix + keys[i]

    return keys, boundaries[0] + 1


def strip_location_rows(
    keys: list[str], values: list[str],
) -> tuple[list[str], list[str]]:
    pairs = [(k, v) for k, v in zip(keys, values) if 'location' not in k.lower()]
    return [k for k, _ in pairs], [v for _, v in pairs]


def collapse_metbk_keys(keys: list[str]) -> list[str]:
    """Collapse e.g. 'SBMETBK-BPR' to the 7-char join key 'SBMETBP', to
    match the equivalent key built from the reference designator by
    refdes_ikeys(). Only needed on platforms with METBK instruments.
    """
    return [k[0:5] + k[8:10] if 'METBK' in k else k for k in keys]


class ConfigKeyError(KeyError, ValueError):
    """No config row produced a lookup key the platform table needs.

    Subclasses KeyError so platform modules that add their own hint (the
    ISSM WAVSS row) still catch it, and ValueError so the CLI reports it as a
    clean error instead of a traceback.
    """

    def __str__(self) -> str:
        return str(self.args[0])


class SerialDict(dict):
    """{lookup key: serial} that refuses to answer for an ambiguous key.

    A key is ambiguous when two config rows produce it with different
    serials, e.g. a PHSEN-D and a PHSEN-G side by side in the NSIF section
    (both keyed 'RIPHSEN'). A plain dict would silently keep the last one.
    Ambiguous keys that are never looked up (duplicate IMEI or release rows,
    blank rows) are harmless and do not raise.
    """

    def __init__(self, keys: list[str], values: list[str]) -> None:
        super().__init__()
        self._ambiguous: dict[str, set[str]] = {}
        for key, value in zip(keys, values):
            if key in self and dict.__getitem__(self, key) != value:
                self._ambiguous.setdefault(key, {dict.__getitem__(self, key)}).add(value)
            self[key] = value

    def __getitem__(self, key: str) -> str:
        if key in self._ambiguous:
            raise ValueError(
                f'Config sheet has more than one row for lookup key {key!r} with different serials '
                f'{sorted(self._ambiguous[key])}. Relabel the row CI does not track (e.g. '
                f"'PHSEN S/N' -> 'PHSEN (not CI) S/N') and re-run.")
        if key not in self:
            raise ConfigKeyError(
                f'No config row for lookup key {key!r}. Check the S/N row label and, for HYDGN, the '
                'DCL:Port # row above it.')
        return super().__getitem__(key)


def build_serial_dict(keys: list[str], values: list[str]) -> dict[str, str]:
    return SerialDict(keys, values)


def refdes_ikeys(
    refdes_list: list[str], metbk_remap: dict[str, str] | None = None,
) -> list[str]:
    """Build the instrument-key -> lookup key used to join a reference
    designator to its serial number, mirroring the config-sheet side's
    section-prefix + (optional) METBK collapse.
    """
    remap = metbk_remap or {}
    remapped = []
    for rd in refdes_list:
        for old, new in remap.items():
            rd = rd.replace(old, new)
        remapped.append(rd)
    p_start, p_end, c_start, c_end = _IKEY_SLICE
    return [rd[p_start:p_end] + rd[c_start:c_end] for rd in remapped]


def disambiguate_hydgn_ikeys(
    ikeys: list[str], ports: tuple[str, str] = ('11:02', '12:03'),
) -> list[str]:
    """Companion to disambiguate_port_keys() for the refdes side: the two
    HYDGN reference designators share the join key 'SBHYDGN'; by table
    convention the first one listed uses ports[0] and the second ports[1].
    """
    ikeys = list(ikeys)
    idx = [i for i, k in enumerate(ikeys) if k.upper() == 'SBHYDGN']
    if len(idx) == 2:
        ikeys[idx[0]] += ports[0]
        ikeys[idx[1]] += ports[1]
    return ikeys


def platcon_serials(
    config: ConfigTable, values: list[str], platcon_codes: list[str],
) -> list[str]:
    """Platcon bottle S/N lookup, keyed by the config sheet's notes column
    (platcon bottle assignment, e.g. 'CPM1, DCL11, DCL12').
    """
    notes = config.column(NOTE_COL)
    serials = []
    for code in platcon_codes:
        matches = [i for i, v in enumerate(notes) if code in v]
        if len(matches) != 1:
            raise ValueError(
                f'Expected exactly one platcon row containing {code!r}, '
                f'found {len(matches)}')
        serials.append(values[matches[0]])
    return serials


# Shared across every platform with METBK[A000:A007] reference designators
# (CE02SHSM, CE04OSSM, CE07SHSM, CE09OSSM): maps the generic METBKAxxx
# refdes suffix to the specific instrument's suffix, so refdes_ikeys() can
# extract a join key that matches collapse_metbk_keys()'s output.
METBK_REFDES_REMAP: dict[str, str] = {
    'METBKA000': 'METLGR000',
    'METBKA001': 'METCTD001',
    'METBKA002': 'METBPR002',
    'METBKA003': 'METHRH003',
    'METBKA004': 'METLWR004',
    'METBKA005': 'METPRC005',
    'METBKA006': 'METSWR006',
    'METBKA007': 'METWND007',
}
