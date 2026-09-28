% October 9, 2024 Deployment of CE07SHSM-00019
mstruct = defaultm('utm'); 
mstruct.zone = utmzone(47, -125); 
[ellipsoid, estr] = utmgeoid(mstruct.zone); 
mstruct.geoid = almanac('earth', 'geoid', 'm', estr); 
mstruct = defaultm(utm(mstruct));

% deploy lat-lon (from cruise plan)
olat = 46 + 59.175 / 60;         % from E-Log
olon = -(124 + 34.129 / 60);
[ox, oy] = projfwd(mstruct, olat, olon);

% new lat-lon calculated by iteration
%nlat = 46 + 59.175 / 60;         % from E-Log
%nlon = -(124 + 34.129 / 60);
nlat = 46 + 59.175 / 60;        % iteration
nlon = -(124 + 34.085 / 60);

disp(['new lat ', num2str(60 * (nlat - floor(nlat))), ' lon ', num2str(60 * (nlon - ceil(nlon)))]);
[nx, ny] = projfwd(mstruct, nlat, nlon); % convert to utm meters

% measurements from survey. 
lat =  46 + [59.044 59.211 59.290] / 60;
lon = -124 - [34.113 34.294 33.992] / 60;
ranges = [263 289 262]; % meters range from the echosounder
[utmx, utmy] = projfwd(mstruct, lat, lon);

figure(1);
set(gca, 'fontsize', 12);
axesm(mstruct);
plotm(nlat, nlon, 'xg', 'linewidth', 2, 'markersize', 10);
hold on;
plotm(olat, olon, 'or', 'linewidth', 2, 'markersize', 10);
plotm(lat, lon, 'k.', 'markersize', 10); 
legend({'as surveyed', 'as planned', 'survey locations'});
dutm = 50;
set(gca, 'xtick', floor(min(utmx) / 100) * 100:dutm:ceil(max(utmx) / 100) * 100, ...
         'ytick', floor(min(utmx) / 100) * 100:dutm:ceil(max(utmx) / 100) * 100);

ddegs = 1;
degs = ddegs:ddegs:360;
% (x, y) coordinates around circles where it could be based on survey
for i = 1:length(lat)
    sx = utmx(i) + ranges(i) * cos(degs * pi / 180);
    sy = utmy(i) + ranges(i) * sin(degs * pi / 180);
    [slat, slon] = projinv(mstruct, sx, sy);
    plotm(slat, slon, 'k');
end
% textm(lat, lon, {'N', 'ESE', 'WSW', 'WNW', 'ENE', 'S', 'X'});
xlabel('UTM meters');
ylabel('UTM meters');
title([int2str(dutm), ' meter squares']);
xlim = get(gca, 'xlim');
set(gca, 'xtick', xlim(1):dutm:xlim(2));
ylim = get(gca, 'ylim'); 
set(gca, 'ytick', ylim(1):dutm:ylim(2));
grid on

figure(2);
set(gca, 'fontsize', 12); 
plot(nlon, nlat, 'xg', 'linewidth', 2, 'markersize', 10);
hold on;
plot(olon, olat, 'or', 'linewidth', 2, 'markersize', 10);
plot(lon, lat, 'k.', 'markersize', 10); 
legend({'as surveyed', 'as planned', 'survey locations'})

% (x, y) coordinates around circles where it could be based on survey
for i = 1:length(lat)
    sx = utmx(i) + ranges(i) * cos(degs * pi / 180);
    sy = utmy(i) + ranges(i) * sin(degs * pi / 180);
    [slat, slon] = projinv(mstruct, sx, sy);
    plot(slon, slat, 'k');
end
% textm(lat, lon, {'N', 'ESE', 'WSW', 'WNW', 'ENE', 'S', 'X'});
xlabel('longitude'); 
ylabel('latitude'); 
grid on

% depth calculation
xydist = sqrt( (utmx-nx).^2 + (utmy-ny).^2 );
% disp(['Ship to surveyed release horizontal distances ', int2str(xydist)]);
depths = sqrt( ranges.^2 - xydist.^2);
disp(['Depth of release calculated from each survey point: ', int2str(depths),' dist ',num2str(sqrt(sum((depths-mean(depths)).^2)))]);
% disp(['     mean: ', int2str(mean(depths)), ', standard deviation: ', int2str(std(depths))]);
