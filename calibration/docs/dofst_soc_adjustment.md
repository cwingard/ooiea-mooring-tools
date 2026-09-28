# DOFST-K (SBE 43F) adjusted Soc

Background for how `asset_cal/dofst/parser.py` chooses the oxygen signal slope (Soc, `CC_oxygen_signal_slope`).

## Why Soc is adjusted

Sea-Bird calibrates the 43F in house on a pump with a higher flow rate than the pump on the host (glider or McLane
profiler). The flow difference changes the oxygen reading, often by ~2%. For profilers and gliders Sea-Bird then
installs the 43F on its host system and adjusts Soc against a Winkler sample. The adjusted Soc is the correct value.

From Sea-Bird (Greg, to Russ Desiderio):

> When we calibrate the 43F's in house they're connected to stronger pumps with higher flow rates than the pump
> normally installed on gliders. This difference in flow will result in a DO value that is often ~2% different than
> the glider's value. To compensate for this, we will install the 43F on the system that it is normally installed on
> and do a SOC adjustment to correct for this difference with a Winkler and the 43F's output when installed on the
> glider. As such, the adjusted SOC value is the correct one to use.

## The 1.0354 estimated factor

When Sea-Bird did not supply an adjusted Soc, Russ Desiderio estimated it as 1.0354 x the unadjusted Soc:

> SBE did not supply the SOC(adjusted) value for the DOFST; their factory standalone cal provides a signal-slope value
> scaling factor denoted as Soc. They usually then do a 1 pt cal for profilers and gliders to adjust the scale factor
> for flow rate for when the DOFST is hooked up to non-factory-cal plumbing. I've attached an excel file which shows
> that historically the Soc(adj) value can be determined by multiplying the Soc value by 1.0354.

`dofst_adjusted_soc_factor.xlsx` is that workbook: 14 calibrations of WFP sensors 2496, 2498 and 3535 (2015-2022)
with both Soc values. 1.0354 is the least-squares slope through the origin (mean ratio 1.0353). The individual ratios
range from 1.0099 to 1.0792 (standard deviation 0.017), so the factor is an estimate good to roughly +/-2% for any one
calibration. The "R2=0.99973" quoted in some asset-management notes is the uncentered R^2 of the through-origin fit;
the ordinary R^2 is 0.977. Using no adjustment at all would bias oxygen low by ~3.5% on average for these sensors.

## Rules the parser applies

1. Certificate Soc marked `(adj)`: used as printed ("vendor adjusted Soc").
2. No `(adj)`, and the MMP QCT capture (`--qct`, 52-MP `dc` output) shows a host-adjusted Soc -- ratio to the
   certificate Soc in (1.000, 1.100]: the host value is used and noted with its date.
3. Otherwise: certificate Soc x 1.0354, noted as an estimate.

With a capture, the oxygen serial must match, its date must not precede the certificate's, and Foffset, A, B, C and E
(and Soc, when the certificate's is adjusted) must agree within one unit in the last printed place of the less precise
value. Anything else stops the run.

## Known case: 4361 (certificate 31-Jan-24)

The certificate has no `(adj)`. The 52-MP on profiler ML14378-01D (QCT 3310-00100-00170, March 2025) holds
Soc = 3.8013e-04 dated 06-mar-24, 1.0388 x the certificate's 3.6592e-004; its other coefficients match the
certificate. asset-management's `CGINS-DOFSTK-04361__20240131.csv` has the 1.0354 estimate (3.788694e-004). With the
capture, rule 2 applies and the parser writes 3.8013e-04. That the 06-mar-24 value is Sea-Bird's host adjustment is
inferred from its date and ratio, not documented.
