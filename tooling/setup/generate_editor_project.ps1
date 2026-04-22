param(
    [string]$RepoRoot,
    [string]$EngineRoot,
    [string]$OutputRoot,
    [string]$DumpPath,
    [switch]$Clean,
    [switch]$SkipSuzie,
    [switch]$RefreshEngineReference,
    [switch]$GenerateProjectFiles,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve_ue426_root.ps1')

if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot 'projects\RoboQuest_jmap_426_local'
}

function Invoke-Checked([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
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

    throw 'Python 3 was not found. Install Python or ensure py/python/python3 is on PATH.'
}

function Assert-SafeGeneratedOutputRoot([string]$Path, [string]$RepoRoot) {
    $projectsRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'projects'))
    $leaf = Split-Path $Path -Leaf
    $pathRoot = [System.IO.Path]::GetPathRoot($Path)

    if ($Path -eq $pathRoot -or $Path -eq $RepoRoot -or $Path -eq $projectsRoot) {
        throw "Refusing to delete an unsafe output root: $Path"
    }

    if (-not ($leaf -like 'RoboQuest_jmap_*' -or (Test-Path -LiteralPath (Join-Path $Path 'RoboQuest.uproject')))) {
        throw "Refusing to delete '$Path' without a generated-project marker. Use a RoboQuest_jmap_* output root or delete it manually."
    }
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedEngineRoot = Resolve-UE426Root -PreferredPath $EngineRoot
$pythonCommand = Resolve-PythonCommand
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
    $existingItems = @(Get-ChildItem -LiteralPath $resolvedOutputRoot -Force -ErrorAction SilentlyContinue)
    if ($existingItems.Count -gt 0) {
        if (-not $Clean) {
            throw "Output root already exists and is not empty: $resolvedOutputRoot`nRe-run with -Clean to replace it."
        }
        Assert-SafeGeneratedOutputRoot -Path $resolvedOutputRoot -RepoRoot $resolvedRepoRoot
        Remove-Item -LiteralPath $resolvedOutputRoot -Recurse -Force
    }
}

$engineReferenceRoot = Join-Path $resolvedRepoRoot 'tooling\generated\engine_module_reference'
if ($RefreshEngineReference -and (Test-Path -LiteralPath $engineReferenceRoot)) {
    Remove-Item -LiteralPath $engineReferenceRoot -Recurse -Force
}
if (-not (Test-Path -LiteralPath $engineReferenceRoot)) {
    & (Join-Path $PSScriptRoot 'materialize_engine_reference.ps1') `
        '-EngineRoot', $resolvedEngineRoot,
        '-DestinationRoot', $engineReferenceRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'materialize_engine_reference.ps1 failed'
    }
}

$configCandidates = @(
    (Join-Path $resolvedRepoRoot 'references\generated_project\P\RoboQuest\Config'),
    (Join-Path $resolvedRepoRoot 'references\generated_project\RoboQuest\Config'),
    (Join-Path $resolvedRepoRoot 'references\generated_project\Config')
)
$configSource = $configCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$projectPluginRootCandidates = @(
    (Join-Path $resolvedRepoRoot 'references\generated_project\P\RoboQuest\Plugins'),
    (Join-Path $resolvedRepoRoot 'references\generated_project\RoboQuest\Plugins'),
    (Join-Path $resolvedRepoRoot 'references\generated_project\Plugins')
)
$projectPluginRoot = $projectPluginRootCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

$generatorScript = Join-Path $resolvedRepoRoot 'tooling\roboquest_scripts_snapshot\jmap_generate_uproject.py'
$generatorArgs = @(
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
if ($projectPluginRoot) {
    $generatorArgs += @('--project-plugin-root', $projectPluginRoot)
}

Invoke-Checked $pythonCommand.FilePath (@($pythonCommand.PrefixArguments) + $generatorArgs)

$uprojectPath = Join-Path $resolvedOutputRoot 'RoboQuest.uproject'
New-Item -ItemType Directory -Path (Join-Path $resolvedOutputRoot 'Content') -Force | Out-Null

if (-not $SkipSuzie) {
    $suzieDumpCandidates = @(
        (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.jmap'),
        $resolvedDumpPath
    ) | Select-Object -Unique
    $suzieDumpPath = $suzieDumpCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

    $installSuzieScript = Join-Path $PSScriptRoot 'install_suzie.ps1'
    $installSuzieArgs = @(
        '-RepoRoot', $resolvedRepoRoot,
        '-ProjectRoot', $resolvedOutputRoot
    )
    if ($suzieDumpPath) {
        $installSuzieArgs += @('-DumpPath', $suzieDumpPath)
    }
    $installSuzieInvokeArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $installSuzieScript) + $installSuzieArgs
    Invoke-Checked 'powershell' $installSuzieInvokeArgs
}

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
