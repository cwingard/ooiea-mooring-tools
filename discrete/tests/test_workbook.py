"""Transcription workbook layout, migrate and Niskin grouping rules."""
from asset_discrete.workbook import LISTS, SCHEMA, make_workbook, migrate, prune_niskins, read_workbook


def test_template_sheets_and_headers(tmp_path):
    path = tmp_path / 't.xlsx'
    make_workbook().save(path)
    sheets = read_workbook(path)
    assert set(sheets) == set(SCHEMA)
    assert all(rows == [] for rows in sheets.values())


def test_dropdowns_are_strict_except_notes_cast_and_niskin():
    wb = make_workbook()
    for name in SCHEMA:
        for dv in wb[name].data_validations.dataValidation:
            if dv.type == 'list':
                soft = name == 'Notes' and str(dv.sqref)[0] in 'BC'
                assert bool(dv.showErrorMessage) is not soft, (name, dv.sqref)
                assert dv.formula1.startswith('=OFFSET(Lists!')


def test_sites_come_from_reference():
    assert LISTS['Sites'][:2] == ['CE01', 'CE02']


def test_migrate_is_lossless_on_current_layout(workbook, tmp_path):
    out = tmp_path / 'm.xlsx'
    migrate(workbook).save(out)
    assert read_workbook(out) == read_workbook(workbook)


def test_prune_keeps_sampled_and_flagged():
    rows = [dict(cruise='X', cast=1, niskin=1, trip_depth_m=10, temp_c=8.0, salinity_psu=33.0, niskin_flag='Leaking'),
            dict(cruise='X', cast=1, niskin=2, oxygen_samples='1, 2'),
            dict(cruise='X', cast=1, niskin=3, notes='spare bottle')]
    kept = prune_niskins(rows)
    assert [r['niskin'] for r in kept] == [1, 2]
    assert kept[1]['trip_depth_m'] == 10            # filled from the first bottle of the group
    assert 'Niskin 3: spare bottle' in kept[1]['notes']
