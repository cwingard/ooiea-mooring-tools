"""Python calibration-file generators for Endurance and CGSN uncabled arrays.

This package is a from-scratch Python port of the Matlab scripts in
asset-management/tools/matlab/Endurance_cal_scripts. It does not
import from, depend on, or modify asset-management/tools/cal_scripts
(the RCA/cabled-array Python parsers) -- the two arrays use different
asset-lookup conventions and calibration filename schemes, so sharing
more than the csv output format would couple unrelated logic.
"""
