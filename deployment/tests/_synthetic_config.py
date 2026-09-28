"""Build a synthetic ConfigTable (label, value, notes) for a
shelf/offshore/inshore surface-mooring platform module, for round-trip
testing the shared serial_lookup.py plumbing (section splitting, METBK
collapse, HYDGN disambiguation, PCO2A fix) without needing a real
config.xlsx fixture.

Not a general-purpose tool -- just enough to exercise every branch of
_prepare_keys_values / _instrument_serial_dict / _refdes_ikeys for a
given platform module and assert every reference designator's serial
number round-trips correctly.
"""
from __future__ import annotations

from asset_deploy.config_xlsx import ConfigTable

_PCO2A_RAW_VALUE = '12-345-50A'
_PCO2A_EXPECTED_SERIAL = '12345'


def build_synthetic_config(
    platform_module,
    mooring_sn: str,
    water_depth: str = '100',
    lat: str = '44.00000',
    lon: str = '-124.00000',
    cruise_id: str = 'TEST01',
    metbk_remap: dict[str, str] | None = None,
) -> tuple[ConfigTable, dict[str, str]]:
    """Returns (config, expected_sensor_uid_by_refdes)."""
    refdes_sensor = platform_module.REFDES_SENSOR
    platcons = platform_module.PLATCON
    n_platcon = platform_module.N_PLATCON
    sections = platform_module.SECTIONS

    rows: list[list[str]] = [
        ['Title', '', ''],
        ['Reference Designator:', mooring_sn[:8], ''],
        ['Type:', '', ''],
        ['Mooring S/N:', mooring_sn, ''],
        ['Anchor Launch Date:', '2026-01-01', ''],
        ['Anchor Launch Time:', '12:00', ''],
        ['Latitude:', lat, ''],
        ['Longitude:', lon, ''],
        ['Water Depth:', water_depth, ''],
        ['Cruise #:', cruise_id, ''],
        ['', '', ''],
    ]

    counter = [10000]

    def next_serial() -> str:
        counter[0] += 1
        return str(counter[0])[-5:]

    expected: dict[str, str] = {}

    # -- platcons: one physical unit (and serial) per bottle code --
    rows.append(['Platform Control', '', ''])
    platcon_serial: dict[str, str] = {}
    for code in platcons:
        platcon_serial.setdefault(code, next_serial())
    for code in dict.fromkeys(platcons):
        s = platcon_serial[code]
        rows.append([f'{code} Assm S/N', s, code])
    for i in range(n_platcon):
        refdes, template = refdes_sensor[i]
        expected[refdes] = template.replace(
            'xxxxx', platcon_serial[platcons[i]])

    # -- instruments --
    remap = metbk_remap or {}

    def instrument_class(refdes: str) -> str:
        rd = refdes
        for old, new in remap.items():
            rd = rd.replace(old, new)
        return rd[18:23]

    instrument_rows = refdes_sensor[n_platcon:]

    # resolve a stable key per row instance: HYDGN gets a distinct key
    # per occurrence (disambiguated by DCL:Port #, like the real algo);
    # any other class repeated within a section shares one row/serial,
    # also like the real algorithm (a dict key collision, not a bug).
    resolved_keys: list[tuple[str, str, int | None]] = []
    hydgn_occurrence: dict[str, int] = {}
    for refdes, _ in instrument_rows:
        prefix = refdes[9:11].upper()
        cls = instrument_class(refdes)
        if cls == 'HYDGN':
            n = hydgn_occurrence.get(prefix, 0)
            hydgn_occurrence[prefix] = n + 1
            resolved_keys.append((prefix, cls, n))
        else:
            resolved_keys.append((prefix, cls, None))

    key_serial: dict[tuple[str, str, int | None], str] = {}
    current_prefix = None
    hydgn_ports = ('11:02', '12:03')
    for (refdes, _), key in zip(instrument_rows, resolved_keys):
        prefix, cls, occurrence = key
        if prefix != current_prefix:
            label = next(lbl for lbl, pfx in sections if pfx == prefix)
            rows.append([label.capitalize(), '', ''])
            current_prefix = prefix
        if key in key_serial:
            continue
        if cls == 'HYDGN':
            port = hydgn_ports[occurrence]
            rows.append(['HYDGN DCL:Port #', port, ''])
            s = next_serial()
            rows.append(['HYDGN S/N', s, ''])
        elif 'PCO2A' in refdes and 'PCO2W' not in refdes:
            rows.append([f'{cls} S/N', _PCO2A_RAW_VALUE, ''])
            s = _PCO2A_EXPECTED_SERIAL
        else:
            s = next_serial()
            rows.append([f'{cls} S/N', s, ''])
        key_serial[key] = s

    for (refdes, template), key in zip(instrument_rows, resolved_keys):
        expected[refdes] = template.replace('xxxxx', key_serial[key])

    return ConfigTable(rows), expected
