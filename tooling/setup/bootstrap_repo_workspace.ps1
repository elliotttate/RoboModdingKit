param(
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [switch]$CloneExternalSources
)

$ErrorActionPreference = 'Stop'

$paths = @(
    (Join-Path $RepoRoot 'projects'),
    (Join-Path $RepoRoot 'references'),
    (Join-Path $RepoRoot 'tooling\external_sources')
)

foreach ($path in $paths) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    Write-Host "ready $path"
}

if ($CloneExternalSources) {
    & (Join-Path $PSScriptRoot 'bootstrap_external_sources.ps1') `
        -DestinationRoot (Join-Path $RepoRoot 'tooling\external_sources')
    if ($LASTEXITCODE -ne 0) {
        throw 'bootstrap_external_sources.ps1 failed'
    }
}

Write-Host ''
Write-Host 'Workspace bootstrap complete.' -ForegroundColor Green
Write-Host 'Next steps:'
Write-Host '1. Install RoboQuest locally and point your generation commands at that install.'
Write-Host '2. Install UE 4.26.'
Write-Host '3. Read docs/10_generation_pipeline.md.'
Write-Host '4. Generate local dumps into references/ and a local jmap project into projects/.'
