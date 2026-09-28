# ooiea-mooring-tools

Tooling used by Endurance Array (EA) technicians and data managers across the mooring lifecycle: from
pre-deployment configuration through getting recovered/streaming data into the OOI CI ingestion systems.

This document is the architecture record for the repo -- why it exists, what is and is not in scope, how the
pieces relate, and the open questions that are still unresolved. It is meant to let a future maintainer (or an
AI assistant) reconstruct the reasoning, not just the current file layout.

## 1. Scope

**In scope:** anything involved in taking a mooring from pre-cruise planning through deployment, recovery, and
getting the resulting data into CI. This includes calibration file generation, deployment configuration and CSV
generation, ingestion CSV generation, the recovered-data directory tree builder, onboard mooring/DCL
configuration, at-sea position determination, and SBD/Gmail-based telemetry harvest tooling.

**Out of scope:** anything downstream of data arriving in CI -- converting raw data to NetCDF, serving it via
ERDDAP, or displaying it in OMS++. That is a separate lifecycle phase already served by existing, shared
codebases (`cgsn-parsers`, `cgsn-processing`, OMS++). This repo does not absorb them; where they need
deployment-configuration context, they become *consumers* of this repo's generated YAML, the same as any other
consumer.

## 2. Relationship to existing repos and systems

| Repo / system | Status | Notes |
|---|---|---|
| `asset_management` | External, unchanged | Downstream data/output repo. Calibration files and deployment CSVs land here. Existing MATLAB and RCA Python tooling under `tools/` stays as-is; this repo's calibration/deployment generators are net-new, not a migration. |
| `ingestion_csvs` | External, unchanged | Holds the CSV tables that instruct the M2M system how to ingest data. Read/write target for this repo's ingestion CSV generator. |
| `cgsn_processing` / `cgsn_parsers` | External, unchanged | Shared with CGSN; feed the internal OMS. `cgsn_processing` currently contains the in-progress RDB-to-YAML generator (`generate_yaml.py`); this may move into `ooiea-mooring-tools/core` once the design stabilizes, but the packages themselves are not absorbed. |
| OMS++ (Django/Postgres) | External, unchanged | Standalone display application. Becomes a YAML/RDB consumer for configuration context; not absorbed. |
| `platform_cfgs` | Absorbed (split into two functions) | See section 5. |
| Roundabout (RDB) | External, authoritative | The single source of truth. See section 3. |

**The rule applied to decide absorb vs. external:** absorb a subsystem into this repo if it is EA-only with no
other consumer; leave it external and treat it as a read/write target if it is shared or feeds something outside
this project's scope.

## 3. Data architecture: RDB -> YAML -> consumers

Roundabout (RDB) is the single point of entry for base mooring/deployment configuration -- the authoritative
source for deployment metadata, instrument inventory, and (per build) DCL/port assignment.

The per-deployment YAML is a generated, stable interface derived from RDB -- not hand-maintained, not a second
source of truth. Every other artifact in this repo is a consumer (or, in one case, a co-producer) of that YAML:

- Deployment CSV generation
- Ingestion CSV generation
- buildtree (recovered-data directory structure)
- Onboard DCL/CPM configuration
- SBD/Gmail filter and harvest-script generation

A field only needs to exist outside RDB if something downstream of RDB actually consumes it. Fields RDB tracks
purely for its own inventory purposes (battery serials, telemetry-hardware serial numbers/redundancy) stay in
RDB only and are not carried into the YAML.

### 3.1 Field-to-artifact matrix

| Atom | Source | YAML | Deployment CSV | Ingestion CSV | buildtree | DCL/CPM cfg | Gmail/SBD filters |
|---|---|---|---|---|---|---|---|
| Mooring / site ID | RDB | Y | Y | Y | Y | Y | Y |
| Deployment number / deploy name | RDB | Y | Y | Y | Y | Y | -- |
| Array / category / subcategory | RDB | Y | Y | -- | -- | -- | -- |
| Disposition, start/stop dates | RDB (automated) | Y | Y | -- | -- | -- | -- |
| Deploy/recover cruise IDs | RDB (automated) | Y | Y | -- | -- | -- | -- |
| Latitude / longitude | anchor survey -> RDB | Y | Y | -- | -- | -- | -- |
| Watch circle, site/water depth | RDB | Y | -- | -- | -- | -- | -- |
| Platform/DCL/CPM topology | static, template-encoded | Y | derived | -- | -- | Y (derived from YAML) | -- |
| Instrument class + instance | RDB | Y | Y | Y | -- | Y | -- |
| DCL / port assignment | RDB (default + per-build override) | Y | derived | Y | implied | Y | -- |
| Instrument serial number | RDB | Y | Y | Y | -- | Y | -- |
| UUID (RDB asset ID) | RDB | Y | -- | -- | -- | -- | -- |
| Telemetry IMEI (beacons, SBD modems) | RDB | Y | -- | -- | -- | -- | Y (key field) |
| Instrument redundancy (same class, CI-ingested) | RDB | implicit -- each unit is a fully distinct entry | -- | -- | -- | -- | -- |
| Telemetry serial numbers, redundancy | RDB only | -- | -- | -- | -- | -- | -- |
| Battery serials | RDB only | -- | -- | -- | -- | -- | -- |

"Derived" means the value is computed from other atoms via a documented naming convention (paths, dataset
names), not separately entered or stored.

## 4. Phasing: Crawl, Walk, Run

- **Crawl:** keep using the existing manual configuration spreadsheets while working out the optimal YAML
  structure. No consumer code depends on RDB yet.
- **Walk:** begin testing/development with RDB and `cgsn_processing` to automate YAML generation. Hand-editing
  still expected, but significantly reduced.
- **Run:** full CLI tooling pulling from RDB to build the YAML, and using the YAML to generate deployment CSVs,
  ingestion CSVs, buildtree structure, onboard configuration, and SBD/Gmail tooling.

Consumer code should not be built against the YAML schema until it has stabilized past Crawl, to avoid churn
from repeatedly breaking early consumers.

## 5. Repo structure

Organized by function (what a tool does), not by destination (which external repo/system consumes its output)
or by where it runs. Rationale: destination-based naming collides with the external repos of the same name and
obscures what a tool actually does; a function-based tree is what makes a folder's purpose guessable without
tribal knowledge.

```text
ooiea-mooring-tools/
    core/                # shared: YAML schema/models, RDB client, validation
    calibration/         # cal file generation (MATLAB -> Python conversion, vendor/QCT-driven)
    deployment/          # deployment record / CSV generation -- see deployment/README.md
    ingestion/           # ingestion CSV generation and consistency checking
    buildtree/           # recovered-data directory tree builder
    onboard_config/      # DCL/CPM/serial cfg generation (absorbed from platform_cfgs/configs
                         #    and platform_cfgs/tools/config_manager.py) -- relationship to the
                         #    YAML is still undecided, see section 6
    instrument_setup/    # bench/integration-time instrument configuration, instrument-class-scoped
                         #    (absorbed from platform_cfgs/instrument_setup); no YAML dependency
    sbd_messages/        # Gmail filter + harvest shell script generation, keyed on YAML IMEI values
    anchor_survey/       # at-sea lat/lon tool (MATLAB -> Python); optional dependency group, offline-capable
```

Naming test for any future addition: would a new team member's first guess at where a tool lives, based on what
the tool *does*, be correct? If not, the name or the grouping is wrong.

## 6. Open questions

- **`generate_yaml.py` inventory pull is not implemented.** Deployment-level metadata (dates, cruise IDs,
  lat/lon, disposition) is already pulled from RDB. Per-instrument inventory (serials, DCL/port assignment,
  UUIDs) is not -- this is the actual hard remaining piece of Walk-phase work.
- **Schema versioning / contract tests are not yet in place.** Planned as a natural follow-on once the YAML
  schema and consumer list are stable -- the mechanism for "what does changing X break" without requiring tribal
  knowledge or a bespoke AI layer.

## 7. Tool status

- **`calibration/`** -- working. Vendor/QCT source files -> asset_management calibration CSVs; 11 instrument
  classes ported from MATLAB. No YAML dependency.
- **`deployment/`** -- working (Crawl). Per-deployment config xlsx -> asset_management `*_Deploy.csv`, mooring uid,
  platcon and recovery records via `deploy`, `deploy --replace` (as-deployed update) and `recover`; validates the
  cruise, bulk asset records and the sheet before writing. Becomes a YAML consumer in Run. Usage:
  [deployment/README.md](deployment/README.md).
- **`buildtree/`** -- absorbed as-is (`buildtree.py`), not yet reworked.
- **`anchor_survey/`** -- absorbed as-is (MATLAB), not yet converted.
- **`core/`, `ingestion/`, `onboard_config/`, `instrument_setup/`, `sbd_messages/`** -- not started.
