@echo off
setlocal

set "PATH=%PATH:"=%"
set INCLUDE=
set LIB=
set LIBPATH=

call C:\PROGRA~1\MICROS~3\2022\COMMUN~1\VC\AUXILI~1\Build\vcvars64.bat
if errorlevel 1 exit /b 1

cmake -S "E:\SteamLibrary\steamapps\common\RoboQuest\sdk_dump_tools" -B "E:\SteamLibrary\steamapps\common\RoboQuest\sdk_dump_tools\build" -G Ninja -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1

cmake --build "E:\SteamLibrary\steamapps\common\RoboQuest\sdk_dump_tools\build" --config Release
if errorlevel 1 exit /b 1
