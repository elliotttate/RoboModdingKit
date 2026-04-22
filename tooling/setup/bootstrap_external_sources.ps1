param(
    [string]$DestinationRoot = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'tooling\external_sources'),
    [switch]$UpdateExisting
)

$ErrorActionPreference = 'Stop'

$manifestPath = Join-Path $PSScriptRoot 'external_sources.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git is required but was not found on PATH.'
}

New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null

foreach ($repo in $manifest.repositories) {
    $repoPath = Join-Path $DestinationRoot $repo.name

    if (-not (Test-Path -LiteralPath $repoPath)) {
        Write-Host "clone $($repo.name) <- $($repo.url)"
        git clone $repo.url $repoPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to clone $($repo.url)"
        }
    } elseif ($UpdateExisting) {
        Write-Host "update $($repo.name)"
        git -C $repoPath pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update $repoPath"
        }
    } else {
        Write-Host "skip $($repo.name)"
    }

    if ($repo.PSObject.Properties.Name -contains 'ref' -and $repo.ref) {
        Write-Host "checkout $($repo.name) -> $($repo.ref)"
        git -C $repoPath fetch --tags
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to fetch tags for $repoPath"
        }
        git -C $repoPath checkout $repo.ref
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to checkout $($repo.ref) in $repoPath"
        }
    }
}

Write-Host ''
Write-Host "External sources are available in $DestinationRoot" -ForegroundColor Green
