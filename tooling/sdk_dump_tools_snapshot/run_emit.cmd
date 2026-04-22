@echo off
setlocal

if "%~2"=="" (
    echo usage: run_emit.cmd ^<input.genny^> ^<output_dir^>
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "EMITTER=%SCRIPT_DIR%\bin\rq_sdkgenny_emit.exe"

if not exist "%EMITTER%" (
    if "%~3"=="" (
        echo The prebuilt emitter is missing. Pass a sdkgenny checkout as the optional third argument to rebuild it.
        exit /b 1
    )
    call "%SCRIPT_DIR%\build_emit.cmd" "%~3" || exit /b 1
    set "EMITTER=%SCRIPT_DIR%\build\rq_sdkgenny_emit.exe"
)

"%EMITTER%" "%~1" "%~2" || exit /b 1
