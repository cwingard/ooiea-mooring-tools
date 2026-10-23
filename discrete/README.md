# discrete -- Discrete Summary for Endurance Array cruises (package `asset_discrete`)

Produces the OOI-wide Discrete Summary for an Endurance cruise reproducibly, from a hand-entered transcription
workbook, the cruise's Sea-Bird `.btl` files and (later) the lab result files, and validates any Discrete Summary
file (ours, historic, or another array's) against the OOI-wide format.

Out of scope for now: BCO-DMO submission (code not yet received), ROV/J2 dives (RCA only), and the DOSTA 2-point
Winkler process (discontinued). It lives in this repo under the README section 2 rule: EA owns producing its
summaries and nothing else consumes the tooling.

## 1. Status (2026-10-23)

| Piece | State |
|---|---|
| Transcription workbook (`new`, `migrate`) | working; layout settled on Endurance 25 (SR2614) and Endurance 18 |
| `.btl` parser (`btl.py`) | working; SR2614 casts 1-3 |
| `build` (CTD + workbook -> xlsx, README, build log) | working; SR2614 v1.00 (CTD only), v1.01 (+ oxygen) |
| `validate` (summary format) | working; run on all 24 historic EA summaries |
| Lab readers, join to lab results | oxygen (Scripps ODF `.LST`) working on SR2614; others not started |
| Sample Issues `assign` / `exclude` / `review` | recorded in the workbook; applied once lab readers exist |
| `validate inputs` (workbook/btl/lab cross-checks) | partly inside `build` (start position/time, Niskins fired) |

## 2. Usage

Run from this folder in the `ea_tools` environment (or use the `asset-discrete` command after the editable install
in the top-level README):

```bash
cd ~/code/ooiea-mooring-tools/discrete
python -m asset_discrete.cli new  Endurance-26_SR27XX_Transcription.xlsx
python -m asset_discrete.cli migrate OLD.xlsx NEW.xlsx
python -m asset_discrete.cli build WORKBOOK.xlsx BTL_DIR OUTPUT_DIR --version 1.00 --note "Assembled. CTD data only."
python -m asset_discrete.cli build WORKBOOK.xlsx BTL_DIR OUTPUT_DIR --lab oxygen=O2.LST \
    --version 1.01 --note "Added discrete oxygen"
python -m asset_discrete.cli validate FILE.csv [FILE.csv ...] --out issues.csv \
    --asset-management ~/code/asset-management
```

- `new` writes the blank transcription workbook (instructions on its README sheet).
- `migrate` moves a filled workbook from an older layout to the current one, matching columns by header. Renamed
  columns are carried over, retired ones dropped; any other unknown column stops the run. Write to a new file and
  compare before replacing the original.
- `build` writes `<Expedition>_<Cruise>_Discrete_Summary.xlsx`, `..._README.txt` and `..._build_log.txt` into
  OUTPUT_DIR. The README revision history is read back from OUTPUT_DIR and the new `--version` line appended; a
  version already in the history stops the run. `--lab ANALYSIS=PATH` (repeatable; `oxygen` for now) joins a lab
  file's results to the drawn samples; analyses without a file stay drawn-not-received. Check the build log after
  every build.
- `validate` checks finished CSVs (header and order, fill value, flag format and assigned bits, value/flag
  consistency, times and cruise window, cast metadata, replicate flags, CTD bit 7, physical ranges, ...). Without
  `--asset-management` the cruise IDs and windows are not checked. Exit status 1 when there are errors.

The release CSV is not written by the build: once a cruise is final, open the xlsx in Excel and Save As
"CSV UTF-8". Numbers in the xlsx carry number formats that match their published text, so the saved CSV is the
published file (checked against a directly written CSV for SR2614 v1.00).

## 3. Workflow

1. Transcribe the paper Rosette Sampling Logs into a workbook made with `new` (going forward, filled in on the
   ship). Uncertain reads go in Transcription Check; the reviewer fixes the value and deletes the check.
2. `build` with the `.btl` files -> version 1.00 (CTD only, every drawn sample "drawn, not received").
3. As lab files arrive, drop them in unedited and rebuild with a new version. Problems with lab results are
   resolved on the Sample Issues sheet, never by editing a lab file or the output.
4. When final, save the CSV from the xlsx and publish it with the README.

Cruise folder (the tool only takes paths; this is the suggested layout):

```text
Endurance-25_SR2614/
    Endurance-25_SR2614_Transcription.xlsx
    *Sampling_Log*.pdf      # scans the workbook was typed from
    ctd/                    # one .btl per cast, named as the Cast Log CTD File
    labs/                   # lab files exactly as received
    output/                 # written by build
```

## 4. Sources of truth

| Input | Who edits it | Read by |
|---|---|---|
| Transcription workbook (one per cruise) | people, from the paper Rosette Sampling Logs | build |
| Sea-Bird `.btl` files (one per cast) | nobody; output of SBE Data Processing | build |
| Lab return files (as received) | nobody; never hand-edited | build (planned) |
| `asset-management/cruise/CruiseInformation.csv` | as today (by hand) | validate |
| `asset_discrete/reference/` (template header, flags, flag map, stations) | rarely, via git | everything |

The summary and its README are outputs, regenerated on every build and never edited by hand. `cruiseList.csv`,
`stationNames.csv` and `targetAssets.csv` from the old notebooks are retired: cruise windows come from
asset-management; the station list is `reference/stations.csv` (it also feeds the workbook's Site dropdown).

## 5. Transcription workbook

Sheets: README, Cruise, Cast Log, Niskin Log, Sample Issues, Notes, Lists. Sheet and header names are the contract
with the build (`workbook.py` SCHEMA); headers carry their units and formats, e.g. `Start Time [UTC HH:MM]`.

- **Cast Log**: one row per cast, only columns that reach the summary. Site is interpreted by the transcriber
  (CE09P -> CE09). Longitude degrees are entered negative (west). If the sheet has no start time, the `.btl`
  `* NMEA UTC (Time)` value is entered and Notes says so. Operator, cast purpose, flow-through, bottom/end
  positions and the pH column of the CGSN sheet are not transcribed.
- **Niskin Log**: one row per Niskin that was sampled or has a problem to record (leaked, empty, did not trip).
  Bottles fired as spares and not sampled are left out. Each row carries its depth's trip time, trip depth,
  temperature and salinity (the sheet's "Potential Temp" column is in-situ temperature). Sample numbers go on the
  Niskin they were drawn from as comma separated lists ("49, 50, 51"); a leaking or empty Niskin is never
  sampled, so samples written on its row (or moved with an arrow) belong to the next Niskin.
- **Sample Issues**: one row per sample problem. `flag` gives a sample a Sample Flag (shipboard staff use only
  Cast, Niskin, Analysis, Sample ID, Sample Flag, Reason); `assign` puts a lab row (Lab File + Lab Sample Key,
  Lab File Row only to tell duplicate keys apart) on a cast/Niskin/sample; `exclude` drops a lab row (standards,
  test runs); `review` is undecided and will block the build.
- **Notes**: published text that does not belong to one flagged row (cruise-wide events, cast ranges such as
  `1-9`, analysis-wide statements). Cast and Niskin take a number, a range or All.
- **Lists**: dropdown values. Every dropdown is strict except Notes Cast/Niskin; lists grow with entries added
  directly under the last one (no blank rows). One-off sites go on that cruise's Lists sheet, recurring ones into
  `reference/stations.csv`.

Formatting (widths, centring, number formats, header heights) follows the reviewed Endurance 25 workbook
(`workbook.py` LAYOUT). Spreadsheet style: no fills, comment triangles or filters.

## 6. CTD side

### 6.1 `.btl` contract

The parser (`btl.py`) reads columns by the header names, never by position, plus the NMEA header lines and the
sensor calibration dates in the embedded XMLCON.

Required SBE variables, in this order (Bottle Summary writes its derived variables first, then the Data Conversion
variables in their configured order; reference file SR2614_01.btl):

| # | SBE name | Summary column / use |
|---|---|---|
| 1 | OxsolML/L | CTD Oxygen Saturation [mL/L] (Bottle Summary derived) |
| 2 | Sal00 | CTD Salinity 1 [psu] (Bottle Summary derived) |
| 3 | Sal11 | CTD Salinity 2 [psu] (Bottle Summary derived) |
| 4 | PrDM | CTD Pressure [db] |
| 5 | DepSM | CTD Depth [m] (NMEA latitude; default 45.75 N only if NMEA is missing, noted in the workbook) |
| 6 | Latitude | CTD Latitude [deg] |
| 7 | Longitude | CTD Longitude [deg] |
| 8 | T090C | CTD Temperature 1 [deg C] |
| 9 | T190C | CTD Temperature 2 [deg C] |
| 10 | C0S/m | CTD Conductivity 1 [S/m] |
| 11 | C1S/m | CTD Conductivity 2 [S/m] |
| 12 | Sbeox0ML/L | CTD Oxygen [mL/L] (hysteresis and tau corrections on) |
| 13 | FlSP | CTD Fluorescence [mg/m^3] (Seapoint; other fluorometer names added when a cruise needs them) |
| 14 | CStarAt0 | CTD Beam Attenuation [1/m] (XMLCON path length 0.25 m) |
| 15 | CStarTr0 | CTD Beam Transmission [%] |
| 16 | Ph | CTD pH, only if a pH sensor is fitted |
| 17+ | Par, AltM, TimeS, Scan | QC only, not in the summary (Spar dropped) |

Variables are read by name. A missing required variable is an error. A different order is only a note: keep the
order consistent across casts and cruises, but nothing depends on it.

Planned: the `**` header lines (station, cast, cast type) are read by key and cross-checked against the
workbook; a mismatch is reported for someone to double check (e.g. SR2614 cast 1 header says `CEO2`, the workbook
says CE02). Cast numbers and CTD file names are kept exactly as recorded by the ship (`_01` vs `_001`
varies) because the same files are referenced elsewhere; the summary maps name to name, never renames. The
`** Operator` line is ignored; the operator is not transcribed or carried anywhere.

Start position comes from the .btl NMEA header lines and is checked against the Cast Log position (warning
beyond 1 km; catches transposed digits). If the .btl has no NMEA position, the Cast Log position is used and
the build log says so. Start time comes from the Cast Log; when the log has none, the transcriber enters the
`* NMEA UTC (Time)` value from the .btl and says so in Notes. The build warns when the two differ by more than
15 minutes. Sensor calibration dates older than one year set CTD parameter flag bit 6 and add one README note.

A missing required variable is an error naming the variable, which is the cue to fix the ship's processing (as
with SR2611, which delivered `Sbeox0Mm/L` only and no attenuation). The ship processing setup should be
standardized to this list; a short SOP page goes in the README.

### 6.2 No silent conversions

The build does not compute oxygen in mL/L, oxygen solubility or attenuation itself. If they are missing, the .btl
is reprocessed. This keeps every CTD value traceable to SBE software and avoids adding gsw and our own
Garcia-Gordon implementation. (Reversible: a `--derive` option could be added later if reprocessing is ever
impossible, with the derivation recorded in the README.)

## 7. Join and flag rules

Join keys for the lab readers (oxygen implemented; the rest planned, from the E18 work, all proven against the
v1.49 summary):

| Analysis | Workbook key | Lab key |
|---|---|---|
| oxygen | cast + Niskin + flask (Sample ID) | Cst, Bot, Flask |
| salinity | Sample ID (salts bottle #) | `sbot` column; the analyst-typed `CCNN` label is only cross-checked |
| nutrients | Sample ID | `E18-nn` (prefix per cruise) |
| chlorophyll | Sample ID (filter #) | Sample ID |
| dic_ta | Sample ID | `OOI E-18 DIC n` / `DIC-n`; CRM rows dropped |

Oxygen (`labs/oxygen.py`): results are matched on cast + flask; a lab Niskin that disagrees with the workbook, a
lab flask that is on no Niskin Log row, a duplicate cast/flask, or an `Expedition:` header naming another cruise
stops the build. The reported `ml/l` text is used as is (ODF already applies standardisation, blank and flask
volume). The leading station code is not a key; the build warns when its number disagrees with the cast's site
(SR2614 cast 1, CE02, is coded `0001` throughout). The lab's draw temperature is checked against the log
(warning beyond 0.2 C) and the log wins (SR2614 cast 1 Niskin 8: log 14.7, lab 14.72). Lab comments (e.g. `OT
0.2810` on SR2614 flasks 49, 67, 71; meaning not yet confirmed with the lab) go to the build log only and set no
flag. A received result gets bit 2, or only the Sample Issues flag (plus bit 0) when one applies.

Sample Issues apply after parsing, before the join. `flag` gives a sample a Sample Flag (shipboard staff enter
these for problems seen at collection; lab-driven flags go here too); `assign` puts a lab row (file + key, plus
Lab File Row only to tell duplicate keys apart) on a cast/Niskin/sample; `exclude` drops a lab row (standards,
test runs); any `review` row blocks the build. For a duplicate or unmatched lab key the build proposes the
likely Niskin (replicate and CTD profile agreement) as a suggested `assign` row; it never moves a result on its
own.

Flags are derived, never typed as bit strings:

- Blank flag text in the workbook = Acceptable / No problems noted (bit 2).
- Bit 0 (Notes/Other) is set on every row and flag column that a published note (section 10) applies to.
- Discrete sample drawn (listed on its Niskin Log row) but no lab result yet = bit 1, value -9999999. The build
  splits each comma separated sample list into one record per sample before joining to lab results.
- Replicate flags from the count of samples of that analysis from that Niskin: 1 -> bit 2, 2 -> bit 3, 3 -> bit 4.
- CTD conductivity/oxygen/fluorescence/pH flags get bit 7 on the row carrying the corresponding discrete sample
  (drawn, whether or not a result exists; matches 2019+ files and the drawn-not-received convention of earlier ones).
- Data-only casts (no Niskins fired) get CTD File Flag bit 1 and fill everywhere else.
- CTD parameter flags get bit 6 (calibration coefficients > 1 year old) automatically when the sensor's
  CalibrationDate in the .btl/.xmlcon header is more than 365 days before the cast start time. Applies per sensor:
  T1/T2, C1/C2, pressure, oxygen, fluorometer, C-Star, pH.
- Row layout: one row per (cast, Niskin, replicate index), as today; a Niskin with no samples gets one row.
  Summary rows are the Niskin Log rows: Niskins that were sampled or have a problem to record. Their CTD values
  come from the .btl. Fired bottles not on the Niskin Log are not in the summary; the .btl is only used to check
  that every Niskin on the log was fired.

## 8. Validation

### 8.1 Inputs (planned `validate inputs`; build already checks start position/time and fired Niskins)

Errors: workbook schema (sheet/header names), unknown flag text, unknown station, cruise not in CruiseInformation,
cast without a .btl, Niskin on the log not fired in the .btl, duplicate or unknown lab keys, lab sample with no
workbook sample, open transcription checks, `review` sample issues.

Warnings: log trip depth vs .btl pressure (> 2 m or 2%), log start position vs NMEA (> 1 km), log start time vs
NMEA (> 15 min), lab depth vs trip depth (DIC/chl sheets carry depth), chl volume log vs lab, oxygen draw temp
log vs lab, physical ranges by depth class, replicate disagreement (per-analysis tolerance), lab comments
(echoed for review).

### 8.2 Summary format (`validate`)

The prototype run on the 24 historic sheets on 2026-10-22: header and order, -9999999 exactly, 16-bit flag
format and assigned bits per flag type, value/flag consistency (value with fill flag, acceptable flag with fill
value, value with drawn-not-received), timestamp format and cruise window, cast metadata identical per
(cruise, CTD file, cast), replicate flags vs row count, CTD bit 7 vs discrete samples, data-only casts, physical
ranges (suppressed when the value is already flagged questionable/bad), beam attenuation vs transmission
(25 cm path), depth/pressure, discrete vs CTD salinity/oxygen (warnings), precision > 8 significant digits,
duplicate rows, whitespace. Output: issues CSV (file, line, column, severity, code, value, message).

## 9. Output conventions (open decisions are marked)

- Columns exactly as `reference/discreteSummary_template.csv`.
- The build writes a formatted `<Expedition>_<Cruise>_Discrete_Summary.xlsx` (sheets "Discrete Summary" and
  "Discrete Data Flags"), the `..._README.txt` (UTF-8, LF, historic layout) and a `..._build_log.txt` of
  cross-check results. Numbers are stored as numbers with a number format matching their text (fill -9999999 as
  `0`), flags and times as text, so the release CSV is saved from the xlsx in Excel as "CSV UTF-8" (BOM + CRLF,
  same as every historic EA file) once the cruise is final. Checked: a "save as shown" CSV of the SR2614 v1.00
  xlsx is identical to the CSV the build produced directly.
- File names `<Expedition>_<Cruise>_Discrete_Summary.*` (spaces in the expedition become hyphens); the version
  lives in the README revision history, not the file name (matches current EA practice).
- **Decision: numeric precision per column.** Proposal: report the lab's own precision (decimals as delivered in
  the lab file, after reading as text), and fixed decimals for CTD values (pressure 3, T 4, C 6, S 4, O2 4, ...).
- Target Asset: as transcribed (comma + space separated), not checked against asset management. Casts are not
  always next to a mooring or glider; date, latitude and longitude link samples back to a mooring/glider.
- CTD File: the .hex name exactly as recorded by SeaSave (leading/trailing whitespace stripped only).
- Flag definitions come from `reference/flags.csv` only. Any flag table written alongside the summary uses the
  summary's own terms ("Discrete Replicate Flags", not the "Discrete Duplicate Flags" heading in the E18 xlsx).
- An analysis not drawn from a Niskin on the log: value -9999999, discrete flag bit 9 ("Sample not drawn for
  this measurement from this bottle"). Historic sheets wrote -9999999 in the flag column instead.

## 10. README generation

Revision history is appended per build from `--version` and a `--note`. Summary Notes, in the existing "Cruise,
Cast, Bottle, Flag -- text" form, come from:

- the Notes on any Cast Log or Niskin Log row that carries a flag (Cast Flag / CTD File Flag / Niskin Flag);
- the Reason on Sample Issues `flag` rows (flag column = the analysis's discrete flag);
- every row of the Notes sheet (text with no single flagged row: cruise-wide events, cast ranges such as `1-9`,
  analysis-wide statements).

Nothing is entered twice. Notes on unflagged rows, Transcription Checks and the Reason on assign/exclude/review
rows stay internal. Lab method blocks (e.g. the Hales detection limits) will live in `reference/labs/<lab>.txt`
and be included when that lab's files are used (parked; to be designed with the lab readers).

## 11. Tests

`pytest` from the repo root, or `python -m pytest` here. `tests/data/SR2614_01.btl` is a real cast; the
transcription workbook for it is built in `tests/conftest.py`. Planned acceptance test: E18 (workbook + lab files +
.btl) reproducing the v1.49 oxygen, salinity, chlorophyll and DIC values exactly.

## 12. Next steps

1. Confirm the meaning of the ODF `OT` comment; review SR2614 oxygen replicate spread (up to 6.6% at low O2).
2. Salinity (Autosal), chlorophyll, nutrients and carbon readers with trimmed real fixtures; the join; Sample
   Issues `assign`/`exclude`/`review`.
3. `validate inputs`; lab method text in `reference/labs/<lab>.txt` added to the README when that lab's files are
   used.
4. E18 acceptance test; then rebuild earlier cruises from their cast sheets.

## 13. Known data issues found so far (for the record)

- SR2520 (E23): CTD Fluorescence column holds beam attenuation (all 51 rows match -ln(T)/0.25 to 1e-4),
  attenuation column holds transmission, transmission is 0.00. True fluorescence is missing. Rebuild E23's CTD
  columns from the SR2520 .btl files rather than patching.
- SKQ202405S (E20): attenuation about 1/4 of what transmission implies (consistent with a 1 m path length in the
  XMLCON). Unconfirmed; check the XMLCON.
- E10, E14, E16, E18: salinity flags still say drawn-not-received although values are present.
- E01-E09, E15: salinity drawn, never analyzed; flags already say so (not an error).
- flags.csv (2021 copy) had discrete sample flag bit 9 in the Niskin flag column; corrected 2026-10-22 to match
  the E18 xlsx flag table. No historic sheet sets bit 9, so earlier validation results are unaffected.
- E18: duplicate nutrient keys (E18-03 x2, E18-08 x3), 7 implausible nutrient values, chl volume 150 vs 100 mL on
  16 filters -- held as `review` rows in the E18 workbook.
