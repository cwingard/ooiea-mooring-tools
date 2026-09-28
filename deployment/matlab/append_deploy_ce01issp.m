% append_deploy_CSPP.m
% desiderio 29-nov-2017
% desiderio 30-may-2019 modifications to make compatible with new 
%                       (Ian Black's) config.xlsx sheet format.
% desiderio 15-feb-2020
%           more modifications needed to config.xlsx sheet because
%           of further modifications by Ian: the entries are *links*
%           to cells in other xlsx sheets; when these columns are 
%           'converted' to text, the links (which are text) are not
%           changed to a text representation of the serial number,
%           for example.
% SOLUTION:
%          make a new sheet, and copy BY VALUE the first 2 columns
%          over to it. Then proceed as normal, this should work.
% desiderio 19-aug-2020
%          more mods over the months, continually changing.
%          the latest: REPLACE Column B with a copy of it by VALUE,
%          to get rid of links and formulas; then, the now established
%          normal procedure, inserting a copy of Column B and then
%          manipulating Column C.
% desiderio 01-apr-2021  2 columns have been added to the deploy.csv files
%                        for populating 'RoundAbout'. see deploy.csv columns
%                        section of the code (~ line 102) for documentation.
%                        Improved parsing of instruments not deployed.
% desiderio 20-sep-2023  (a) changed expected lat lon inputs to
%                        character vector, 5 decimal places
%                        (b) xlsread: specified sheetname 'Configuration' 
% wingard 20-mar-2024    removed desiderio idiosyncracies and adapted to local
%                        directory structure
%
% Appends CSPP asset management deployment info to
% an OOI CI Deploy.csv file downloaded from GitHub: 
%     https://github.com/oceanobservatories/asset-management/tree/master/deployment
%
% Inputs: (hardcoded at program top)
%          prepped config.xlsx file (see config_filename variable)
%
% Output: determined from the config.xlsx filename; one of the following
%         CE01ISSP_Deploy.csv
%         CE02SHSP_Deploy.csv
%         CE06ISSP_Deploy.csv
%         CE07SHSP_Deploy.csv
%
% If the previous deployment's stopDateTime recovery information, which
% should be formatted as yyyy-MM-ddThh:mm:ss, is located in cell D8 of
% the prepped config file, then it will be written out verbatim into
% the appropriate rows and column of the output deploy.csv file.

% The config.xlsx file must be prepared as follows. Note that lats and lons
% are expected to be character vectors in decimal degrees.
%
% (1) UNMERGE ALL CELLS:
%     (a) Select entire sheet
%     (b) Click on Home, then Format, then Format Cells at bottom
%     (c) Click on Alignment, double click on Merge cells, OK
% (2) Select Column B, Copy, and PASTE AS VALUES copied cells ON TOP OF column B
% (3) Select Column B, Copy, and INSERT COPIED CELLS at column B.
% (4) Select Column D, right click, Insert to insert column.  (!!!) else recovery won't work
% (5) CHANGE COLUMN C TO TEXT BY:
%     Highlight the 3rd column
%     Click on Data tab
%     Select "Text to Columns"
%     Select fixed width, click on Next;
%     If there is a line break, delete it by double clicking; Next;
%     Select "Text" in Column data format, 
%     Finish.
% (6) Cell C8: insert a 'T' between launch date time, if needed
%              add ':00' as seconds for the dateTime  =====>>>> MAY NEED TO
%              BE MANUAL EDIT
% (7) RENAME VELPT-J AQS TO VVELPT-J AQS in column A to distinguish it from Board
%
%                            NOT NECESSARY (for now)
% (X) Convert C9 and C10 values for lat and lon into text 000.00000: 
%     (a) Type or (copy/paste!) =ROUND(B9, 5) into D9 
%     (b) Fill:                 =ROUND(B10, 5) into D10
%     (c) Copy\paste D9:D10 to C9:C10 as 'Values'  
%     (d) Prepend ' in each cell to turn into text
%
% Besides standardizing the excel cell formats for import, the original 
% S/N entries are preserved in the 2nd column while modifications
% can be made in the 3rd column to make the entered serial numbers
% conform to the OOI conventions. This program reads in the entries
% in this 3rd column to create sensor.uids for export.
 
% Config.xlsx File Preparation Checklist
% (0) Optional: enter previous deployment's stopDateTime in cell D8,
%               after the insert-copy operation has been done.
% (1) Make sure MOORING S/N (rows 3 and 4) are correct (especially deployment #)
% (2) Cruise (row 5 entry) is named as archived in CruiseInformation.csv
% (3) Anchor Launch DateTime (row 8) format is YYYY-MM-DDThh:mm:ss (GMT)
% (4a)  Format Lat (row 9) as decimal degree character vector, 5 decimal places
% (4b)  Format Lon (row 10) as decimal degree character vector, 5 decimal places
%. .. LONGITUDES MUST BE NEGATIVE
% (5) Water Depth (row 11) is entered
% (6) Entries for instruments that are not deployed should be either
%     'N/A', 'None', or 'Not Deployed' (case insensitive).
% (7) Adjust non-OOI standard serial numbers:
%        (Do NOT need to alter SBE CTD if its serial number is prefixed
%         with 49-).
%        (Do not need to deal with VELPT entry if taken care of as
%         detailed in the config.xlsx preparation section).
%     CHANGE S/N SERIES DESIGNATION(S) FROM J TO D IF APPROPRIATE;
%     This code will make the appropriate change in the sensor.uid.
%
% (8) SAVE CONFIG.XLSX CHANGES.
%
% (9) Don't forget to change paths and filenames in this code.
mode = 'update';  % write to local master
ncol = 20;  % number of columns in deploy_filename
deploy_path = 'C:\Users\chris\code\asset-management\deployment\';
deploy_filename = 'CE01ISSP_Deploy.csv';
deploy_filename = [deploy_path deploy_filename];
config_path = 'C:\Users\chris\OneDrive - Oregon State University\OOI\buoys\Deployments\scripts\platforms\deploy\';

% change these for each new platform/deployment
config_name = 'CE01ISSP-00024.xlsx';
config_filename = [config_path config_name];

% useful variables for later
mooring_name = config_name(1:8);
depNum = str2double(config_name(10:14));  % numeric variable, not char
mooring_location = config_name(5:8);      % either 'ISSM' or 'SHSM'

disp(' ');
disp(['Mooring_uid: ' config_name(1:14)]);

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
%   2   'CUID_Recover'             empty
%   3   'Reference Designator'     variable
%   4   'deployedBy'               empty
%   5   'deploymentNumber'         single-valued
%   6   'deployment_depth'         variable (dependent on platform)
%   7   'lat'                      single-valued
%   8   'lon'                      single-valued
%   9   'mooring.uid'              single-valued            
%  10   'node.uid'                 empty for non-mobile moorings
%  11   'notes'                    optional
%  12   'orbit'                    empty
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
% new config.xlsx format (May 2019)
idx_CruiseID       =  5;
idx_LaunchDateTime =  8;
idx_Lat            =  9;
idx_Lon            = 10;
idx_WaterDepth     = 11;

% mooring_name and depNum (deployment number as a numeric variable)
% were parsed earlier from the config.xlsx filename.

% these columns contain reference designator and sensor.uid values.
% to emphasize the 1:1 correspondence, and for proofreading,
% they are entered as a 2-column cell array. Make future changes
% on these master arrays.
%
% for the CSPPs, the reference designator lineups are different for
% inshore (ISSP) versus shelf (SHSP) sites; the instrument lineups 
% are however identical. set up lineups according to mooring location.
if strcmpi(mooring_location, 'ISSP')
    refdes_sensor = {
    'MOORNAME-SP001-00-SPPENG000'  'CGCON-CSPPCE-xxxxx'
    'MOORNAME-SP001-09-CTDPFJ000'  'CGINS-CTDPF?-xxxxx'
    'MOORNAME-SP001-02-DOSTAJ000'  'CGINS-DOSTA?-xxxxx'
    'MOORNAME-SP001-08-FLORTJ000'  'CGINS-FLORT?-xxxxx'
    'MOORNAME-SP001-06-NUTNRJ000'  'CGINS-NUTNR?-xxxxx'
    'MOORNAME-SP001-04-OPTAAJ000'  'CGINS-OPTAA?-xxxxx'
    'MOORNAME-SP001-10-PARADJ000'  'CGINS-PARAD?-xxxxx'
    'MOORNAME-SP001-07-SPKIRJ000'  'CGINS-SPKIR?-xxxxx'
    'MOORNAME-SP001-05-VELPTJ000'  'CGINS-VELPT?-xxxxx'  };
elseif strcmpi(mooring_location, 'SHSP')
    refdes_sensor = {
    'MOORNAME-SP001-00-SPPENG000'  'CGCON-CSPPCE-xxxxx'
    'MOORNAME-SP001-08-CTDPFJ000'  'CGINS-CTDPF?-xxxxx'
    'MOORNAME-SP001-01-DOSTAJ000'  'CGINS-DOSTA?-xxxxx'
    'MOORNAME-SP001-07-FLORTJ000'  'CGINS-FLORT?-xxxxx'
    'MOORNAME-SP001-05-NUTNRJ000'  'CGINS-NUTNR?-xxxxx'
    'MOORNAME-SP001-04-OPTAAJ000'  'CGINS-OPTAA?-xxxxx'
    'MOORNAME-SP001-09-PARADJ000'  'CGINS-PARAD?-xxxxx'
    'MOORNAME-SP001-06-SPKIRJ000'  'CGINS-SPKIR?-xxxxx'
    'MOORNAME-SP001-02-VELPTJ000'  'CGINS-VELPT?-xxxxx'  };
else
    error('Could not parse CSPP mooring type (must be ISSP or SHSP).');
end
% insert the correct mooring name into ref_des.
refdes_sensor = strrep(refdes_sensor, 'MOORNAME', mooring_name);
% use the constituent cell arrays in the rest of the program
RefDes     = refdes_sensor(:,1);
sensor_uid = refdes_sensor(:,2);
clear refdes_sensor        % make sure there is only one source
       
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
% documentation at program top.
%
% overdimension the number of rows so that this statement will work
% for all cspp moorings; does not decrease performance, while
% using 'A:D' does.
[~, T, ~] = xlsread(config_filename, 'Configuration', 'A1:D80');
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
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #03: Reference Designator *****************
C(:, 3) = RefDes;

%****** Fill in column #04: deployedBy  **************************
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #05: deploymentNumber *********************
C(:, 5) = repmat({num2str(depNum)}, nrow, 1);

%****** Fill in column #06: deployment_depth *********************
% Postpone till after the determination of water depth.

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
% template: 'CGMCE-01ISSP-00004' for deployment 4.
% mooring id contains the deployment number already parsed (depNum)
mooring_uid = ['CGM' mooring_name(1:2) '-' mooring_name(3:end) '-' ...
    num2str(depNum, '%5.5u')];
C(:, 9) = repmat({mooring_uid}, nrow, 1);

%****** Fill in column #10: node.uid *****************************
% Postpone till after the profiler sensor.uid is parsed.

%****** Fill in column #11: notes ********************************
% Postpone till after it is determined whether some 
% instruments were not deployed; in these cases, this
% will be noted in this column.

%****** Fill in column #12: orbit ********************************
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #13: recoveredBy **************************
% no action needed: this column pre-allocated with '' entries.

%****** Fill in column #14: sensor.uid ***************************
% construct a dictionary with the keys being the instruments 
% deployed and the values the serial numbers. 
%
% Keys: 
% construct from the 1st 5 characters of the entries in the 1st column.
% First make sure that each row has at least 5 characters to avoid an
% "Index exceeds matrix dimensions." error.
Keys = strcat(T(:,1), '00000000');
% make sure that the row entry "SPKIR bioshutter" does not become 
% a "SPKIR" key
Keys = strrep(Keys, 'SPKIR bioshutter', 'OCR-507 bioshutter');
% Values for instrument series:
% the instrument series designation as listed in the 1st column of the
% config file will be used in the instruments' uid;
% do this operation before final coding for Keys variable
Values_Series = cellfun(@(x) x(7), Keys, 'UniformOutput', false);
Keys = cellfun(@(x) x(1:5), Keys, 'UniformOutput', false);
% dictionary for instrument series look-up:
% the container arguments must be row vectors
Dict_Series = containers.Map(Keys', Values_Series');
% Values_SN:
% process instrument serial numbers in column 3 to make OOI SN values
Values_SN = T(:,3);
% deal with instruments not deployed
notDeployed = {'None' 'N/A' 'not deployed'};
tf_notDeployed = contains(Values_SN, notDeployed, 'IgnoreCase', true);
Values_SN(tf_notDeployed) = {''};
% take care of fixable 'non-standard' s/n entries:
Values_SN = strrep(Values_SN, '49-', '0');    % this will fix SBE CTD
Values_SN = strrep(Values_SN, 'WLP-', '00');  % this will fix cspp S/N
Values_SN = strcat('00000', Values_SN);  % this will fix all 1-4 digit S/N
Values_SN = cellfun(@(x) x(end-4:end), Values_SN, 'UniformOutput', false);
% instruments not deployed will have a S/N of 00000
% the container arguments must be row vectors
Dict_SerNum = containers.Map(Keys', Values_SN');
%
% construct instrument keys from the refdes elements
Ikeys = cellfun(@(x) x(end-8:end-4), RefDes, 'UniformOutput', false);
% the Ikey for the cspp uid is in the config sheet as:
Ikeys{1} = 'Profi';
%
% sensor.uids:
% fill in %5.5u serial numbers into last sensor_uid field
for ii = 1:length(RefDes)
    sn_str = Dict_SerNum(Ikeys{ii});
    sensor_uid{ii} = strrep(sensor_uid{ii}, 'xxxxx', sn_str);
    series = Dict_Series(Ikeys{ii});
    sensor_uid{ii} = strrep(sensor_uid{ii}, '?', series);
end
%
% tag fields where assets were not deployed.
% (a) replace entry in sensor_uid with {''}
% (b) flag by prepending '#' in the cruiseID column (later section)
% (c) flag by adding notation in notes section (later section)
tf_notDeployed = contains(sensor_uid, '00000');
sensor_uid(tf_notDeployed) = {''};
C(:, 14) = sensor_uid;

%****** Fill in column #15: startDateTime ************************
% format: 2015-04-09T17:30:00
%
startDateTime = T{idx_LaunchDateTime, 3};
disp(['startdatetime as read in and written out:  ' startDateTime]);
C(:, 15) = repmat({startDateTime}, nrow, 1);

%****** Fill in column #16: stopDateTime *************************
% FOR CURRENT DEPLOYMENT:
% no action needed: this column pre-allocated with '' entries.
% FOR PREVIOUS DEPLOYMENT:
% if there is an entry in cell D8 of the prepped config.xlsx file,
% then it will be written out verbatim as the previous deployment's
%
% stopDateTime.
% 2019-05-09 Ian changed the config file and removed text which
%            guaranteed that a 4th column existed. So, this code
%            will not work if there is not a recovery entry.
%            For now, change by appending a blank column.                  
T(:, end+1) = T(:, end);
T(:, end) = {''};
stopDateTime = T{8,4};  % excel cell location row 8 column D
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
waterDepth = str;    % waterDepth [m]

%*****************************************************************
% 2nd pass: process columns 01, 06, 10, and 11 which required 
%           variables which hadn't been calculated yet.
%*****************************************************************

%****** Fill in column #01: CUID_Deploy **************************
% Cruise ID (needs tf_notDeployed variable)
cuid = repmat(T(idx_CruiseID, 3), nrow, 1);
% prepend '#' for rows associated with no sensor deployed
cuid(tf_notDeployed) = cellfun(@(x) ['#' x], cuid(tf_notDeployed), ...
    'UniformOutput', false);
C(:, 1) = cuid;

%****** Fill in column #06: deployment_depth *********************
%
% NOTE: as of the time this code was written, CI *does* include
% water depth and deployment depth entries for rows for which
% an instrument was not deployed.
%
% use the water depth (bottom depth).
for ii = 1:nrow
    C(ii, 6) = {waterDepth};
end

%****** Fill in column #10: node.uid *****************************
% if   the profiler sensor.uid is: CGCON-CSSPCE-XXXXX, 
% then the profiler   node.uid is: CGVEH-CSSPCE-XXXXX.
%
% the profiler uid is in the 1st row, column 14, so:
node.uid = strrep(C(1, 14), 'CON', 'VEH');
% node.uid entries are written out for all rows.
C(1:length(RefDes), 10) = (node.uid);

%****** Fill in column #11: notes ********************************
% needs tf_notDeployed variable
% annotate some of the sensor deployment depths
%
% note which sensors were not deployed
C(tf_notDeployed, 11) = {'Not Deployed'};

%****** VertCat new deployment to earlier ones, write out ************
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

% parse instrument and platcon sensor_uids and see if any are new.
% missing uids will be output to the screen and will need to be added
% by hand into the appropriate bulkAssetRecord files.
find_missing_bulkSensor_entries(sensor_uid);
find_missing_bulkEng_entries(sensor_uid);

disp('-----------------------------------------------------------');
fprintf('Don''t forget to UPDATE MOORING.UID; track by using\n');
fprintf('append_mooringUID_to_platformAssetRecord.m\n');
fprintf('\nIs an entry in cruise.csv also required?\n');
disp('-----------------------------------------------------------');
disp(' ');

commandwindow
