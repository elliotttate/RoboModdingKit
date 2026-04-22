@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "SOURCE_DIR=%SCRIPT_DIR%"
set "BUILD_DIR=%SOURCE_DIR%\build"

set "SDKGENNY_SOURCE_DIR=%~1"
if not defined SDKGENNY_SOURCE_DIR if exist "%SOURCE_DIR%\..\external_sources\sdkgenny\" set "SDKGENNY_SOURCE_DIR=%SOURCE_DIR%\..\external_sources\sdkgenny"
if not defined SDKGENNY_SOURCE_DIR (
    echo usage: build_emit.cmd ^<path-to-sdkgenny-checkout^>
    echo.
    echo The default dump pipeline uses the prebuilt bin\rq_sdkgenny_emit.exe and does not need this step.
    exit /b 1
)

where cl >nul 2>nul
if errorlevel 1 (
    set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
    if exist "%VSWHERE%" (
        for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find **\VsDevCmd.bat`) do set "VSDEVCMD=%%I"
        if defined VSDEVCMD (
            call "%VSDEVCMD%" -arch=amd64 -host_arch=amd64
            if errorlevel 1 exit /b 1
        )
    )
)

cmake -S "%SOURCE_DIR%" -B "%BUILD_DIR%" -G Ninja -DCMAKE_BUILD_TYPE=Release -DSDKGENNY_SOURCE_DIR="%SDKGENNY_SOURCE_DIR%"
if errorlevel 1 exit /b 1

cmake --build "%BUILD_DIR%" --config Release
if errorlevel 1 exit /b 1
