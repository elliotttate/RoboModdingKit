param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [string]$BackupFolderName = 'RoboModdingKit_backup'
)

$ErrorActionPreference = 'Stop'

$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$binRoot = Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64'
$backupRoot = Join-Path $binRoot $BackupFolderName

if (-not (Test-Path -LiteralPath $backupRoot)) {
    throw "Backup folder not found: $backupRoot"
}

$filesToRestore = @(
    'UE4SS.dll',
    'UE4SS-settings.ini',
    'dwmapi.dll'
)

foreach ($name in $filesToRestore) {
    $source = Join-Path $backupRoot $name
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $binRoot $name) -Force
        Write-Host "restored $name"
    } else {
        Write-Warning "Backup file missing: $source"
    }
}

$modsBackup = Join-Path $backupRoot 'Mods'
if (Test-Path -LiteralPath $modsBackup) {
    $modsTarget = Join-Path $binRoot 'Mods'
    New-Item -ItemType Directory -Path $modsTarget -Force | Out-Null
    $null = & robocopy $modsBackup $modsTarget /MIR /XJ /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to restore Mods from $modsBackup"
    }
    Write-Host 'restored Mods'
}

Write-Host ''
Write-Host "Restore complete from $backupRoot" -ForegroundColor Green
