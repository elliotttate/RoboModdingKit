param(
    [string]$EngineRoot,
    [string]$DestinationRoot = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'tooling\generated\engine_module_reference'),
    [switch]$CopyInsteadOfJunctions
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'resolve_ue426_root.ps1')

function Ensure-Directory([string]$Path) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Link-Or-CopyPublicDir([string]$SourcePublicDir, [string]$DestinationPublicDir, [switch]$CopyOnly) {
    if (Test-Path -LiteralPath $DestinationPublicDir) {
        return
    }

    Ensure-Directory (Split-Path $DestinationPublicDir -Parent)

    if (-not $CopyOnly) {
        try {
            & cmd /c "mklink /J `"$DestinationPublicDir`" `"$SourcePublicDir`"" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return
            }
        } catch {
        }
    }

    $null = & robocopy $SourcePublicDir $DestinationPublicDir /E /XJ /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to materialize $SourcePublicDir"
    }
}

$resolvedEngineRoot = Resolve-UE426Root -PreferredPath $EngineRoot
if ((Join-Path $resolvedEngineRoot 'Engine') -and (Test-Path -LiteralPath (Join-Path $resolvedEngineRoot 'Engine\Source'))) {
    $installRoot = $resolvedEngineRoot
} elseif ($resolvedEngineRoot.EndsWith('\Engine', [System.StringComparison]::OrdinalIgnoreCase)) {
    $installRoot = Split-Path $resolvedEngineRoot -Parent
} else {
    $installRoot = $resolvedEngineRoot
}

$searchRoots = @(
    (Join-Path $installRoot 'Engine\Source'),
    (Join-Path $installRoot 'Engine\Plugins')
)

Ensure-Directory $DestinationRoot

$moduleCount = 0
foreach ($root in $searchRoots) {
    if (-not (Test-Path -LiteralPath $root)) {
        continue
    }

    foreach ($buildFile in Get-ChildItem -LiteralPath $root -Recurse -Filter *.Build.cs -File) {
        $moduleName = [IO.Path]::GetFileNameWithoutExtension($buildFile.Name)
        $moduleDir = Split-Path $buildFile.FullName -Parent
        $publicDir = Join-Path $moduleDir 'Public'
        if (-not (Test-Path -LiteralPath $publicDir)) {
            continue
        }

        $destModuleRoot = Join-Path $DestinationRoot $moduleName
        $destPublicDir = Join-Path $destModuleRoot 'Public'
        Link-Or-CopyPublicDir -SourcePublicDir $publicDir -DestinationPublicDir $destPublicDir -CopyOnly:$CopyInsteadOfJunctions
        $moduleCount += 1
    }
}

Write-Host "Engine reference ready at $DestinationRoot ($moduleCount module public trees)" -ForegroundColor Green
