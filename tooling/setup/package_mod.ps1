param(
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,
    [string]$OutputRoot,
    [ValidateSet('Auto', 'Pak', 'UE4SS')]
    [string]$Type = 'Auto',
    [string]$MountPoint = '../../../',
    [string]$Version = 'V11',
    [string]$Compression = 'Zlib',
    [uint32]$PathHashSeed = 51336062
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $RepoRoot 'tooling\generated\mod_packages'
}

function Ensure-Directory([string]$Path) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Get-ModManifest([string]$DirectoryPath) {
    $manifestPath = Join-Path $DirectoryPath 'robomod.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        return $null
    }
    return Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
}

function Resolve-ModType([string]$RequestedType, [string]$DirectoryPath, $Manifest) {
    if ($RequestedType -ne 'Auto') {
        return $RequestedType
    }
    if ($Manifest -and $Manifest.type) {
        switch -Regex ([string]$Manifest.type) {
            '^pak$' { return 'Pak' }
            '^ue4ss$' { return 'UE4SS' }
        }
    }
    if (Test-Path -LiteralPath (Join-Path $DirectoryPath 'Scripts\main.lua')) {
        return 'UE4SS'
    }
    if (Test-Path -LiteralPath (Join-Path $DirectoryPath 'stage')) {
        return 'Pak'
    }
    throw "Could not auto-detect mod type for $DirectoryPath. Pass -Type explicitly."
}

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$resolvedSourcePath = (Resolve-Path -LiteralPath $SourcePath).Path
if (-not (Test-Path -LiteralPath $resolvedSourcePath -PathType Container)) {
    throw "SourcePath must be a mod directory: $resolvedSourcePath"
}

Ensure-Directory $OutputRoot
$resolvedOutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$manifest = Get-ModManifest -DirectoryPath $resolvedSourcePath
$resolvedType = Resolve-ModType -RequestedType $Type -DirectoryPath $resolvedSourcePath -Manifest $manifest
$modName = if ($manifest -and $manifest.name) { [string]$manifest.name } else { Split-Path $resolvedSourcePath -Leaf }
$effectiveMountPoint = $MountPoint
$effectiveVersion = $Version
$effectiveCompression = $Compression
$effectivePathHashSeed = $PathHashSeed
if ($manifest) {
    if (-not $PSBoundParameters.ContainsKey('MountPoint') -and $manifest.mount_point) {
        $effectiveMountPoint = [string]$manifest.mount_point
    }
    if (-not $PSBoundParameters.ContainsKey('Version') -and $manifest.version) {
        $effectiveVersion = [string]$manifest.version
    }
    if (-not $PSBoundParameters.ContainsKey('Compression') -and $manifest.compression) {
        $effectiveCompression = [string]$manifest.compression
    }
    if (-not $PSBoundParameters.ContainsKey('PathHashSeed') -and $null -ne $manifest.path_hash_seed) {
        $effectivePathHashSeed = [uint32]$manifest.path_hash_seed
    }
}

if ($resolvedType -eq 'UE4SS') {
    $stagingRoot = Join-Path $resolvedOutputRoot ($modName + '_zip_stage')
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction SilentlyContinue
    Ensure-Directory $stagingRoot
    $zipSourceRoot = Join-Path $stagingRoot $modName
    Copy-Item -LiteralPath $resolvedSourcePath -Destination $zipSourceRoot -Recurse -Force

    $zipPath = Join-Path $resolvedOutputRoot ($modName + '.zip')
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path $zipSourceRoot -DestinationPath $zipPath -CompressionLevel Optimal
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    Write-Host "Packaged UE4SS mod to $zipPath" -ForegroundColor Green
    return
}

$stageRoot = if ($manifest -and $manifest.stage_root) {
    Join-Path $resolvedSourcePath ([string]$manifest.stage_root)
} else {
    Join-Path $resolvedSourcePath 'stage'
}
if (-not (Test-Path -LiteralPath $stageRoot -PathType Container)) {
    throw "Pak mod stage root was not found: $stageRoot"
}

$repakExe = Join-Path $resolvedRepoRoot 'tooling\bin\repak.exe'
if (-not (Test-Path -LiteralPath $repakExe)) {
    throw "repak.exe not found at $repakExe"
}

$workRoot = Join-Path $resolvedOutputRoot ($modName + '_pack_work')
Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
Ensure-Directory $workRoot

$builtPakPath = Join-Path $workRoot ($modName + '.pak')
& $repakExe 'pack' $stageRoot $builtPakPath '--mount-point' $effectiveMountPoint '--version' $effectiveVersion '--compression' $effectiveCompression '--path-hash-seed' $effectivePathHashSeed
if ($LASTEXITCODE -ne 0) {
    throw "repak pack failed for $stageRoot"
}

if (-not (Test-Path -LiteralPath $builtPakPath -PathType Leaf)) {
    throw "repak did not emit a pak at $builtPakPath"
}

$finalPakPath = Join-Path $resolvedOutputRoot ($modName + '.pak')
Move-Item -LiteralPath $builtPakPath -Destination $finalPakPath -Force
Remove-Item -LiteralPath $workRoot -Recurse -Force
Write-Host "Packaged pak mod to $finalPakPath" -ForegroundColor Green
