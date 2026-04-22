param(
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$EngineRoot,
    [string]$OutputRoot = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'projects\RoboQuest_jmap_426_local'),
    [string]$DumpPath,
    [switch]$GenerateProjectFiles,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve_ue426_root.ps1')

function Invoke-Checked([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedEngineRoot = Resolve-UE426Root -PreferredPath $EngineRoot
$dumpCandidates = @(
    (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.v2.jmap'),
    (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.all.jmap'),
    (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.jmap')
)

if ($DumpPath) {
    $resolvedDumpPath = (Resolve-Path -LiteralPath $DumpPath).Path
} else {
    $resolvedDumpPath = $dumpCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $resolvedDumpPath) {
    throw 'No jmap dump was found. Run dump_modding_artifacts.ps1 first or pass -DumpPath.'
}

$uhtDumpRoot = Join-Path $resolvedRepoRoot 'references\ue4ss\UHTHeaderDump'
if (-not (Test-Path -LiteralPath $uhtDumpRoot)) {
    throw "UHT dump not found: $uhtDumpRoot"
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $resolvedOutputRoot) {
    Remove-Item -LiteralPath $resolvedOutputRoot -Recurse -Force
}

$engineReferenceRoot = Join-Path $resolvedRepoRoot 'tooling\generated\engine_module_reference'
if (-not (Test-Path -LiteralPath $engineReferenceRoot)) {
    Invoke-Checked 'powershell' @(
        '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $PSScriptRoot 'materialize_engine_reference.ps1'),
        '-EngineRoot', $resolvedEngineRoot,
        '-DestinationRoot', $engineReferenceRoot
    )
}

$configCandidates = @(
    (Join-Path $resolvedRepoRoot 'references\generated_project\P\RoboQuest\Config'),
    (Join-Path $resolvedRepoRoot 'references\generated_project\RoboQuest\Config'),
    (Join-Path $resolvedRepoRoot 'references\generated_project\Config')
)
$configSource = $configCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

$generatorScript = Join-Path $resolvedRepoRoot 'tooling\roboquest_scripts_snapshot\jmap_generate_uproject.py'
$generatorArgs = @(
    '-3',
    $generatorScript,
    $resolvedDumpPath,
    '--project-name', 'RoboQuest',
    '--root-module', 'RoboQuest',
    '--modules', 'ALL',
    '--out-dir', $resolvedOutputRoot,
    '--engine-association', '4.26',
    '--engine-root', $resolvedEngineRoot,
    '--engine-reference-root', $engineReferenceRoot,
    '--uht-dump-root', $uhtDumpRoot
)
if ($configSource) {
    $generatorArgs += @('--copy-config-from', $configSource)
}

Invoke-Checked 'py' $generatorArgs

$uprojectPath = Join-Path $resolvedOutputRoot 'RoboQuest.uproject'
if ($GenerateProjectFiles) {
    Invoke-Checked (Join-Path $resolvedEngineRoot 'Engine\Binaries\DotNET\UnrealBuildTool.exe') @(
        '-projectfiles',
        "-project=$uprojectPath",
        '-game',
        '-engine'
    )
}

if ($Build) {
    $buildBat = Join-Path $resolvedEngineRoot 'Engine\Build\BatchFiles\Build.bat'
    cmd /c ('"' + $buildBat + '" RoboQuestEditor Win64 Development -Project="' + $uprojectPath + '" -WaitMutex -NoHotReloadFromIDE -NoUBTMakefiles -MaxParallelActions=6')
    if ($LASTEXITCODE -ne 0) {
        throw 'Build.bat failed'
    }
}

Write-Host "Editor project ready at $uprojectPath" -ForegroundColor Green
