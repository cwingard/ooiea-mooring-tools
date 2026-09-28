mstruct = defaultm('utm'); 
mstruct.zone = utmzone(47, -125); 
[ellipsoid, estr] = utmgeoid(mstruct.zone); 
mstruct.geoid = almanac('earth', 'geoid', 'm', estr); 
mstruct = defaultm(utm(mstruct));

% Deploy lat-lon (from cruise plan)
olat = 44 + 38.133 / 60;
olon = -(124 + 18.088 / 60);
[ox, oy] = projfwd(mstruct, olat, olon);

% Best guess if available, potentially back deck GPS reading. 
nlat = 44 + 38.05 / 60;  
nlon = -(124 + 18.02 / 60);

% Survey measurements (lat, lon and ranges in meters)
lat =  44 + [38.219 38.165 38.103] / 60;
lon = -124 - [18.036 18.192 18.20] / 60;
ranges = [358 253 192]; 
[utmx, utmy] = projfwd(mstruct, lat, lon);

% Initial guess based on average of surveyed lat/lon
[nx_guess, ny_guess] = projfwd(mstruct, mean(lat), mean(lon));

% Iterative optimization
options = optimset('TolFun', 1e-6, 'MaxIter', 1000); % Set tolerance and max iterations
initial_guess = [nx_guess, ny_guess];  % Start in UTM coordinates

% Nonlinear least squares solver for minimizing distance errors
final_point = lsqnonlin(@(point) triangulation_error(point, utmx, utmy, ranges), ...
                        initial_guess, [], [], options);

% Convert back to latitude and longitude
[final_lat, final_lon] = projinv(mstruct, final_point(1), final_point(2));

disp(['Final triangulated point: Latitude = ', num2str(final_lat), ', Longitude = ', num2str(final_lon)]);

% Function to calculate error between guessed point and range measurements
function error = triangulation_error(point, utmx, utmy, ranges)
    % Compute distance between guessed point and surveyed points
    xydist = sqrt((utmx - point(1)).^2 + (utmy - point(2)).^2);
    % Error is the difference between calculated and measured distances
    error = xydist - ranges;
end
