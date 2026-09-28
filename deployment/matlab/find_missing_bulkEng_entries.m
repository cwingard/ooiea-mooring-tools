function Missing_uid = find_missing_bulkEng_entries(Sensor_uid)
%.. desiderio 30-nov-2017
%.. desiderio 07-feb-2019: UPDATED to reflect re-organization of GitHub 
%..                        Asset Management: all CGCON equipment will be
%..                        moved from sensor_bulk_load to eng_bulk_load.
%
%   Because the sensor and eng (controller) records have been split into
%   different files, this subroutine will deal only with equipment
%   with a uid beginning with 'CGCON' (controllers). Equipment with a uid
%   starting with 'CGINS' will be handled by a different routine.
%
%************************************************************************
%.. Inputs: 
%..        (a)  a cell array of sensor.uids read in from a deploy.csv file
%..        (b)  path to eng_bulk_load-AssetRecord.csv (hardcoded)
%
%.. Outputs:
%..        (a) cell array of uid names that are missing from the asset record.
%..        (b) Outputs these names to the screen.
%..        (c) IF A PROFILER CONTROLLER UID IS MISSING, THEN THIS CODE WILL
%..            CONSTRUCT THE CORRESPONDING NODE UID AND WRITE IT TO THE SCREEN
%..            because presumably the node_bulk_load record will also need
%..            to be updated with the new node uid.
%
%.. Asset Management files are not altered by this routine. 
%************************************************************************
%.. This routine is called by:
%.. .. append_deploy_ce01issm.m
%.. .. append_deploy_ce02shsm.m
%.. .. append_deploy_ce04ossm.m
%.. .. append_deploy_ce06issm.m
%.. .. append_deploy_ce07shsm.m
%.. .. append_deploy_ce09ossm.m
%
%.. .. append_deploy_ce09ospm.m
%.. .. append_deploy_CSPP.m
%************************************************************************

%.. if an instrument was not deployed, the sensor_uid will come in as an
%.. empty element of a cell {''}. Delete if this occurs.
Sensor_uid(cellfun('isempty', Sensor_uid)) = [];

%.. discard CGINS uids, which will be checked in a separate routine
tf_CGINS = contains(Sensor_uid, 'CGINS');
Sensor_uid(tf_CGINS) = [];
disp(' ');
disp('Checking bulkEng Asset record for these Sensor_UIDs:'); 
disp(Sensor_uid(:));
disp(' ');

ncolAR = 14;  % expected number of columns in assetRecord_filename
assetRecord_path = 'C:\Users\chris\code\asset-management\bulk\';
assetRecord_filename = 'eng_bulk_load-AssetRecord.csv';
assetRecord_filename = [assetRecord_path assetRecord_filename];

%.. when reading in bulk Asset Records, the header row read in will be
%.. checked against the expected order and an error thrown if there is
%.. any disagreement:
header_expected = ['ASSET_UID,'                                   ...
                   'LEGACY_ASSET_UID,'                            ...
                   'TYPE,'                                        ...
                   'Mobile,'                                      ...
                   'DESCRIPTION OF EQUIPMENT,'                    ...
                   'MIO_Inventory_Description,'                   ...
                   'Manufacturer,'                                ...
                   'Model,'                                       ...
                   'Manufacturer''s Serial No./Other Identifier,' ...
                   'Firmware Version,'                            ...
                   'ACQUISITION DATE,'                            ...
                   'ORIGINAL COST,'                               ...
                   'comments,'                                    ...
                   'MIO'];

%********  READ IN ENG ASSET RECORD FILE (Feb 2019 and later) **********
%**
%** NOTE: There may be column entries containing commas which are *not*
%**       delimiters; these are enclosed within double quotes. Therefore 
%**       these rows contain one more comma than would be expected for a
%**       standard csv file.
%**************************************************************************

%.. make sure that there are the expected number of columns in the header.
fid = fopen(assetRecord_filename);
AR = textscan(fid,'%s','whitespace','','delimiter','\n');
fclose(fid);
AR = AR{1};  % unwrap
n_commas = length(strfind(AR{1}, ','));  % # commas in header row
ncol_actual = n_commas + 1;
if ncolAR ~= ncol_actual
    err_msg = ['Unexpected number of columns in '  assetRecord_filename];
    error(err_msg);
end
%.. get and check the header entries
header = AR{1};
if strcmpi(header, header_expected)
    disp('column labels of ''ENG'' asset record are as expected.');
else
    disp('header');
    disp(header')
    disp('header_expected');
    disp(header_expected)
    error('column labels of ''ENG'' asset record are not as expected.');
end
%.. only need the entries in the first column, but can't use split because
%.. some rows contain commas which are not delimiters.
Asset_uid = cellfun(@(x) x(1:find(x==',', 1, 'first')-1), AR(2:end), ...
    'UniformOutput', 0);
%.. find sensor_uids missing from Asset_uid, don't sort result
%.. .. 2019: only CGCON entries are in eng_bulk_load
Missing_uid = setdiff(Sensor_uid, Asset_uid, 'stable');
%.. these missing instrument uids are useful to detect:
%.. (a) new instrumentation that needs to be added to assetRecord
%.. (b) an instrument series deployed at a non-matching RefDes port, eg:
%..     (i)  an OPTAAC deployed on an nsif
%..     (ii) a series J (cspp) instrument deployed on a surface mooring
disp(' ');
disp('UIDs missing from the ''Eng'' asset record:');
if isempty(Missing_uid)
    disp('None.');
else
    disp(Missing_uid);
    %.. check to see if the missing uid indicates a new profiler (technically,
    %.. profiler controller); if so, a new node asset entry is also needed.
    q = Missing_uid;
    q = strrep(q, 'CGCON-CSPPCE', 'CGVEH-CSPPCE');  % if cspp
    q = strrep(q, 'CGCON-CWFPCE', 'CGVEH-CWFPCE');  % if wfp
    node = q(strncmpi(q, 'cgveh', 5));
    if ~isempty(node)
        disp('UID missing from the node asset record:');
        disp(node);
    end
end
disp(' ');
end











