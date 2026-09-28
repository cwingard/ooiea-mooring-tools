% append_deploy_ce06issm.m
% desiderio 28-oct-2017
% desiderio 01-nov-2017  added subroutine to automatically check for new
%                        sensor.uids and if any are platcons, add new
%                        platcon uids to asset record.
% desiderio 15-oct-2019  added latlon screen output and negative lon check
% desiderio 01-apr-2021  2 columns have been added to the deploy.csv files
%                        for populating 'RoundAbout'. see deploy.csv columns
%                        section of the code (~ line 102) for documentation.
%                        Improved parsing of instruments not deployed.
% desiderio 14-sep-2023  added assembly_template_revision constant entries 
% desiderio 18-dec-2023  (1) add CUID_Recover to previous deployment
%                        (2) add watch circle orbit
%                        (3) add WAVSSM reference designator
% desiderio 07-feb-2024  change sensor.uid for WAVSSM reference designator
%                        from CGINS-ADCPTM to CGINS-WAVSSM (introduced
%                        via Pull Request 1086).
% desiderio 15-mar-2024  (1) added Dependences listing at program top
%                        (2) Preparation of config.xlsx file standardized
%                        (3) Additional Notes documentation added
% wingard 20-mar-2024    removed desiderio idiosyncracies and adapted to local
%                        directory structure
%
% DEPENDENCES:
% find_missing_bulkSensor_entries.m
% find_missing_bulkEng_entries.m
% sub_append_platconUID_to_engAssetRecord.m

% APPENDS SURFACE MOORING ASSET MANAGEMENT DEPLOYMENT INFO
% to an OOI CI Deploy.csv file downloaded from GitHub: 
%     https://github.com/ ...
%     ooi-integration/asset-management/tree/master/deployment
%
% Inputs: (hardcoded at program top)
%          CE06ISSM_Deploy.csv      (see deploy_filename variable)
%          prepped config.xlsx file (see config_filename variable)
%
% Output:  CE06ISSM_Deploy.csv
%
% If the previous deployment's stopDateTime recovery information, which
% should be formatted as yyyy-MM-ddThh:mm:ss, is located in cell D5 of
% the prepped config file, then it will be written out verbatim into
% the appropriate rows and column of the output deploy.csv file.

%               PREPARATION OF CONFIG.XLSX FILE
% The config.xlsx file must be prepared as follows.
%
% Within excel the 2nd column must be copied and inserted so that 
% columns 2 and 3 are identical. Then column 3 must be formatted so that
% all the entries are forced to be text. The simple attempt to do this,
% by highlighting the column, right clicking, selecting "Format Cells"
% (Number tab), "Text", OK, *WILL NOT WORK*. Instead:
%
% Right click the 2nd column to select it and bring up the context menu 
% Click Copy
% Again Right click the 2nd column 
% Insert Copied Cells 
% Select the 3rd column, then:
%     Click on Data tab
%     Select "Text to Columns" in Data Tools
%     Select Fixed Width
%     Next; Next;
%     Select "Text" in Column data format
%     Finish.
%
% Besides standardizing the excel cell formats for import, the original 
% S/N entries are preserved in the 2nd column while modifications
% can be made in the 3rd column to make the entered serial numbers
% conform to the OOI conventions. This program reads in the entries
% in this 3rd column to create sensor.uids for export.
 
% Config.xlsx File Preparation Checklist
% (0a) Optional: enter previous deployment's stopDateTime in cell D5.
% (0b) Optional: enter previous deployment's CUID_Recover in cell D11.
% (1) Make sure MOORING S/N (row 4) is correct (especially deployment #)
% (2) Anchor Launch Date (row 5) format is YYYY-MM-DD (GMT, not local)
% (3) Anchor Launch Time (row 6) format is hh:mm or hh:mm:ss (GMT)
% (4a)  Format Lat (row 7) as decimal degree character vector, 5 decimal places
% (4b)  Format Lon (row 8) as decimal degree character vector, 5 decimal places
% (5) Water Depth (row 9) is entered
% (6) Cruise # (row 11 entry) is ID'd as archived in CruiseInformation.csv
% (7) Make sure platcon bottle assignments are present in column 4.
%     (and that DCL36 has replaced DCL35).
% (8) Entries for instruments that are not deployed should be either
%     'N/A', 'None', or 'Not Deployed' (case insensitive).
% (9)  Adjust non-OOI standard serial numbers:
%      (a) Platcon S/N that are of the form YEAR-xxxx 
%      (b) Do NOT need to alter SBE CTD or PRESF SN if the serial number
%          is prefixed with 16- 16P- 26- or 26P-).
%      (c) Do NOT need to alter CAMDS S/N entry).
%
%*****************************************************************************
%*****************************************************************************
% (10) (a) Duplicate (Copy; Insert Copied Cells) the ADCPT S/N row in the mfn*
%          section so that there are two consecutive identical ADCPT S/N rows*
%      (b) In the second row change 'ADCPT' to 'WAVSS' (not 'WAVSSM'!)
%*****************************************************************************
%*****************************************************************************
%
% (11) SAVE CONFIG.XLSX CHANGES before running this code.
%
% Additional Notes:
% If all subroutine dependences are active then local master bulk_load
% is checked for the existence of sensor and platcon serial numbers.
% 
% (a) IF THE SERIES OF A DEPLOYED INSTRUMENT DOES NOT MATCH THE SERIES
%     DESIGNATION IN THE CORRESPONDING REFERENCE DESIGNATOR then the
%     code will not find that serial number in bulk asset management;
%     this will be flagged in the command window as a missing entry in
%     bulk_sensor. The EASY FIX for this is to make a one-time edit of
%     the series designation in the appropriate second column of the 
%     refdes_sensor cell array. For example, if an OPTAA-C instrument
%     is deployed on an nsif, then the second value in the RIDxx-xx-OPTAAD
%     row should be changed to 'CGINS-OPTAAC-xxxxx'. The reference 
%     designators themselves (first column) must remain unchanged.
% (b) Not all variants of serial number formats have been foreseen. For
%     example, if 'P00072' is entered for a PHSEN-D instrument, the code
%     will interpret this as missing PHSEND serial number '00072' instead
%     of as the desired 'P0072'. The fix is to change the value in the
%     3rd column in the edited  config.xlsx to the proper value 'P0072'.
mode = 'update';  % write to local master
ncol = 20;  % number of columns in deploy_filename
deploy_path = 'C:\Users\chris\code\asset-management\deployment\';
deploy_filename = 'CE06ISSM_Deploy.csv';
deploy_filename = [deploy_path deploy_filename];
config_path = 'C:\Users\chris\OneDrive - Oregon State University\OOI\buoys\Deployments\scripts\platforms\deploy\';
config_name = 'CE06ISSM-00020.xlsx';
config_filename = [config_path config_name];

disp(' ');
disp(['Mooring_uid: ' config_name(1:14)]);
disp(' ');

% deployment depth [meters] relative to sealevel
depBuoyWell = '0';    % for instruments in the buoy well
depBuoyInshoreCTDBP = '1.0';  % 2018-10-10
depBuoyInshoreFLORT = '1.5';  % 2018-10-10
depBuoyInshoreVELPT = '1.6';  % 2018-10-10
depNSIF = '7';        % all nsif instruments
% depMFN = (waterdepth).

% watch circle orbits:
% inshore  (issm) 100
% shelf    (shsm) 250 
% offshore (ossm) 500
orbit = 100;
assembly_template_revision_entry = 'B';

% the deploy_csv file has the following columns which need to be filled
% out for each instrument in a given deployment (which is what this
% code does). the columns can be in any order; therefore, this code
% reads in the deploy.csv file and then SORTS THE COLUMNS INTO THE
% ORDER GIVEN BELOW so that a cell array can be created containing the
% deployment's entries and then appended to the old data. following each
% column heading is a designation as to the nature of the row entries:
% empty         ('' row entries in csv file)
% single-valued (same entry for each row in a GIVEN deployment)
% variable      (entry is row-dependent)
%
%   1   'CUID_Deploy'              single-valued (cruise ID)
%   2   'CUID_Recover'             empty for the current deployment
%   3   'Reference Designator'     variable
%   4   'deployedBy'               empty
%   5   'deploymentNumber'         single-valued
%   6   'deployment_depth'         variable (dependent on platform)
%   7   'lat'                      single-valued
%   8   'lon'                      single-valued
%   9   'mooring.uid'              single-valued            
%  10   'node.uid'                 empty for non-mobile moorings
%  11   'notes'                    optional
%  12   'orbit'                    single-valued
%  13   'recoveredBy'              empty
%  14   'sensor.uid'               variable
%  15   'startDateTime'            single-valued
%  16   'stopDateTime'             empty for the current deployment
%  17   'versionNumber'            single-valued
%  18   'water_depth'              single-valued
%  19   'electrical.uid'              either empty or single-valued
%  20   'assembly_template_revision'  either empty or single-valued

% 2021-03-19: 2 columns have been added to the deploy.csv files to aid
% transferring asset management data into the roundabout system:
% "electrical.uid"
% "assembly_template_revision"
% they are irrelevant as far as CI-AM build tests are concerned. the
% easiest code fix for me is to read in the deploy.csv file and sort
% as done previously (note that capital letters come before lower case)
% and then move the new columns to the back. this maintains my hard-
% coded column numbering.

% just before writing out the data, change the column ordering for
% convenient (for me) viewing in GitHub - move new columns to the rear.
reorder_columns_on_output = [ 5   3  14     15  16   7  ...
                              8   9   1     10  17   4  ...
                              2  13  12      6  18  11  ...
                             19  20                     ];

% config.xlsx row numbers for parsing entries required by deploy.csv
idx_MooringSN =  4;  % mooring name and deployment number
idx_LaunchDate = 5;
idx_LaunchTime = 6;
idx_Lat        = 7;
idx_Lon        = 8;
idx_WaterDepth = 9;
idx_CruiseID =  11;

% these columns contain reference designator and sensor.uid values.
% to emphasize the 1:1 correspondence, and for proofreading,
% they are entered as a 2-column cell array. Make future changes
% on this master array.
refdes_sensor = {
    'CE06ISSM-SBC11-00-CPMENG000'     'CGCON-ECPM01-xxxxx'
    'CE06ISSM-SBD17-00-DCLENG000'     'CGCON-EDCL17-xxxxx' 
    'CE06ISSM-RID16-00-DCLENG000'     'CGCON-NDCL16-xxxxx'  
    'CE06ISSM-MFC31-00-CPMENG000'     'CGCON-MCPM03-xxxxx'
    'CE06ISSM-MFD37-00-DCLENG000'     'CGCON-MDCL37-xxxxx'
    'CE06ISSM-MFD35-00-DCLENG000'     'CGCON-MDCL36-xxxxx'
    'CE06ISSM-SBD17-06-CTDBPC000'     'CGINS-CTDBPC-xxxxx'
    'CE06ISSM-SBD17-06-FLORTD000'     'CGINS-FLORTD-xxxxx'
    'CE06ISSM-SBD17-01-MOPAK0000'     'CGINS-MOPAK0-xxxxx'
    'CE06ISSM-SBD17-04-VELPTA000'     'CGINS-VELPTA-xxxxx'
    'CE06ISSM-RID16-03-CTDBPC000'     'CGINS-CTDBPC-xxxxx'
    'CE06ISSM-RID16-03-DOSTAD000'     'CGINS-DOSTAD-xxxxx'
    'CE06ISSM-RID16-02-FLORTD000'     'CGINS-FLORTD-xxxxx'
    'CE06ISSM-RID16-07-NUTNRB000'     'CGINS-NUTNRB-xxxxx'
    'CE06ISSM-RID16-01-OPTAAD000'     'CGINS-OPTAAD-xxxxx'
    'CE06ISSM-RID16-05-PCO2WB000'     'CGINS-PCO2WB-xxxxx'
    'CE06ISSM-RID16-06-PHSEND000'     'CGINS-PHSEND-xxxxx'
    'CE06ISSM-RID16-08-SPKIRB000'     'CGINS-SPKIRB-xxxxx'
    'CE06ISSM-RID16-04-VELPTA000'     'CGINS-VELPTA-xxxxx'
    'CE06ISSM-MFD35-04-ADCPTM000'     'CGINS-ADCPTM-xxxxx'
    'CE06ISSM-MFD35-04-WAVSSM000'     'CGINS-WAVSSM-xxxxx'
    'CE06ISSM-MFD37-06-CAMDSA000'     'CGINS-CAMDSA-xxxxx'
    'CE06ISSM-MFD37-03-CTDBPC000'     'CGINS-CTDBPC-xxxxx'
    'CE06ISSM-MFD37-03-DOSTAD000'     'CGINS-DOSTAD-xxxxx'
    'CE06ISSM-MFD37-01-OPTAAD000'     'CGINS-OPTAAD-xxxxx'
    'CE06ISSM-MFD35-05-PCO2WB000'     'CGINS-PCO2WB-xxxxx'
    'CE06ISSM-MFD35-06-PHSEND000'     'CGINS-PHSEND-xxxxx'
    'CE06ISSM-MFD35-02-PRESFA000'     'CGINS-PRESFA-xxxxx'
    'CE06ISSM-MFD35-01-VEL3DD000'     'CGINS-VEL3DD-xxxxx'
    'CE06ISSM-MFD37-07-ZPLSCC000'     'CGINS-ZPLSCC-xxxxx'   };

% use the constituent cell arrays in the rest of the program 
RefDes     = refdes_sensor(:,1);
sensor_uid = refdes_sensor(:,2);
clear refdes_sensor        % make sure there is only one source

% the platform control designations following are ordered to
% correspond with the 1st 6 RefDes entries. This 1:1 ordering is
% required to make the correct platcon serial number assignments.
PlatCon = {'CPM1' 'DCL17' 'DCL16' ...
           'CPM3' 'DCL37' 'DCL36' };
       
% reorder rows to group platform's platcon with platform's instruments
reorder_rows_on_output = [1:2 7:10 3 11:19 4:6 20:29];

%********  READ IN AND COLUMN SORT DEPLOY_CSV FILE **********************
fid = fopen(deploy_filename);
D = textscan(fid,'%s','whitespace','','delimiter','\n');
fclose(fid);
D = D{1};  % unwrap
% make sure that there are the expected number of columns.
n_commas = length(strfind(D{1}, ','));  % # commas in header row
if ncol ~= n_commas+1
    error(['Unexpected number of columns in ' deploy_filename]);
end

clear D  % always clear cell array variable names!
fid = fopen(deploy_filename);
% use CollectOutput to 'collapse' the indexing of the input data;
% after 'unwrapping', it will be straightforward to cat the
% latest deployment's data to the data about to be read in below.
D = textscan(fid, repmat('%s', 1, ncol), 'delimiter', ',', ...
    'CollectOutput', 1);
fclose(fid);
% 'unwrap' by getting rid of the outer cell array layer
D = D{1};
% need a default column ordering in order to make row additions,
% that is, to add a deployment; CI continually changes the column
% ordering, so, sort them and use the resultant ordering as default.
header = D(1, :);
[~, idx_sort]  = sort(header);
% put the 2 newest columns at the end, out of the way
idx_electrical = find(contains(header, 'electrical'));
idx_assembly   = find(contains(header, 'assembly'));
last2columns   = [idx_electrical idx_assembly];
idx_sort       = setdiff(idx_sort, last2columns, 'stable');
idx_sort       = [idx_sort last2columns];

% now re-orient the data columns
D = D(:, idx_sort);

%*****************  READ IN PREPPED CONFIG.XLSX FILE ********************
% all of the 3rd column excelfile cell entries must be formatted 
% as text, not as numbers, using the procedure outlined in the
% documentation at program top. the 4th column must contain
% platcon bottle assignments (CPM, DCL)
%
% overdimension the number of rows so that this statement will work
% for all surface moorings; does not decrease performance, while
% using 'A:D' does.
[~, T, ~] = xlsread(config_filename, 'A1:D500');
T = strtrim(T);  % get rid of leading and trailing spaces

%************************************************************************
%
% fill in each column of cell array C with the current deployment's
% data, to be appended to the (column-sorted) data read in from the
% deploy_csv file.
nrow = length(RefDes);   % number of rows for current deployment's entries
C(1:nrow, 1:ncol) = {''};  % pre-allocate with empty quotes
%
%************************************************************************

%****** Fill in column #01: CUID_Deploy **************************
% Postpone till after the determination of which instruments,
% if any, were not deployed in sensor.uid column: this is 
% signified in CI by prepending '#' to the CUID_Deploy value.

%****** Fill in column #02: CUID_Recover *************************
% Postpone till after the determination of depNum

%****** Fill in column #03: Reference Designator *****************
C(:, 3) = RefDes;

%****** Fill in column #04: deployedBy  **************************
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #05: deploymentNumber *********************
str = T{idx_MooringSN, 3};
tab = char(9);
str = strrep(str, '-', tab);
str = strrep(str, '_', tab);
depNum = sscanf(str, '%*s%u');
C(:, 5) = repmat({num2str(depNum)}, nrow, 1);

%****** Fill in column #06: deployment_depth *********************
% Postpone till after the determination of water depth,
% because the mfn deployment depth values are assigned 
% to be 2 meters less than the water depth.

%****** Fill in column #07: lat **********************************
try
    val = str2double(T{idx_Lat, 3});
    C(:, 7) = repmat({num2str(val,'%9.5f')}, nrow, 1);
    disp([' latitude as written out:    ' C{1, 7}]);
catch
    disp('********************************');
    disp('WARNING: UNKNOWN LATITUDE FORMAT');
    disp('********************************');
end

%****** Fill in column #08: lon **********************************
try
    val = str2double(T{idx_Lon, 3});
    C(:, 8) = repmat({num2str(val,'%10.5f')}, nrow, 1);
    disp(['longitude as written out:  ' C{1, 8}]);
catch
    disp('********************************');
    disp('WARNING: UNKNOWN LONGITUDE FORMAT');
    disp('********************************');
end
%........................
%........................
if val>0
    error('POSITIVE DECIMAL DEGREE LONGITUDE SUBMITTED FOR ENDURANCE!');
end
%........................
%........................

%****** Fill in column #09: mooring.uid  *************************
% template: 'CGMCE-09OSSM-00004' for deployment 4.
% mooring id contains the deployment number already parsed (column 05);
% however, make this section stand-alone, and, also, don't hardcode
% the surface mooring id, so that this section will be generalized to
% work for the other surface moorings.
str = upper(T{idx_MooringSN, 3});  % CE06ISSM-00004, for example
mooring_uid = ['CGM' str(1:2) '-' str(3:end)];
C(:, 9) = repmat({mooring_uid}, nrow, 1);

%****** Fill in column #10: node.uid *****************************
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #11: notes ********************************
% Postpone till after it is determined whether some 
% instruments were not deployed; in these cases, this
% will be noted in this column.

%****** Fill in column #12: orbit ********************************
C(:, 12) = {num2str(orbit)};

%****** Fill in column #13: recoveredBy **************************
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #14: sensor.uid ***************************
% construct a dictionary with the keys being the instruments 
% deployed and the values the serial numbers. This method was
% chosen so that even if the ordering of reference designators
% and/or config.xlsx entries are changed, the algorithm will
% still work.
%
% delete trailing ' S/N' in column 1 to make container keys
Keys = strrep(T(:,1), ' S/N', '');
% process serial numbers in column 3 to make container values
Values = T(:,3);
% deal with instruments not deployed
notDeployed = {'None' 'N/A' 'not deployed'};
tf_notDeployed = contains(Values, notDeployed, 'IgnoreCase', true);
Values(tf_notDeployed) = {''};
% take care of some common fixable 'non-standard' s/n entries:
Values = strrep(Values, '-', '0');    % this will fix SBE, CAMDS, NTR
Values = strcat('00000', Values);     % this will fix all 1-4 digit S/N
Values = cellfun(@(x) x(end-4:end), Values, 'UniformOutput', false);
% instruments not deployed will have a S/N of 00000
%
% find instrumentation rows and key keys to platform
idx_Instruments = find(strncmpi(Keys, 'Instruments', 11));
idx_NSIF        = find(strncmpi(Keys, 'NSIF', 4));
idx_MFN         = find(strncmpi(Keys, 'MFN', 3));  % two of these
idx_MFN         = idx_MFN(2);  % we want the second one
idx_end         = length(Keys);
% buoy instrumentation rows
idx_buoy = idx_Instruments+1:idx_NSIF-1;
% prepend 'SB' to these keys to denote buoy instruments
Keys(idx_buoy) = strcat('SB', Keys(idx_buoy));
% riser (nsif) instrumentation rows
idx_riser = idx_NSIF+1:idx_MFN-1;
% prepend 'RI' to these keys to denote riser instruments
Keys(idx_riser) = strcat('RI', Keys(idx_riser));
% mfn instrumentation rows
idx_mfn = idx_MFN+1:idx_end;
% prepend 'MF' to these keys to denote mfn instruments
Keys(idx_mfn) = strcat('MF', Keys(idx_mfn));
%
% make a dictionary (container) containing the instrument
% designations and their serial numbers.
idx = idx_buoy(1):idx_end;
Dict_SerNum = containers.Map(Keys(idx)', Values(idx)');
%
% construct instrument keys from reference designators.
idx_rd = [10 11 19:23];
Ikeys = cellfun(@(x) x(idx_rd), RefDes, 'UniformOutput', false);
%
% Read in platcon serial numbers, at the start of the RefDes listing.
% the platcon bottle designations (PlatCon) must be in the 4th column;
% their serial numbers were in 3rd column, are now in Values
n_platcon = length(PlatCon);  % number of platcon reference designators
for ii=1:n_platcon
    idx = find(~cellfun(@isempty, strfind(T(:, 4), PlatCon{ii})));
    sensor_uid{ii} = strrep(sensor_uid{ii}, 'xxxxx', Values{idx});
end
%
% Instrument sensor.uids:
% fill in %5.5u serial numbers into last sensor_uid field

for ii = n_platcon+1:length(RefDes)
    try
        sn_str = Dict_SerNum(Ikeys{ii});
    catch ME
        disp(' ')
        disp(ME)
        disp(['Missing key: ' Ikeys{ii}]);        
        error('Check instructions at code top: has WAVSS row been inserted into config.xlsx?')
    end
    sensor_uid{ii} = strrep(sensor_uid{ii}, 'xxxxx', sn_str);
end
%
% tag fields where assets were not deployed.
% (a) replace entry in sensor_uid with {''}
% (b) flag by prepending '#' in the cruiseID column (later section)
% (c) flad by adding notation in notes section (later section)
tf_notDeployed = contains(sensor_uid, '00000');
sensor_uid(tf_notDeployed) = {''};
C(:, 14) = sensor_uid;

%****** Fill in column #15: startDateTime ************************
% format: 2015-04-09T17:30:00
%
date = T{idx_LaunchDate, 3};
disp(['date as read in:      ' date]);
% sometimes the date appears in excel as yyyy-mm-dd, but is read
% in as mm/dd/yyyy.
if contains(date, '/')
    date = [date(7:10) '-' date(1:2) '-' date(4:5)];
end
time = T{idx_LaunchTime, 3};
disp(['time as read in:      ' time]);
% time entries might be either hh:mm or hh:mm:ss
if length(time)==5, time = [time ':00']; end
startDateTime = [date 'T' time];
disp(['datetime as written out:  ' startDateTime]);
C(:, 15) = repmat({startDateTime}, nrow, 1);

%****** Fill in column #16: stopDateTime *************************
% FOR CURRENT DEPLOYMENT:
% no action needed: this column pre-allocated with '' entries.
% FOR PREVIOUS DEPLOYMENT:
% if there is an entry in cell D5 of the prepped config.xlsx file,
% then it will be written out verbatim as the previous deployment's
% stopDateTime.
stopDateTime = T{5,4};  % excel cell location row 5 column D
if ~isempty(stopDateTime)
    % find rows of cell array D corresponding to previous deployment.
    %
    % the current deployment number is contained in the variable depNum
    % as a numeric unsigned integer (not a string). To make sure there
    % won't ever be a problem matching deploy.csv entries in the 
    % deploymentNumber column like '00004', convert the entries in this
    % column cell array D to numeric before looking for row matches. 
    tf_row = str2double(D(:, 5)) == depNum - 1;
    D(tf_row, 16) = {stopDateTime};
end

%****** Fill in column #17: versionNumber ************************
% use the versionNumber in the previous deployment (in cellArray D)
verNum = D(end, 17);
C(:, 17) = repmat(verNum, nrow, 1);

%****** Fill in column #18: water_depth **************************
%
% NOTE: as of the time this code was written, CI *does* include
% water depth and deployment depth entries for rows for which
% an instrument was not deployed.
%
% this handles '542', '542m', and '542 m' formats; write out just '542'
str = T{idx_WaterDepth, 3};
str = strrep(str, ' ', 'z');
tf_letter = isletter(str);    % find letters
str(tf_letter) = [];          % delete letters
C(:, 18) = repmat({str}, nrow, 1); 
waterDepth = str2num(str);    % waterDepth [m] for mfn deployment depth

%****** Fill in column #20: assembly_template_revision ***********
C(:, 20) = {assembly_template_revision_entry};

%*****************************************************************
% 2nd pass: process columns 01, 02, 06, and 11 which required 
%           variables which hadn't been calculated yet.
%*****************************************************************

%****** Fill in column #01: CUID_Deploy **************************
% Cruise ID (needs tf_notDeployed variable)
cuid = repmat(T(idx_CruiseID, 3), nrow, 1);
% prepend '#' for rows associated with no sensor deployed
cuid(tf_notDeployed) = cellfun(@(x) ['#' x], cuid(tf_notDeployed), ...
    'UniformOutput', false);
C(:, 1) = cuid;

%****** Fill in column #02: CUID_Recover *************************
% Just as for the CUID_Deploy entries, if an instrument was not
% deployed, then the first character of the CUID_Recover entry
% must be '#'.
% FOR CURRENT DEPLOYMENT:
% no action needed: this column pre-allocated with '' entries.
% FOR PREVIOUS DEPLOYMENT:
% if there is an entry in cell D11 of the prepped config.xlsx file,
% then it will be written out verbatim.
CUID_Recover = T{11,4};  % excel cell location row 11 column D
if ~isempty(CUID_Recover)
    % find rows of cell array D corresponding to previous deployment.
    tf_row   =   str2double(D(:, 5)) == depNum - 1;
    D(tf_row, 2) = {CUID_Recover};
    % overwrite with a prepended '#' where instruments were not deployed:
    % find instances where CUID_Deploy values contain '#'.
    tf_hashtag = contains(D(:, 1), '#');
    D(tf_row & tf_hashtag, 2) = {['#' CUID_Recover]};
end

%****** Fill in column #06: deployment_depth *********************
%
% NOTE: as of the time this code was written, CI *does* include
% water depth and deployment depth entries for rows for which
% an instrument was not deployed.
%
depMFN = num2str(waterDepth);  % mfn deployment depth
% shotgun buoy (well-instruments), nsif, and mfn deployment depths.
% restrict matches to just the platform code characters, just in
% case the 'SB', 'RI', and 'MF' patterns occur in Instrument-Series
% designations.
platformCode = cellfun(@(x) x(10:11), RefDes, 'UniformOutput', false);
C(strcmpi(platformCode, 'SB'), 6) = {depBuoyWell};
C(strcmpi(platformCode, 'RI'), 6) = {depNSIF};
C(strcmpi(platformCode, 'MF'), 6) = {depMFN};
% special cases
% CTDBP, FLORT, and VELPT instruments are on multiple platforms, so
% construct an identifier which includes the platform and instrument:
pc_instr = cellfun(@(x) x([10:11 19:23]), RefDes, 'UniformOutput', false);
C(strcmpi(pc_instr, 'SBCTDBP'), 6) = {depBuoyInshoreCTDBP};
C(strcmpi(pc_instr, 'SBFLORT'), 6) = {depBuoyInshoreFLORT};
C(strcmpi(pc_instr, 'SBVELPT'), 6) = {depBuoyInshoreVELPT};

%****** Fill in column #11: notes ********************************
% needs tf_notDeployed variable
% annotate some of the sensor deployment depths if desired
%
% note which sensors were not deployed
C(tf_notDeployed, 11) = {'Not Deployed'};

%****** VertCat new deployment to earlier ones, write out ************
%C = C(reorder_rows_on_output, :);    % reorder new deployment's rows
Out = [D; C];                        % vertcat
Out = Out(:, reorder_columns_on_output);
fmt = repmat('%s,', 1, ncol);
fmt = [fmt(1:end-1) '\n'];           % drop last comma, add linefeed
if strcmpi(mode, 'update')
    fid = fopen(deploy_filename, 'w');
else
    fid = fopen('R:\deploy.csv', 'w');    % test, write to RAMdrive
end
for ii = 1:length(Out)
    fprintf(fid, fmt, Out{ii, :});
end
fclose(fid);

% parse instrument and platcon sensor_uids and see if any are new
%
% if any instrument uids are missing their uids will be output to screen
% and the entries to the bulkSensor file will need to be done by hand.
disp(' ');
disp('If ADCPTM is present, it should be listed twice (ADCPT + WAVSS).')
find_missing_bulkSensor_entries(sensor_uid);
% if any platcon uids are missing their uids will be output to screen
% and the sub_append function will enter them into the bulkEng file.
missing_uid = find_missing_bulkEng_entries(sensor_uid);
sub_append_platconUID_to_engAssetRecord(missing_uid, mode)

disp(' ')
disp('----------------------------------------------');
disp('----------------------------------------------');
disp('Run append_mooringUID_to_platformAssetRecord.m');
disp('----------------------------------------------');
disp('----------------------------------------------');
disp(' ');

commandwindow
