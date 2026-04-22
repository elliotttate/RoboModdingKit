param(
    [string]$RepoRoot,
    [string]$ProjectRoot,
    [string]$DumpPath
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
if (-not $ProjectRoot) {
    $ProjectRoot = Join-Path $RepoRoot 'projects\RoboQuest_jmap_426_local'
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$uprojectPath = Join-Path $resolvedProjectRoot 'RoboQuest.uproject'

if (-not (Test-Path -LiteralPath $uprojectPath)) {
    throw "RoboQuest.uproject was not found at $uprojectPath"
}

$bundledSuzieRoot = Join-Path $resolvedRepoRoot 'templates\plugins\Suzie'
if (-not (Test-Path -LiteralPath (Join-Path $bundledSuzieRoot 'Suzie.uplugin'))) {
    throw "Bundled Suzie plugin was not found at $bundledSuzieRoot"
}

$dumpCandidates = @(
    (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.jmap'),
    (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.v2.jmap'),
    (Join-Path $resolvedRepoRoot 'references\dumps\RoboQuest.all.jmap')
)

if ($DumpPath) {
    $resolvedDumpPath = (Resolve-Path -LiteralPath $DumpPath).Path
} else {
    $resolvedDumpPath = $dumpCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $resolvedDumpPath) {
    throw 'No dump was found for Suzie. Run dump_modding_artifacts.ps1 first or pass -DumpPath.'
}

$pluginDestination = Join-Path $resolvedProjectRoot 'Plugins\Suzie'
New-Item -ItemType Directory -Path (Split-Path $pluginDestination -Parent) -Force | Out-Null

& robocopy $bundledSuzieRoot $pluginDestination /MIR /XD .git Binaries Intermediate /NFL /NDL /NJH /NJS /NP /R:1 /W:1
if ($LASTEXITCODE -gt 7) {
    throw "robocopy failed while copying Suzie (exit code $LASTEXITCODE)"
}

$dynamicClassesRoot = Join-Path $resolvedProjectRoot 'Content\DynamicClasses'
New-Item -ItemType Directory -Path $dynamicClassesRoot -Force | Out-Null
Copy-Item -LiteralPath $resolvedDumpPath -Destination (Join-Path $dynamicClassesRoot 'RoboQuest.jmap') -Force

$uproject = Get-Content -LiteralPath $uprojectPath -Raw | ConvertFrom-Json
if (-not $uproject.PSObject.Properties.Match('Plugins')) {
    $uproject | Add-Member -MemberType NoteProperty -Name Plugins -Value @()
}

$existingSuzie = @($uproject.Plugins) | Where-Object { $_.Name -eq 'Suzie' }
if ($existingSuzie.Count -gt 0) {
    foreach ($pluginEntry in $existingSuzie) {
        $pluginEntry.Enabled = $true
    }
} else {
    $uproject.Plugins += [pscustomobject]@{
        Name = 'Suzie'
        Enabled = $true
    }
}

$uproject | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $uprojectPath -Encoding UTF8

Write-Host "Suzie installed into $resolvedProjectRoot" -ForegroundColor Green
Write-Host "Dynamic classes dump: $resolvedDumpPath" -ForegroundColor Green
