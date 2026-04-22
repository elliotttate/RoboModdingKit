param(
    [string]$RepoRoot,
    [string]$GameRoot,
    [string]$EngineRoot,
    [string]$GeneratedProjectRoot,
    [string]$OutputJson
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve_ue426_root.ps1')

if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
if (-not $OutputJson) {
    $OutputJson = Join-Path $RepoRoot 'tooling\generated\doctor_report.json'
} elseif (-not (Split-Path $OutputJson -Parent)) {
    $OutputJson = Join-Path (Get-Location) $OutputJson
}

function Resolve-PythonCommand() {
    foreach ($candidate in @(
        @{ FilePath = 'py'; PrefixArguments = @('-3') },
        @{ FilePath = 'python'; PrefixArguments = @() },
        @{ FilePath = 'python3'; PrefixArguments = @() }
    )) {
        try {
            Get-Command $candidate.FilePath -ErrorAction Stop | Out-Null
            return $candidate
        } catch {
        }
    }
    return $null
}

function Add-Check([System.Collections.Generic.List[object]]$Checks, [string]$Name, [bool]$Ok, [string]$Details) {
    $Checks.Add([pscustomobject]@{
        Name = $Name
        Ok = $Ok
        Details = $Details
    })
}

function Resolve-GeneratedProjectPath([string]$RepoRootPath, [string]$PreferredRoot) {
    if ($PreferredRoot) {
        $resolvedPreferred = (Resolve-Path -LiteralPath $PreferredRoot).Path
        if ($resolvedPreferred.EndsWith('.uproject', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $resolvedPreferred
        }
        return Join-Path $resolvedPreferred 'RoboQuest.uproject'
    }

    $defaultProject = Join-Path $RepoRootPath 'projects\RoboQuest_jmap_426_local\RoboQuest.uproject'
    if (Test-Path -LiteralPath $defaultProject) {
        return $defaultProject
    }

    $projectsRoot = Join-Path $RepoRootPath 'projects'
    if (-not (Test-Path -LiteralPath $projectsRoot -PathType Container)) {
        return $defaultProject
    }

    $candidates = Get-ChildItem -LiteralPath $projectsRoot -Directory |
        ForEach-Object { Join-Path $_.FullName 'RoboQuest.uproject' } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        ForEach-Object { Get-Item -LiteralPath $_ } |
        Sort-Object LastWriteTime -Descending
    if ($candidates) {
        return $candidates[0].FullName
    }

    return $defaultProject
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$checks = New-Object 'System.Collections.Generic.List[object]'

$python = Resolve-PythonCommand
Add-Check $checks 'Python 3' ([bool]$python) ($(if ($python) { $python.FilePath } else { 'Not found on PATH' }))

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
Add-Check $checks 'git' ([bool]$gitCommand) ($(if ($gitCommand) { $gitCommand.Source } else { 'Not found on PATH' }))

try {
    $resolvedEngineRoot = Resolve-UE426Root -PreferredPath $EngineRoot
    Add-Check $checks 'UE 4.26 root' $true $resolvedEngineRoot
    Add-Check $checks 'UE4Editor.exe' (Test-Path -LiteralPath (Join-Path $resolvedEngineRoot 'Engine\Binaries\Win64\UE4Editor.exe')) (Join-Path $resolvedEngineRoot 'Engine\Binaries\Win64\UE4Editor.exe')
    Add-Check $checks 'UnrealPak.exe' (Test-Path -LiteralPath (Join-Path $resolvedEngineRoot 'Engine\Binaries\Win64\UnrealPak.exe')) (Join-Path $resolvedEngineRoot 'Engine\Binaries\Win64\UnrealPak.exe')
} catch {
    Add-Check $checks 'UE 4.26 root' $false $_.Exception.Message
}

foreach ($relativePath in @(
    'tooling\bin\jmap_dumper.exe',
    'tooling\bin\repak.exe',
    'tooling\bin\retoc.exe',
    'tooling\bin\kismet-analyzer.exe',
    'tooling\setup\dump_modding_artifacts.ps1',
    'tooling\setup\dump_aes_keys.py',
    'tooling\setup\doctor_moddingkit.ps1',
    'tooling\setup\generate_editor_project.ps1',
    'tooling\setup\package_mod.ps1',
    'tooling\setup\install_mod.ps1',
    'tooling\setup\uninstall_mod.ps1',
    'tooling\setup\restore_game_runtime_backup.ps1',
    'templates\ue4ss\HelloRoboLogMod\robomod.json',
    'templates\pak\HelloPakMod\robomod.json',
    'runtime\UE4SS_working_runtime\Win64\UE4SS.dll',
    'runtime\UE4SS_working_runtime\Win64\dwmapi.dll'
)) {
    $path = Join-Path $resolvedRepoRoot $relativePath
    Add-Check $checks $relativePath (Test-Path -LiteralPath $path) $path
}

$summaryPath = Join-Path $resolvedRepoRoot 'references\dump_summary.json'
Add-Check $checks 'Dump summary' (Test-Path -LiteralPath $summaryPath) $summaryPath
$projectPath = Resolve-GeneratedProjectPath -RepoRootPath $resolvedRepoRoot -PreferredRoot $GeneratedProjectRoot
Add-Check $checks 'Generated project' (Test-Path -LiteralPath $projectPath) $projectPath

if ($GameRoot) {
    try {
        $resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
        Add-Check $checks 'Game root' $true $resolvedGameRoot
        Add-Check $checks 'RoboQuest shipping exe' (Test-Path -LiteralPath (Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64\RoboQuest-Win64-Shipping.exe')) (Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64\RoboQuest-Win64-Shipping.exe')
        Add-Check $checks 'Base pak' (Test-Path -LiteralPath (Join-Path $resolvedGameRoot 'RoboQuest\Content\Paks\RoboQuest-WindowsNoEditor.pak')) (Join-Path $resolvedGameRoot 'RoboQuest\Content\Paks\RoboQuest-WindowsNoEditor.pak')
        Add-Check $checks 'UE4SS mods.txt' (Test-Path -LiteralPath (Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64\Mods\mods.txt')) (Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64\Mods\mods.txt')
    } catch {
        Add-Check $checks 'Game root' $false $_.Exception.Message
    }
}

$overallOk = -not ($checks | Where-Object { -not $_.Ok })

New-Item -ItemType Directory -Path (Split-Path $OutputJson -Parent) -Force | Out-Null
[pscustomobject]@{
    generated_at = (Get-Date).ToString('s')
    repo_root = $resolvedRepoRoot
    overall_ok = $overallOk
    checks = $checks
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputJson

$checks | Sort-Object Name | Format-Table Name, Ok, Details -AutoSize
Write-Host ''
Write-Host "Doctor report written to $OutputJson" -ForegroundColor Green

if (-not $overallOk) {
    exit 1
}
