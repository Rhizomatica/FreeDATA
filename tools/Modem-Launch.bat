REM Place this batch file in FreeData/tnc and then run it
REM ie. c:\FD-Src\tnc

REM Set environment variable to let modem know where to find config, change if you need to specify a different config
set FREEDATA_CONFIG=.\config.ini 

REM launch modem
flask --app server run

pause