%.. append_mooringUID_to_platformAssetRecord
%.. desiderio 30-oct-2017
%.. desiderio 08-feb-2019: Updated to take into account that asset Record csv
%..                        file entries bracketed with double quotes contain
%..                        commas which are *not* delimiters.
%.. desiderio 15-oct-2019: output is now sorted.
%
%.. Inputs:  All hardcoded, change each deployment turn as needed:
%..         (a) the deployment-mooring S/Ns to be added;
%..             can be surface moorings and profilers (cspp and wfp)
%..         (b) platform_bulk_load-AssetRecord.csv
%..
%.. Output:  platform_bulk_load-AssetRecord.csv
 
clearvars  % always clear variables denoting cell arrays

%mode = 'test';  % don't write to local master, write to RAMdrive
mode = 'update';  % write to local master

%.. using this format, individual moorings can be commented out
%
%.. (although they don't need to be, because existence is checked).
%
%
%.. FOLLOW THIS CONVENTION:
%.. .. Only update a mooring's deployment number immediately before this code
%.. .. is run to update the platform_bulk asset management file. Comment
%.. .. out those files that are not to be updated.
%..
%.. .. In that way, it can be determined at a glance the state of
%.. .. mooring.uid entries - in all cases for all moorings, whether
%.. .. commented out or not, the deployment number listed will be
%.. .. the most recent update into asset management.
%..
%.. .. Plus, the last mooring(s) updated will not be commented out.
%..
%.. .. AFTER A RUN DO NOT ANTICIPATE THE NEXT RUN AT A LATER DATE BY 
%.. .. INCREMENTING AND THEN COMMENTING THAT LINE OUT.
Mooring_SN = {
      'CE01ISSM-00021'
      'CE02SHSM-00019'
      'CE04OSSM-00018'
      %'CE06ISSM-00020'
      %'CE07SHSM-00019'
      %'CE09OSSM-00019'
      %'CE09OSPM-00021'
      %'CE01ISSP-00024'
      %'CE02SHSP-00036'
      %'CE06ISSP-00018'
      %'CE07SHSP-00016'
    };

%.. form uids from the deployment serial numbers so that a direct
%.. comparison can be made with existing uids.
%..     mooring_uids are of the form:
%..          CGMCE-01ISSM-00008
Mooring_uid = cellfun(@(x) ['CGM' x(1:2) '-' x(3:14)], Mooring_SN, ...
    'UniformOutput', false);

ncolAR = 14;  % number of columns in assetRecord_filename
assetRecord_path = 'C:\Users\chris\code\asset-management\bulk\';
assetRecord_filename = 'platform_bulk_load-AssetRecord.csv';
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

fid = fopen(assetRecord_filename);
AR = textscan(fid,'%s','whitespace','','delimiter','\n');
fclose(fid);
AR = AR{1};  % unwrap
%.. save this version of the asset record - the new uid entries
%.. will be directly appended to it.
Asset_Record = AR;

%.. make sure that there are the expected number of columns.
n_commas = length(strfind(AR{1}, ','));  % # commas in header row
ncol_actual = n_commas + 1;
if ncolAR ~= ncol_actual
    err_msg = ['Unexpected number of columns in '  assetRecord_filename];
    error(err_msg);
end
%.. get the header entries
header = AR{1};
%.. check against expected order:
if strcmpi(header, header_expected)
    disp('column labels of platformAssetRecord are as expected.');
else
    error('column labels of platformAssetRecord are not as expected.');
end
%.. only need the entries in the first column, but can't use split because
%.. some rows contain commas which are not delimiters.
Asset_uid = cellfun(@(x) x(1:find(x==',', 1, 'first')-1), AR(2:end), ...
    'UniformOutput', 0);
%.. find sensor_uids missing from Asset_uid, don't sort result
Missing_uid = setdiff(Mooring_uid, Asset_uid, 'stable');

disp(' ');
disp('UIDs missing from the asset record:');
if isempty(Missing_uid)
    disp('None.');
    disp('Program terminated.')
    disp(' ');
    return
else
    disp(Missing_uid);
end
disp(' ');


%.. set up a dictionary so that the missing mooring_uid can be parsed
%.. to form the asset record entries:
%
%   CGMCE-XX__YY-______
%
%   XX = 01: Oregon Inshore
%        02: Oregon Shelf
%        04: Oregon Offshore
%        06: Washington Inshore
%        07: Washington Shelf
%        09: Washington Offshore
%
%   YY = SM: Surface Mooring
%      = SP: Surface Piercing Profiler Mooring
%      = PM: Wire Following Profiler Mooring
keys = {'01' '02' '04' '06' '07' '09' 'SM' 'SP' 'PM'};
values = {'Coastal Endurance Oregon Inshore '       ...
          'Coastal Endurance Oregon Shelf '         ...
          'Coastal Endurance Oregon Offshore '      ...
          'Coastal Endurance Washington Inshore '   ...
          'Coastal Endurance Washington Shelf '     ...
          'Coastal Endurance Washington Offshore '  ...
          'Surface Mooring'                         ...
          'Surface Piercing Profiler Mooring'       ...
          'Wire Following Profiler Mooring'            };
Dict = containers.Map(keys, values);
template = ['UID,,Platform,0,equipmentD,MOORING ENDURANCE,' ...
    'WHOI,model,SN,,,,,Oregon State University'];
New_asset_entry(1:length(Missing_uid), 1) = {template};
for ii=1:length(Missing_uid)
    key1 = Missing_uid{ii}(7:8);      % mooring location
    key2 = Missing_uid{ii}(11:12);    % mooring type

    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'UID', Missing_uid{ii});

    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'equipmentD', [Dict(key1) Dict(key2)]);

    model = Missing_uid{ii}([4:5 7:12]);
    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'model', model);   

    sernum = Missing_uid{ii}([4:5 7:end]);
    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'SN', sernum);
end
disp('New asset entries:');
disp(New_asset_entry)
Asset_Record = sort([Asset_Record; New_asset_entry]);

if strcmpi(mode, 'update')
    fid = fopen(assetRecord_filename, 'w');
else
    fid = fopen('R:\platform.csv', 'w');    % test, write to RAMdrive
    disp('Test: check ''R:\platform.csv'' ');
end

for ii = 1:length(Asset_Record)
    fprintf(fid, '%s\n', Asset_Record{ii, :});
end
fclose(fid);

commandwindow
