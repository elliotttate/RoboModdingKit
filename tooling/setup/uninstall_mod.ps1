param(
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [ValidateSet('Auto', 'Pak', 'UE4SS')]
    [string]$Type = 'Auto'
)

$ErrorActionPreference = 'Stop'

function Remove-ModEntry([string]$ModsTxtPath, [string]$ModName) {
    if (-not (Test-Path -LiteralPath $ModsTxtPath)) {
        return $false
    }
    $escapedName = [regex]::Escape($ModName)
    $lines = @(Get-Content -LiteralPath $ModsTxtPath)
    $filtered = @($lines | Where-Object { $_ -notmatch "^\s*$escapedName\s*:" })
    if ($filtered.Count -eq $lines.Count) {
        return $false
    }
    Set-Content -LiteralPath $ModsTxtPath -Value $filtered
    return $true
}

$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$modsRoot = Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64\Mods'
$modsTxtPath = Join-Path $modsRoot 'mods.txt'
$pakModsRoot = Join-Path $resolvedGameRoot 'RoboQuest\Content\Paks\~mods'

$removedUe4ss = $false
$removedPak = $false

if ($Type -in @('Auto', 'UE4SS')) {
    $modDir = Join-Path $modsRoot $Name
    $removedEntry = Remove-ModEntry -ModsTxtPath $modsTxtPath -ModName $Name
    if (Test-Path -LiteralPath $modDir) {
        Remove-Item -LiteralPath $modDir -Recurse -Force
        $removedUe4ss = $true
    } elseif ($removedEntry) {
        $removedUe4ss = $true
    }
    if ($removedUe4ss) {
        Write-Host "Removed UE4SS mod $Name" -ForegroundColor Green
    }
}

if ($Type -in @('Auto', 'Pak')) {
    foreach ($extension in @('.pak', '.sig')) {
        $pakPath = Join-Path $pakModsRoot ($Name + $extension)
        if (Test-Path -LiteralPath $pakPath) {
            Remove-Item -LiteralPath $pakPath -Force
            $removedPak = $true
        }
    }
    if ($removedPak) {
        Write-Host "Removed pak mod $Name" -ForegroundColor Green
    }
}

if (-not ($removedUe4ss -or $removedPak)) {
    Write-Warning "No installed mod named $Name was found."
}
