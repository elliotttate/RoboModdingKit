param(
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,
    [ValidateSet('Auto', 'Pak', 'UE4SS')]
    [string]$Type = 'Auto'
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}

function Ensure-Directory([string]$Path) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Get-ModManifestFromDirectory([string]$DirectoryPath) {
    $manifestPath = Join-Path $DirectoryPath 'robomod.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        return $null
    }
    return Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
}

function Test-IsUe4ssDirectory([string]$DirectoryPath, $Manifest) {
    if ($Manifest -and $Manifest.type -and ([string]$Manifest.type -match '^(?i:ue4ss)$')) {
        return $true
    }
    return Test-Path -LiteralPath (Join-Path $DirectoryPath 'Scripts\main.lua')
}

function Set-ModEnabled([string]$ModsTxtPath, [string]$ModName) {
    $lines = @()
    if (Test-Path -LiteralPath $ModsTxtPath) {
        $lines = Get-Content -LiteralPath $ModsTxtPath
    }
    $escapedName = [regex]::Escape($ModName)
    $filtered = @($lines | Where-Object { $_ -notmatch "^\s*$escapedName\s*:" })
    $filtered += "$ModName : 1"
    Set-Content -LiteralPath $ModsTxtPath -Value $filtered
}

$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$resolvedSourcePath = (Resolve-Path -LiteralPath $SourcePath).Path
$sourceItem = Get-Item -LiteralPath $resolvedSourcePath

$binRoot = Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64'
$modsRoot = Join-Path $binRoot 'Mods'
$modsTxtPath = Join-Path $modsRoot 'mods.txt'
$pakModsRoot = Join-Path $resolvedGameRoot 'RoboQuest\Content\Paks\~mods'

$workingType = $Type
$manifest = $null
$expandedRoot = $null
$modName = $null
$copySourcePath = $resolvedSourcePath

if ($sourceItem.PSIsContainer) {
    $manifest = Get-ModManifestFromDirectory -DirectoryPath $resolvedSourcePath
    if ($workingType -eq 'Auto') {
        if ($manifest -and $manifest.type) {
            $workingType = [string]$manifest.type
        } elseif (Test-Path -LiteralPath (Join-Path $resolvedSourcePath 'Scripts\main.lua')) {
            $workingType = 'UE4SS'
        } else {
            throw "Could not auto-detect mod type for directory $resolvedSourcePath"
        }
    }
    $modName = if ($manifest -and $manifest.name) { [string]$manifest.name } else { $sourceItem.Name }
    if ([string]$workingType -match '^(?i:pak)$') {
        throw "Pak mod directories must be packaged first. Run package_mod.ps1 for $resolvedSourcePath, then install the resulting .pak."
    }
    if (-not (Test-IsUe4ssDirectory -DirectoryPath $resolvedSourcePath -Manifest $manifest)) {
        throw "Directory payload is not a UE4SS mod: $resolvedSourcePath"
    }
} else {
    switch ($sourceItem.Extension.ToLowerInvariant()) {
        '.pak' {
            if ($workingType -eq 'Auto') {
                $workingType = 'Pak'
            } elseif ($workingType -notmatch '^(?i:pak)$') {
                throw "A .pak payload can only be installed as Type Pak."
            }
            $modName = [System.IO.Path]::GetFileNameWithoutExtension($sourceItem.Name)
        }
        '.zip' {
            if ($workingType -eq 'Auto') {
                $workingType = 'UE4SS'
            } elseif ($workingType -notmatch '^(?i:ue4ss)$') {
                throw "A .zip payload can only be installed as Type UE4SS."
            }
            $expandedRoot = Join-Path $env:TEMP ("RoboModdingKit_" + [guid]::NewGuid().ToString('N'))
            Expand-Archive -LiteralPath $resolvedSourcePath -DestinationPath $expandedRoot -Force
            $candidate = Get-ChildItem -LiteralPath $expandedRoot -Directory | Select-Object -First 1
            if (-not $candidate) {
                throw "Zip package did not contain a top-level directory: $resolvedSourcePath"
            }
            $copySourcePath = $candidate.FullName
            $manifest = Get-ModManifestFromDirectory -DirectoryPath $copySourcePath
            if (-not (Test-IsUe4ssDirectory -DirectoryPath $copySourcePath -Manifest $manifest)) {
                throw "Zip payload is not a UE4SS mod package: $resolvedSourcePath"
            }
            $modName = if ($manifest -and $manifest.name) { [string]$manifest.name } else { $candidate.Name }
        }
        default {
            throw "Unsupported mod payload: $resolvedSourcePath"
        }
    }
}

try {
    switch -Regex ([string]$workingType) {
        '^pak$' {
            Ensure-Directory $pakModsRoot
            $destinationPak = Join-Path $pakModsRoot ($modName + '.pak')
            Copy-Item -LiteralPath $sourceItem.FullName -Destination $destinationPak -Force
            Write-Host "Installed pak mod to $destinationPak" -ForegroundColor Green
        }
        '^ue4ss$' {
            Ensure-Directory $modsRoot
            $destinationRoot = Join-Path $modsRoot $modName
            Remove-Item -LiteralPath $destinationRoot -Recurse -Force -ErrorAction SilentlyContinue
            Copy-Item -LiteralPath $copySourcePath -Destination $destinationRoot -Recurse -Force
            Set-ModEnabled -ModsTxtPath $modsTxtPath -ModName $modName
            Write-Host "Installed UE4SS mod to $destinationRoot" -ForegroundColor Green
        }
        default {
            throw "Unsupported mod type: $workingType"
        }
    }
}
finally {
    if ($expandedRoot -and (Test-Path -LiteralPath $expandedRoot)) {
        Remove-Item -LiteralPath $expandedRoot -Recurse -Force
    }
}
