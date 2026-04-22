@echo off
setlocal

if "%~2"=="" (
    echo usage: run_emit.cmd ^<input.genny^> ^<output_dir^>
    exit /b 1
)

call "E:\SteamLibrary\steamapps\common\RoboQuest\sdk_dump_tools\build_emit.cmd" || exit /b 1
"E:\SteamLibrary\steamapps\common\RoboQuest\sdk_dump_tools\build\rq_sdkgenny_emit.exe" "%~1" "%~2" || exit /b 1

