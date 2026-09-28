# calibration -- asset-management calibration csvs

Generates the per-instrument calibration coefficient csvs in `asset-management/calibration/<CLASS><SERIES>/` from
vendor or QCT source files (dev files, `.cal` files, cap/log captures). One source file in, one csv (plus companion
`.ext` array files for OPTAA) out.

Python port of the MATLAB scripts in `asset-management/tools/matlab/Endurance_cal_scripts`. Independent of RCA's
`asset-management/tools/cal_scripts`; neither imports the other. No YAML/RDB dependency.

## Setup

Run from this `calibration/` folder, in the `ooi` conda environment. Standard library only, except PCO2W, which
needs `pdfplumber` (`conda install -c conda-forge pdfplumber`); `pytest` for the tests.

```bash
cd ~/code/ooiea-mooring-tools/calibration
python -m asset_cal.cli --help
```

## Generating a calibration csv

```bash
python -m asset_cal.cli SPKIR-B path/to/DI7255L.cal --asset-management ~/code/asset-management
```

- The first argument is `CLASS-SERIES`. The series is always stated by the operator, never looked up from the
  serial number (the MATLAB serial lists were stale for nearly every class).
- The csv goes into `<asset-management>/calibration/<CLASS><SERIES>/`, named
  `CGINS-<CLASS><SERIES>-<serial, 5 digits>__<caldate>.csv`. The folder must already exist.
- METCTD (the METBK conductivity/temperature sensor) has no folder of its own: always pass `--output-dir METBKA`.
  Its "series" is the source format: `METCTD-CAL` for the vendor `.cal` file, `METCTD-CAP` for a QCT cap/log capture.
- Input filenames are never parsed: point the tool at any file name in any folder. Everything it needs comes from
  the file contents, except the calibration date for DOSTA and PHSEN, whose QCT captures do not contain it -- pass it
  from the vendor certificate with `--caldate YYYYMMDD` (required for those two, rejected for every other class).
  The source file name is copied into the notes column for traceability only.
- PCO2W reads the vendor PDF certificate; every value written comes from it. `--qct <capture>` is optional: with it,
  values are identified against the sensor's QCT capture (so any certificate layout works) and any disagreement
  stops the run; without it, the certificate's Table 1 must be in the known layout or the run stops and asks for
  `--qct`. Tavg is written at the certificate's precision, not the sensor's rounded value.
- DOFST-K reads the Sea-Bird SBE 43F certificate PDF; `--qct` (the MMP QCT with the 52-MP `dc` output) is optional.
  Soc is the certificate's adjusted value if marked `(adj)`, else the host-adjusted value from the capture, else the
  certificate Soc x 1.0354 (estimate). See `docs/dofst_soc_adjustment.md`.
- Values printed at different precision (a vendor file with 7 digits, a capture with 6) agree if they differ by no
  more than one unit in the last place of the less precise one.
- Rule for every class: where both a vendor document and what the instrument reports are available, they must agree.
  A disagreement is an error, never silently resolved.
- There is no interactive review step. Review with `git diff` / `git status` in asset-management before committing.

## Checking a parser against asset-management (`--mode test`)

`--mode test` writes every generated file as `_preview_<name>` next to where the real file would go, and never
touches the real file. To validate a parser, run it on the source file of a calibration that is already committed
and compare:

```bash
python -m asset_cal.cli FLORT-D <previous source file> --asset-management ~/code/asset-management --mode test
cd ~/code/asset-management
diff calibration/FLORTD/_preview_CGINS-FLORTD-01153__20241230.csv calibration/FLORTD/CGINS-FLORTD-01153__20241230.csv
```

Delete the preview afterwards. A difference is not automatically a parser bug: committed files may have been
hand-corrected after the MATLAB run (`git log --follow <file>` shows more than one commit) or written by an older
version of the MATLAB script with different notes text. Coefficient values must match; notes may not.

## Source files

Vendor/QCT source files come from Alfresco (no API; download by hand). Keep them outside both repos, under
`Working/cal_sources/`, one folder per vendor calibration package as downloaded.

## Parser status

| Class-series | Source | Validated against a real source file |
|---|---|---|
| SPKIR-B, SPKIR-J | Satlantic `.cal` | Yes -- byte-identical to committed `CGINS-SPKIRB-00255__20241206.csv` |
| PARAD-J | factory dev file | Sample from MATLAB header only |
| PHSEN-D | QCT capture (+ `--caldate`) | Yes -- values match committed PHSEND P0122 (2024-12-10) |
| FLORT-D, -J, -K | WET Labs dev file | Yes -- names and values match committed FLORTJ 1084 (2025-03-31) |
| DOSTA-D, -J | vendor/QCT | No |
| CTDBP-C, -E | cap file | No |
| PRESF-A, -B, -C | QCT capture (not the SBE `.cal`) | No |
| OPTAA-C, -D, -J | WET Labs dev file | Yes -- csv and both `.ext` files match committed OPTAAD 135 (2024-02-08) |
| NUTNR-B, -J | Satlantic/Sea-Bird cal file | Yes -- byte-identical to committed `CGINS-NUTNRB-01059__20241213.csv` |
| METCTD-CAL, -CAP | `.cal` / QCT capture | Yes -- real capture and vendor `.cal` for SN 13471 agree exactly |
| PCO2W-B | PDF certificate (+ optional `--qct`) | Yes -- C0062 certs 2017-2025 match AM; 2025 also with its capture |
| DOFST-K | SBE 43F PDF certificate (+ optional `--qct`) | Yes -- 4511 matches AM; 4361 checked against MMP QCT |
| PARAD-K | PDF certificate | Not implemented |

"No" means the parser was ported from the MATLAB token positions without a real file to test against. Run it in
`--mode test` against a committed calibration before using it for a new one.

## Adding a class

Add `asset_cal/<class>/parser.py` with a `SeriesParser` subclass (`parse()` returns a record exposing
`serial_number` and `series`; `write_csv()` writes into an existing folder), then add one entry per series to
`PARSERS` in `asset_cal/cli.py`. Keep coefficient values as the exact strings from the source file; never round-trip
them through float.

## Layout

```text
calibration/
    asset_cal/
        cli.py            # CLASS-SERIES dispatch, --mode test previews
        common/           # csv writer, SeriesParser base class
        <class>/          # parser.py + tests/ (with fixtures/ where real files exist)
    tests/                # cli tests
```

## Tests

```bash
python -m pytest
```
