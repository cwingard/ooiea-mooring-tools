function sub_append_platconUID_to_engAssetRecord(Missing_uid, mode)
%.. desiderio 29-oct-2017; from sub_append_platconUID_to_sensorAssetRecord
%.. desiderio 07-feb-2019: UPDATED to reflect re-organization of GitHub 
%..                        Asset Management: all CGCON equipment will be
%..                        moved from sensor_bulk_load to eng_bulk_load.
%.. desiderio 15-oct-2019: added sort statement for alphabetization
%.. desiderio 20-sep-2023: separated header out of sorted cell array because
%..                        header row is not first element in sorted product
%..                        
%
%   subroutine called by append_deploy_XXXXXXXX.m where xxxxxxxx = 
%       ce01issm
%       ce02shsm
%       ce04ossm
%       ce06issm
%       ce07shsm
%       ce09ossm
%
%  This subroutine should not be called by profiler mooring routines because
%  updating the asset record files with entries for new profiler mooring
%  CGCON uids has not been automated.  
%
%************************************************************************
%.. Inputs:
%..     Missing_uid is a cell array of CGCON uids from a deployment that are
%..     not listed in 'eng_bulk_load-AssetRecord.csv'. It is created as the
%..     output of subroutine find_missing_bulkEng_entries.
%..     
%..     mode can be either 'test' or 'update', passed on by the calling
%..     program (one of the append_deploy_XXXXXXXX.m scripts listed above,
%..     the Endurance ISSM, SHSM, and OSSM moorings).
%..
%.. Outputs:
%..     Screen updates of action taken.
%..     if mode = 'update', APPENDS MISSING PLATCON.UID ENTRIES 
%..     to the engAssetRecord local master files. 
%************************************************************************

%.. in case profiler CGCON uids are input, acknowledge and discard them.
profiler_cgcon = {'BST' 'CSPP' 'WFP'};
tf_profiler_cgcon = contains(Missing_uid, profiler_cgcon);
if any(tf_profiler_cgcon)
    disp('Profiler cgcon UIDs (mistakenly(?)) input to function: ');
    disp(Missing_uid(tf_profiler_cgcon));
    disp('These will not be processed.');
    disp(' ');
end
Missing_uid(tf_profiler_cgcon) = [];
%.. delete empty cell array elements if present
Missing_uid(cellfun('isempty', Missing_uid)) = [];
if isempty(Missing_uid)
    disp('No missing CGCON uids.');
    disp(' ');
    return
end

ncolAR = 14;  % number of columns in assetRecord_filename
assetRecord_path = 'C:\Users\chris\code\asset-management\bulk\';
assetRecord_filename = 'eng_bulk_load-AssetRecord.csv';
assetRecord_filename = [assetRecord_path assetRecord_filename];

%********  READ IN ASSET RECORD FILE *******************
%.. make sure that there are the expected number of columns.
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
%.. get the header entries
header = AR{1};
%.. check against expected order:
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

if strcmpi(header, header_expected)
    disp('column labels of asset record are as expected.');
else
    error('column labels of asset record not as expected.');
end

%.. save this version of the asset record - the new uid entries
%.. will be directly appended to it.
%
%.. remove header row
Asset_Record = AR(2:end);

%.. set up a dictionary so that the platcon uids can be parsed
%.. to form the asset record entries:
%
%   CGCON-XYYY__-ZZZZZ
%
%   X   =  B: Surface Buoy
%          E: Surface Buoy
%          N: Near Surface Instrument Frame
%          M: Multi-Function Node
%
%   YYY = CPM: Communications and Power Manager
%         DCL: Data Concentrator Logger
%
%  ZZZZZ = serial number that will be written out to asset record.
%              note that if ZZZZZ=60004, the actual S/N was 2016-0004,
%              but I will still write 60004.
keys = {'B' 'E' 'N' 'M' 'CPM' 'DCL'};
values = {'Surface Buoy '                      ...
          'Surface Buoy '                      ...
          'Near Surface Instrument Frame '     ...
          'Multi-Function Node '               ...
          'Communications and Power Manager'   ...
          'Data Concentrator Logger'           };
Dict = containers.Map(keys, values);
template = 'UID,,Sensor,0,equipmentD,inventoryD,WHOI,model,SN,,,,,';
New_asset_entry(1:length(Missing_uid), 1) = {template};
for ii=1:length(Missing_uid)
    key1 = Missing_uid{ii}(7);     % platform
    key2 = Missing_uid{ii}(8:10);  % controller type
    tf = isKey(Dict, {key1 key2});
    if ~prod(tf)
        disp(['One or both keys are not present in surface mooring ' ...
              'PlatCon dictionary for:']);
          disp(Missing_uid{ii});
          disp(['Key1 = ''' key1 ''',  Key2 = ''' key2 '''']);
        disp(' ');
        continue  % go to next iteration; 'UID' remains unchanged for this ii
    end
    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'UID', Missing_uid{ii});

    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'equipmentD', [Dict(key1) Dict(key2)]);

    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'inventoryD', Dict(key2));
    
    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'model', key2);   

    %.. strip leading zeros if present
    sernum = num2str(str2num(Missing_uid{ii}(end-4:end)));  %#ok
    New_asset_entry{ii} = strrep(New_asset_entry{ii}, ...
           'SN', sernum);
end

%.. If somehow bogus uids masquerading as platcons are present in Missing_uid,
%.. the first entry for that element of New_asset_entry will still be 'UID'.
%.. Delete.
New_asset_entry(strncmpi('UID', New_asset_entry, 3)) = [];
disp('New Platcon entries added to the sorted bulk_sensor Asset Record:')
if isempty(New_asset_entry)
    disp('    None needed.');
    disp('Program terminated; Asset Record not modified.')
    disp(' ');
    return
else
    disp(New_asset_entry)
end

if strcmpi(mode, 'update')
    fid = fopen(assetRecord_filename, 'w');
else
    fid = fopen('R:\bulk.csv', 'w');    % test, write to RAMdrive
end
Asset_Record = [header; sort([Asset_Record; New_asset_entry])];
for ii = 1:length(Asset_Record)
    fprintf(fid, '%s\n', Asset_Record{ii, :});
end
fclose(fid);
