config_to_deploy_code
desiderio 20-mar-2024

There are 8 main programs, 7 for the surface moorings and one for cspp deployments. The profiler mains in particular may not be worth spending time on because the entries in their deploy.csv files can easily be done by hand. Note that while I track the cspp profiler deployment number (different than the site deployment number) for each deployment of the cspp profilers in my local folder names, GH-AM does not. 

Main programs call the subroutines in the dependences folder. The sub_append subroutine can add 'new' platcon entries to the asset record if they are missing from local master, but for this turn I will have already submitted them to Github as part of the pre-cruise crossMIO updates. 

All mains are in 'test' mode. The ce01issm append code has no sensor_uid series changes in the 2nd column of the refdes_sensor cell array, I sent the code "as is".

I also have a routine included in the 'extra' folder. You don't need to bother with it, I will use it to automatically shotgun the addition of the surface mooring UIDs to asset management in the pre-cruise crossMIO updates.