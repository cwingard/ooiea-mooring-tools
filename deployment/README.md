# deployment -- asset-management deployment records

Generates and maintains the OOI CI deployment records for Endurance Array moorings in the `asset-management` repo:

- `deployment/<PLATFORM>_Deploy.csv` -- one row per reference designator per deployment
- `bulk/platform_bulk_load-AssetRecord.csv` -- the mooring uid (e.g. `CGMCE-07SHSM-00021`)
- `bulk/eng_bulk_load-AssetRecord.csv` -- new surface-mooring platform controllers (CPM/DCL), when missing

Ported from the `append_deploy_*.m` MATLAB scripts (kept under `matlab/` for reference). This is the Crawl-phase
tool: it reads the per-deployment configuration workbook (xlsx). It will be replaced by a consumer of the
RDB-generated deployment YAML (see the repo-level `README.md`).

## Setup

Run from this `deployment/` folder, in the `ea_tools` conda environment (`environment.yml` at the repo root; see the
repo-level `README.md`, section 8).

```bash
cd ~/code/ooiea-mooring-tools/deployment
python -m asset_deploy.cli --help
```

All commands take `--asset-management <path to your asset-management clone>`. Every command also accepts
`--mode test`, which writes `_preview_<name>` files next to the real ones instead of changing them. Diff the preview,
delete it, then re-run without `--mode test`.

## Typical turn

| When | Command | What it does |
|---|---|---|
| Pre-cruise | `deploy --config <sheet>` | Stages the new deployment with placeholder date/time/position |
| After deployment | `deploy --config <sheet> --replace` | Updates the staged rows to the as-deployed configuration |
| Recovery | `recover <MOORING_SN> --cruise <CUID> --time <UTC>` | Writes recovery time and cruise into its rows |

Before any of these, the cruise must be in `asset-management/cruise/CruiseInformation.csv` (see Validation).

### deploy -- stage a new deployment

```bash
CONFIGS=~/OneDrive/"Documents - Endurance Array"/Moorings/deployments/Fall_2026/Configurations
python -m asset_deploy.cli deploy \
    --config "$CONFIGS/CE07SHSM-00021.xlsx" \
    --asset-management ~/code/asset-management
```

- The mooring is read from the sheet (`Reference Designator:` and `Mooring S/N:` rows); there is no platform argument.
- Appends the deployment's rows to `<PLATFORM>_Deploy.csv`, adds the mooring uid to
  `platform_bulk_load-AssetRecord.csv`, and (surface moorings only) appends any missing CPM/DCL platcon records to
  `eng_bulk_load-AssetRecord.csv`.
- Refuses to run if the deployment number already exists in the CSV -- use `--replace` for that.
- `--no-append-platcon` skips the platcon append.

### deploy --replace -- update to the as-deployed configuration

Re-run against the updated sheet after deployment: final launch date/time and anchor position, sensors swapped on
deck, sensors that failed and were not deployed.

```bash
python -m asset_deploy.cli deploy --config <sheet> --replace --asset-management ~/code/asset-management
```

- Regenerates the deployment from the sheet and overwrites its existing rows in place, matched by reference
  designator; row order and `versionNumber` are kept, so the git diff shows only real changes.
- Prints the changes before writing, e.g.
  `lat: '45.50000' -> '44.63612'  (all rows)` and
  `sensor.uid: 'CGINS-PHSENG-02102' -> 'CGINS-PHSENG-02087'  (RID26-06-PHSENG000)`.
- Stops if the deployment does not exist yet, if it has already been recovered (edit recovered deployments by hand),
  or if the file's reference designators no longer match the platform table.
- Overwrites every generated column; hand edits to those rows are reverted (they show in the change list).

### recover -- record a recovery

```bash
python -m asset_deploy.cli recover CE07SHSM-00021 --cruise SR2703 --time 2027-04-11T15:30:00 \
    --asset-management ~/code/asset-management
```

- Sets `stopDateTime` and `CUID_Recover` on every row of that deployment. Not-deployed rows (`#` on `CUID_Deploy`)
  get `#` on `CUID_Recover` too.
- Times are UTC, ISO 8601 (`YYYY-MM-DDTHH:MM[:SS]`).
- Stops if the deployment does not exist, if the time is not after the deployment start, or if the deployment
  already has recovery info (`--force` to overwrite).
- Works for any `<PLATFORM>_Deploy.csv`, including platforms without a deploy builder (e.g. CSPP).
- For a mooring that was lost, use `--cruise UNRECOVERED`.

## Validation (nothing is written if any check fails)

- **Cruise:** the cruise ID must exist in `cruise/CruiseInformation.csv`, and the launch (deploy) or recovery time
  must fall inside that cruise's start/stop window. Add or correct the cruise record first.
- **Sensor uids:** each instrument's series letter is looked up in `bulk/sensor_bulk_load-AssetRecord.csv` from its
  class and serial number (e.g. `PHSEN` + `02102` -> `CGINS-PHSENG-02102`). No match or more than one match stops
  the run -- add the missing asset record by hand (see Manual steps).
- **Platform controllers:** CGCON uids missing from `bulk/eng_bulk_load-AssetRecord.csv` are auto-appended for
  surface moorings; for profiler moorings (CE09OSPM) the run stops until they are added by hand.
- **Sheet:** see below.

## Configuration workbook

The sheet is read exactly as maintained -- column A label, column B value, column C notes. No preparation (copying
columns, forcing text format) is needed or supported.

- **Values must be text.** A cell Excel converted to a date or time (e.g. `12:08` for a DCL:Port, `2026-09-30` for a
  date) stops the run with the row label; re-enter it as text.
- **Mooring-level rows are found by label:** `Reference Designator:`, `Mooring S/N:`, `Anchor Launch Date:`,
  `Anchor Launch Time:`, `Latitude:`, `Longitude:` (negative), `Water Depth:`, `Cruise #:`. Each must appear once.
- **Sections:** instrument rows are grouped by the section header rows containing `Instruments`, `NSIF` and (where the
  mooring has one) `MFN`.
- **Platform controllers:** the notes column of each `... Assm S/N` row lists the bottles it covers
  (e.g. `CPM1, DCL11, DCL12`).
- **HYDGN:** the two buoy HYDGN sensors are told apart by the `HYDGN DCL:Port #` row above each S/N row (`11:02`,
  `12:03`).
- **Not deployed:** an instrument with a blank S/N, or `None`, `N/A` or `Not Deployed`, is written as a not-deployed
  row (`#` on `CUID_Deploy`, `Not Deployed` in notes, blank `sensor.uid`).
- **Instruments CI does not track** (one-offs, VEMCO, VICS, pumps, lamps, ...): list them normally. Only instruments
  in the platform's reference designator table are looked up; everything else is ignored.
- **Two rows for the same class in one section** (e.g. a second PHSEN on the NSIF): if both have different serials
  the run stops. Relabel the row CI does not track (e.g. `PHSEN S/N` -> `PHSEN (not CI) S/N`), or hand-edit the
  deploy CSV if both are CI-tracked.
- **CE01ISSM / CE06ISSM:** the MFN ADCPT and WAVSS share one unit; the MFN section needs a copy of the `ADCPT S/N`
  row relabeled `WAVSS S/N`.

## Manual steps that remain

- New instruments need a `bulk/sensor_bulk_load-AssetRecord.csv` record before `deploy` will resolve them (description,
  manufacturer, model and serial format cannot be derived). Keep the file sorted.
- New profiler platform controllers (e.g. a CE09OSPM STC) need a `bulk/eng_bulk_load-AssetRecord.csv` record.
- New cruises need a `cruise/CruiseInformation.csv` record (chronological, array name first in notes).
- `append_mooring_uid.py <MOORING_SN> ...` backfills mooring uids missing from
  `platform_bulk_load-AssetRecord.csv`; `deploy` normally does this itself.

## Supported platforms

`deploy` has builders for CE01ISSM, CE02SHSM, CE04OSSM, CE06ISSM, CE07SHSM, CE09OSSM (surface moorings) and CE09OSPM
(wire-following profiler). Each lives in `asset_deploy/platforms/<platform>.py`, which holds that mooring's
reference designator table, platform controllers and deployment depths. A platform's module is selected by name
from the sheet's `Reference Designator:` row, so adding a platform means adding a module -- no registry to edit.
CSPP (SP) deployments are not supported by `deploy`; `recover` works for them.

## Layout

```text
deployment/
    asset_deploy/
        cli.py            # deploy / recover subcommands
        config_xlsx.py    # reads the workbook (labels, values, notes); rejects date/time cells
        metadata.py       # mooring-level fields looked up by row label
        cruise.py         # CruiseInformation.csv lookups and time-window check
        serial_lookup.py  # config-sheet serial numbers -> sensor.uid serial suffixes
        bulk_records.py   # bulk asset-record lookups and appends
        deploy_csv.py     # read / append / replace / recover rows in *_Deploy.csv
        platforms/        # one module per mooring
    append_deploy.py      # wrapper: `python append_deploy.py ...` = `python -m asset_deploy.cli ...`
    append_mooring_uid.py
    matlab/               # original MATLAB scripts, reference only
    tests/
```

## Tests

```bash
ASSET_MANAGEMENT_DIR=~/code/asset-management python -m pytest tests
```

From the repo root, `pytest` runs these together with the other packages' tests. Tests that need the real
asset-management records (historical parity, end-to-end deploy/replace) skip if `ASSET_MANAGEMENT_DIR` is not
found; they work on temporary copies and never modify the repo.
`tests/fixtures/CE02SHSM-00020.xlsx` must stay the original sheet used for deployment 20 -- it backs the parity check
against the committed `CE02SHSM_Deploy.csv`.
