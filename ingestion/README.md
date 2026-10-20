# ingestion -- ingestion CSVs for the ingestion-csvs repo

Package `asset_ingest`. Writes a deployment's telemetered (`D000NN`) and recovered (`R000NN`) ingestion CSVs into
the ingestion-csvs repo, and checks existing ones for internal consistency. Replaces copying the previous
deployment's files by hand.

Run from this folder in the `ea_tools` conda environment (`environment.yml` at the repo root; see the repo-level
`README.md`, section 8).

## What it reads

| Input | Used for |
| --- | --- |
| `templates/<SITE>_D_ingest.csv`, `templates/<SITE>_R_ingest.csv` | every stream row the site uses |
| deployment configuration workbook (`.xlsx`, read as-is) | site, deployment number, `DCL:Port #` wiring, loggers |
| `<asset-management>/deployment/<SITE>_Deploy.csv` | which reference designators were deployed |

Run the deploy tool (`asset_deploy`) first: the ingestion files follow what asset-management says, so the two stay
consistent.

## Templates

A template is an ingestion CSV (same six columns, same `#` commenting) with two tokens in `filename_mask`:

* `{deployment}` -- replaced by `D000NN` or `R000NN`
* `{dcl}` -- replaced by the instrument's DCL number from the config sheet's `<CLASS> DCL:Port #` row

Engineering rows (port `00`, e.g. `MFD35-00-DCLENG000`) keep their logger literally (`dcl36`). Instance
subdirectories (`ctdbp1`, `velpt2`, ...) are literal too; they are fixed per reference designator. Status and notes
are written as the template has them; R templates carry `Expected` for rows whose data are not yet recovered.

The templates are the one place stream knowledge lives. Change them, not the code, when the mooring changes:

* instrument swapped for a new class (e.g. PHSEN-D to PHSEN-G): replace its rows (new refdes, parser, mask)
* instrument added or retired: add or delete its rows
* parser changed or became available: edit the parser, status and notes, or uncomment the row

Git history of the templates is the record of those changes. Past deployments' files are never regenerated.

Sites with templates, and the files they were seeded from:

| Site | Seeded from |
| --- | --- |
| CE01ISSM | D00022/R00022 |
| CE02SHSM | D00020/R00020 |
| CE04OSSM | D00019/R00019 |
| CE06ISSM | D00021/R00021 |
| CE07SHSM | D00020/R00020 |
| CE09OSPM | D00022/R00022 |
| CE09OSSM | D00020/R00020 |

METBK-CT (`METBKA001`) has only a `recovered_inst` row in the surface-mooring templates: its telemetered and
recovered_host data are the METBK log already ingested for `METBKA000`, and the instrument download exists to fill
gaps in that log. It is therefore also printed by `generate` as having no template row in D.

Profiler templates (CE09OSPM) have no `{dcl}` token; the workbook is then only read for the site and deployment
number.

## Generate

```bash
python -m asset_ingest.cli generate \
    --config ~/OneDrive/"Documents - Endurance Array"/Moorings/deployments/Fall_2026/Configurations/CE07SHSM-00021.xlsx \
    --asset-management ~/code/asset-management \
    --ingestion-csvs ~/code/ingestion-csvs \
    [--mode test] [--replace] [--templates DIR]
```

Writes `<ingestion-csvs>/<SITE>/<SITE>_D000NN_ingest.csv` and `..._R000NN_ingest.csv`. `--mode test` writes
`*_ingest_preview.csv` next to them instead. Existing files are not overwritten without `--replace` (use it to
regenerate after an as-deployed change and a `deploy --replace`).

Rules:

* a reference designator commented out (not deployed) in `<SITE>_Deploy.csv` is written commented out with status
  `Not Deployed`
* the instrument's DCL comes from the config sheet, matched by section (`Instruments Buoy/NSIF/MFN` -> `SB/RI/MF`) and
  class; the port decides when a class repeats in a section (the two buoy HYDGNs)
* an instrument plugged into and recorded by a CTDBP (MFN/NSIF DOSTA, inshore buoy FLORT: same node and port in the
  reference designator, e.g. `MFD37-03-DOSTAD000` on `MFD37-03-CTDBPC000`) takes the CTDBP's DCL; its own
  `DCL:Port #` row is not needed, and if it disagrees it is printed and ignored

The run stops and writes nothing when:

* a template reference designator is not in `<SITE>_Deploy.csv` for that deployment
* a deployed instrument has no `DCL:Port #` value in the sheet
* an instrument recorded by a CTDBP is deployed but its CTDBP is not
* an instrument's DCL is not a logger listed in the sheet's Platform Control notes (catches typos such as `63:03`)
* a `DCL:Port #` cell was stored by Excel as a time

Printed for information:

* reference designators commented out as Not Deployed
* deployed reference designators with no template row -- the METBK sub-sensors (`METBKA002`-`007`) always appear
  here, since they have no stream of their own; anything else here is a new instrument missing from the templates
* sheet instruments with no reference designator (one-offs such as FDCHP, VICS, VEMCO), which are ignored

## After recovery

Edit the R file by hand: set rows to `Available` once the data are on the raw data archive, or comment them out
with `Not Expected` and a note (flooded, did not record). Then run `check`.

## Check

```bash
python -m asset_ingest.cli check CE07SHSM --ingestion-csvs ~/code/ingestion-csvs \
    [--asset-management ~/code/asset-management] [--deployment 21]
```

Read-only; prints one line per finding and exits 1 if there are any. Checks:

* header is `parser,filename_mask,reference_designator,data_source,status,notes`
* each mask points at this site and the file's own `D000NN`/`R000NN` directory
* data_source is `telemetered` in D files, `recovered_host`/`recovered_inst`/`recovered_wfp` in R files
* status is an ingestion-csvs README code; active rows are not `Not Deployed`/`Not Expected`
* all rows for a reference designator in one deployment (D and R) use the same DCL, and an instrument recorded by a
  CTDBP is on the CTDBP's DCL
* with `--asset-management`: active rows are deployed there, and every deployed reference designator has a row in
  that deployment -- only for reference designators that have a row somewhere in the site's files, so METBK
  sub-sensors and instruments that never had a stream (e.g. CE07SHSM's buoy CAMDSD) are not reported

Older deployments have findings; `check` reports them and changes nothing.

## Tests

```bash
python -m pytest tests
```

Synthetic inputs only (`tests/conftest.py`); no repo checkouts needed. From the repo root, `pytest` runs these
together with the other packages' tests.

## Files

| File | Role |
| --- | --- |
| `asset_ingest/cli.py` | `generate` and `check` commands |
| `asset_ingest/generate.py` | fills the templates for one deployment |
| `asset_ingest/check.py` | consistency checks on existing files |
| `asset_ingest/config_wiring.py` | reads site, deployment, `DCL:Port #` wiring and loggers from the workbook |
| `asset_ingest/deploy_state.py` | reads deployed/not-deployed per reference designator from asset-management |
| `asset_ingest/ingest_file.py` | reads/writes the ingestion CSV format |
| `templates/` | per-site D and R templates |
