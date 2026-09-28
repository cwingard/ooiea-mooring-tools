% September 28, 2023 Deployment of CE02SHSM-00017
mstruct = defaultm('utm'); 
mstruct.zone = utmzone(47, -125); 
[ellipsoid, estr] = utmgeoid(mstruct.zone); 
mstruct.geoid = almanac('earth', 'geoid', 'm', estr); 
mstruct = defaultm(utm(mstruct));

% deploy lat-lon (from cruise plan)
olat = 44 + 38.370 / 60;
olon = -(124 + 18.300 / 60);
[ox, oy] = mfwdtran(mstruct, olat, olon);

% new lat-lon calculated by iteration
%nlat = 44 + 38.370 / 60;        % as planned
%nlon = -(124 + 18.300 / 60);
%nlat = 44 + 38.429 / 60;       % from back deck
%nlon = -(124 + 18.316 / 60);
nlat = 44 + 38.437 / 60;       % iteration
nlon = -(124 + 18.326 / 60);

disp(['new lat ', num2str(60 * (nlat - floor(nlat))), ' lon ', num2str(60 * (nlon - ceil(nlon)))]);
[nx, ny] = mfwdtran(mstruct, nlat, nlon); % convert to utm meters

% measurements from survey. 
lat =  44 + [38.1187 38.4456 38.416 38.5960 38.317] / 60;
lon = -124 - [18.2385 18.0687 18.669 18.4842 18.550] / 60;
ranges = [623 351 473 378 387]; % meters range from the echosounder
[utmx, utmy] = mfwdtran(mstruct, lat, lon);

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
    [slat, slon] = minvtran(mstruct, sx, sy);
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
    [slat, slon] = minvtran(mstruct, sx, sy);
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
