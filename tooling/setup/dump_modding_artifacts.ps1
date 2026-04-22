param(
    [string]$RepoRoot,
    [Parameter(Mandatory = $true)]
    [string]$GameRoot,
    [string]$GameProcessName = 'RoboQuest-Win64-Shipping',
    [int]$ProcessId,
    [switch]$LaunchForUht,
    [switch]$SkipJmap,
    [switch]$SkipSdk,
    [switch]$CollectExtrasIfPresent,
    [switch]$GeneratePakListing
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Ensure-Directory([string]$Path) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Set-ModEnabled([string]$ModsTxtPath, [string]$ModName, [bool]$Enabled) {
    $lines = @()
    if (Test-Path -LiteralPath $ModsTxtPath) {
        $lines = Get-Content -LiteralPath $ModsTxtPath
    }

    $escapedName = [regex]::Escape($ModName)
    $replacement = if ($Enabled) { "$ModName : 1" } else { "$ModName : 0" }
    $updated = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match "^\s*$escapedName\s*:") {
            $lines[$index] = $replacement
            $updated = $true
        }
    }

    if (-not $updated) {
        $lines += $replacement
    }

    Set-Content -LiteralPath $ModsTxtPath -Value $lines
}

function Copy-Tree([string]$Source, [string]$Destination) {
    Ensure-Directory $Destination
    $null = & robocopy $Source $Destination /E /XJ /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed: $Source -> $Destination"
    }
}

function Backup-IfExists([string]$SourcePath, [string]$BackupRoot) {
    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
    }

    Ensure-Directory $BackupRoot
    $name = Split-Path $SourcePath -Leaf
    $backupPath = Join-Path $BackupRoot $name
    if (-not (Test-Path -LiteralPath $backupPath)) {
        Copy-Item -LiteralPath $SourcePath -Destination $backupPath -Force
    }
}

function Backup-TreeIfExists([string]$SourcePath, [string]$BackupRoot) {
    if (-not (Test-Path -LiteralPath $SourcePath)) {
        return
    }

    Ensure-Directory $BackupRoot
    $name = Split-Path $SourcePath -Leaf
    $backupPath = Join-Path $BackupRoot $name
    if (-not (Test-Path -LiteralPath $backupPath)) {
        Copy-Tree $SourcePath $backupPath
    }
}

function Get-GameProcess([string]$Name, [int]$ExplicitProcessId) {
    if ($ExplicitProcessId) {
        return Get-Process -Id $ExplicitProcessId -ErrorAction SilentlyContinue
    }

    $lookup = $Name
    if ($lookup.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        $lookup = [System.IO.Path]::GetFileNameWithoutExtension($lookup)
    }

    return Get-Process -Name $lookup -ErrorAction SilentlyContinue |
        Sort-Object StartTime -Descending |
        Select-Object -First 1
}

function Wait-ForPath([string]$Path, [int]$TimeoutSeconds = 180) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $Path) {
            return $true
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Test-FileContainsPattern([string]$Path, [string]$Pattern) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    return [bool](Select-String -Path $Path -Pattern $Pattern -Quiet -ErrorAction SilentlyContinue)
}

function Stop-ProcessTreeById([int]$Id) {
    $null = & cmd /c "taskkill /PID $Id /T /F"
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Checked([string]$FilePath, [string[]]$Arguments) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Invoke-BestEffort([string]$FilePath, [string[]]$Arguments, [string]$FailureMessage) {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$FailureMessage`nCommand: $FilePath $($Arguments -join ' ')"
        return $false
    }
    return $true
}

function Invoke-RepakCapture([string]$RepakPath, [string[]]$ArgumentList, [string]$OutPath, [string]$ErrorPath) {
    if (Test-Path -LiteralPath $OutPath) {
        Remove-Item -LiteralPath $OutPath -Force
    }
    if (Test-Path -LiteralPath $ErrorPath) {
        Remove-Item -LiteralPath $ErrorPath -Force
    }

    $proc = Start-Process -FilePath $RepakPath `
        -ArgumentList $ArgumentList `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $OutPath `
        -RedirectStandardError $ErrorPath

    if ($proc.ExitCode -ne 0) {
        return $false
    }

    if ((Test-Path -LiteralPath $ErrorPath) -and ((Get-Item -LiteralPath $ErrorPath).Length -eq 0)) {
        Remove-Item -LiteralPath $ErrorPath -Force
    }
    return $true
}

function Get-PakFilesUnderGameRoot([string]$ResolvedGameRoot) {
    $pakSearchRoots = @(
        (Join-Path $ResolvedGameRoot 'RoboQuest\Content\Paks'),
        (Join-Path $ResolvedGameRoot 'RoboQuest\Saved\Paks'),
        (Join-Path $ResolvedGameRoot 'Content\Paks')
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -Unique

    $pakFiles = foreach ($root in $pakSearchRoots) {
        Get-ChildItem -LiteralPath $root -Recurse -Filter *.pak -File -ErrorAction SilentlyContinue
    }
    $pakFiles = $pakFiles | Sort-Object FullName -Unique
    if (-not $pakFiles) {
        $pakFiles = Get-ChildItem -LiteralPath $ResolvedGameRoot -Recurse -Filter *.pak -File -ErrorAction SilentlyContinue |
            Sort-Object FullName -Unique
    }
    return @($pakFiles)
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

$resolvedGameRoot = (Resolve-Path -LiteralPath $GameRoot).Path
$pythonCommand = Resolve-PythonCommand
$binRoot = Join-Path $resolvedGameRoot 'RoboQuest\Binaries\Win64'
$gameExe = if ($GameProcessName.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
    $GameProcessName
} else {
    "$GameProcessName.exe"
}
$exePath = Join-Path $binRoot $gameExe
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Game executable not found: $exePath"
}

$runtimeSource = Join-Path $RepoRoot 'runtime\UE4SS_working_runtime\Win64'
$jmapExe = Join-Path $RepoRoot 'tooling\bin\jmap_dumper.exe'
$repakExe = Join-Path $RepoRoot 'tooling\bin\repak.exe'
$sdkSnapshotRoot = Join-Path $RepoRoot 'tooling\sdk_dump_tools_snapshot'
$sdkEmitterExe = Join-Path $sdkSnapshotRoot 'bin\rq_sdkgenny_emit.exe'
$env:PATTERNSLEUTH_RES_EngineVersion = '4.26'

$referencesRoot = Join-Path $RepoRoot 'references'
$dumpsRoot = Join-Path $referencesRoot 'dumps'
$cryptoRoot = Join-Path $referencesRoot 'crypto'
$ue4ssRoot = Join-Path $referencesRoot 'ue4ss'
$sdkWorkRoot = Join-Path $referencesRoot 'sdk_dump_tools'
$sdkOutRoot = Join-Path $referencesRoot 'sdk_generated'
$pakRoot = Join-Path $referencesRoot 'paks'

Ensure-Directory $referencesRoot
Ensure-Directory $dumpsRoot
Ensure-Directory $cryptoRoot
Ensure-Directory $ue4ssRoot
Ensure-Directory $sdkWorkRoot
Ensure-Directory $sdkOutRoot

$gameUhtRoot = Join-Path $binRoot 'UHTHeaderDump'
$gameObjectDump = Join-Path $binRoot 'UE4SS_ObjectDump.txt'
$gameUe4ssLog = Join-Path $binRoot 'UE4SS.log'
$backupRoot = Join-Path $binRoot 'RoboModdingKit_backup'
$modsTxtPath = Join-Path $binRoot 'Mods\mods.txt'
$uhtDumperTemporarilyEnabled = $false

Write-Step 'Deploying the included UE4SS runtime'
Write-Warning "This step writes into $binRoot and may overwrite UE4SS.dll, UE4SS-settings.ini, dwmapi.dll, and files under Mods. Existing files are backed up on first run under $backupRoot."
Backup-IfExists (Join-Path $binRoot 'UE4SS.dll') $backupRoot
Backup-IfExists (Join-Path $binRoot 'UE4SS-settings.ini') $backupRoot
Backup-IfExists (Join-Path $binRoot 'dwmapi.dll') $backupRoot
Backup-TreeIfExists (Join-Path $binRoot 'Mods') $backupRoot
Copy-Tree $runtimeSource $binRoot
if ($LaunchForUht) {
    Set-ModEnabled -ModsTxtPath $modsTxtPath -ModName 'UHTDumper' -Enabled $true
    $uhtDumperTemporarilyEnabled = $true
}

$gameProcess = Get-GameProcess -Name $GameProcessName -ExplicitProcessId $ProcessId

if (-not $SkipJmap -and -not $gameProcess) {
    Write-Warning 'No running RoboQuest process found for jmap. Start the game first, or use -LaunchForUht so the script can launch it.'
}

$launchedProcess = $null
if ($LaunchForUht -and -not $gameProcess) {
    Write-Step 'Launching RoboQuest to let UE4SS generate UHT/Object dumps'
    $launchedProcess = Start-Process -FilePath $exePath -PassThru
    Start-Sleep -Seconds 15
    $gameProcess = Get-GameProcess -Name $GameProcessName -ExplicitProcessId $launchedProcess.Id
}

if (-not $SkipJmap -and $gameProcess) {
    Write-Step "Dumping jmap from PID $($gameProcess.Id)"
    Invoke-BestEffort $jmapExe @('--pid', $gameProcess.Id.ToString(), (Join-Path $dumpsRoot 'RoboQuest.jmap')) 'Native jmap dump failed.'
    Invoke-BestEffort $jmapExe @('--pid', $gameProcess.Id.ToString(), '--all', (Join-Path $dumpsRoot 'RoboQuest.all.jmap')) 'The --all jmap dump failed; continuing with the rest of the pipeline.'
}

if ($LaunchForUht) {
    if ($launchedProcess) {
        Write-Step 'Waiting for the UE4SS UHT dumper to finish and exit the game'
        $deadline = (Get-Date).AddSeconds(240)
        $exitRequestedAt = $null
        $timedOut = $true
        while ((Get-Date) -lt $deadline) {
            $running = Get-Process -Id $launchedProcess.Id -ErrorAction SilentlyContinue
            if (-not $running) {
                $timedOut = $false
                break
            }

            if (-not $exitRequestedAt -and (Test-FileContainsPattern -Path $gameUe4ssLog -Pattern 'Calling exit\(\)')) {
                $exitRequestedAt = Get-Date
            }

            if ($exitRequestedAt -and ((Get-Date) - $exitRequestedAt).TotalSeconds -ge 10) {
                Write-Warning 'UE4SS requested shutdown but RoboQuest stayed open. Terminating the launched process.'
                if (Stop-ProcessTreeById -Id $launchedProcess.Id) {
                    try {
                        Wait-Process -Id $launchedProcess.Id -Timeout 15 -ErrorAction Stop
                    } catch {
                    }
                    $timedOut = $false
                }
                break
            }

            Start-Sleep -Seconds 2
        }

        if ($timedOut -and (Get-Process -Id $launchedProcess.Id -ErrorAction SilentlyContinue)) {
            Write-Warning 'Timed out waiting for the launched game process to exit. Continuing with whatever dump files already exist.'
        }
    } elseif ($gameProcess) {
        Write-Warning 'A RoboQuest process was already running before runtime deployment. UHT/Object dumps only reflect that session if UE4SS was already loaded.'
    }

    Write-Step 'Collecting UE4SS outputs'
    if (Wait-ForPath -Path $gameUhtRoot -TimeoutSeconds 20) {
        Copy-Tree $gameUhtRoot (Join-Path $ue4ssRoot 'UHTHeaderDump')
    } else {
        Write-Warning "UHTHeaderDump was not found at $gameUhtRoot"
    }

    if (Test-Path -LiteralPath $gameObjectDump) {
        Copy-Item -LiteralPath $gameObjectDump -Destination (Join-Path $ue4ssRoot 'UE4SS_ObjectDump.txt') -Force
    } else {
        Write-Warning "UE4SS_ObjectDump.txt was not found at $gameObjectDump"
    }

    if (Test-Path -LiteralPath $gameUe4ssLog) {
        Copy-Item -LiteralPath $gameUe4ssLog -Destination (Join-Path $ue4ssRoot 'UE4SS.log') -Force
    }

    if ($uhtDumperTemporarilyEnabled) {
        Set-ModEnabled -ModsTxtPath $modsTxtPath -ModName 'UHTDumper' -Enabled $false
        $uhtDumperTemporarilyEnabled = $false
    }
}

if (-not $SkipSdk) {
    $localUhtRoot = Join-Path $ue4ssRoot 'UHTHeaderDump'
    $localObjectDump = Join-Path $ue4ssRoot 'UE4SS_ObjectDump.txt'
    if ((Test-Path -LiteralPath $localUhtRoot) -and (Test-Path -LiteralPath $localObjectDump)) {
        Write-Step 'Generating flat SDK artifacts from the UE4SS dump'
        $sdkOutDir = Join-Path $sdkWorkRoot 'out'
        Ensure-Directory $sdkOutDir
        $gennyPath = Join-Path $sdkOutDir 'RoboQuest.generated.genny'

        Invoke-Checked $pythonCommand.FilePath (@($pythonCommand.PrefixArguments) + @(
            (Join-Path $sdkSnapshotRoot 'emit_genny_from_ue4ss.py'),
            '--uht-root', $localUhtRoot,
            '--object-dump', $localObjectDump,
            '--modules', 'RoboQuest', 'RyseUpTool',
            '--output', $gennyPath
        ))

        Remove-Item -LiteralPath $sdkOutRoot -Recurse -Force -ErrorAction SilentlyContinue
        Ensure-Directory $sdkOutRoot
        Invoke-Checked $sdkEmitterExe @($gennyPath, $sdkOutRoot)

        Invoke-Checked $pythonCommand.FilePath (@($pythonCommand.PrefixArguments) + @(
            (Join-Path $sdkSnapshotRoot 'postprocess_generated_sdk.py'),
            '--genny', $gennyPath,
            '--sdk-root', $sdkOutRoot
        ))
    } else {
        Write-Warning 'Skipping SDK generation because the local UHT dump and object dump were not both available.'
    }
}

$aesJsonPath = Join-Path $cryptoRoot 'aes_candidates.json'
$verifiedAesKey = $null
$pakFiles = Get-PakFilesUnderGameRoot -ResolvedGameRoot $resolvedGameRoot
$aesVerificationPak = $pakFiles | Sort-Object Length -Descending | Select-Object -First 1

Write-Step 'Scanning the shipping executable for AES key candidates'
$aesArgs = @(
    (Join-Path $RepoRoot 'tooling\setup\dump_aes_keys.py'),
    '--exe', $exePath,
    '--output', $aesJsonPath
)
if ($aesVerificationPak) {
    $aesArgs += @(
        '--verify-pak', $aesVerificationPak.FullName,
        '--repak', $repakExe
    )
}

if (-not (Invoke-BestEffort $pythonCommand.FilePath (@($pythonCommand.PrefixArguments) + $aesArgs) 'AES candidate scan failed; continuing without AES metadata.')) {
    $verifiedAesKey = $null
} elseif (Test-Path -LiteralPath $aesJsonPath) {
    try {
        $aesSummary = Get-Content -LiteralPath $aesJsonPath -Raw | ConvertFrom-Json
        if ($aesSummary.verified_key) {
            $verifiedAesKey = [string]$aesSummary.verified_key
            Write-Host "Verified AES key recovered for pak inspection." -ForegroundColor Green
        }
    } catch {
        Write-Warning "Failed to parse AES candidate output from $aesJsonPath"
    }
}

if ($GeneratePakListing) {
    Write-Step 'Generating pak listings'
    Ensure-Directory $pakRoot
    foreach ($pak in $pakFiles) {
        $safeName = [IO.Path]::GetFileNameWithoutExtension($pak.Name)
        $listPath = Join-Path $pakRoot ($safeName + '.list.txt')
        $infoPath = Join-Path $pakRoot ($safeName + '.info.txt')
        $listErrorPath = Join-Path $pakRoot ($safeName + '.list.error.txt')
        $infoErrorPath = Join-Path $pakRoot ($safeName + '.info.error.txt')

        if (Test-Path -LiteralPath $listPath) {
            Remove-Item -LiteralPath $listPath -Force
        }
        if (Test-Path -LiteralPath $infoPath) {
            Remove-Item -LiteralPath $infoPath -Force
        }
        if (Test-Path -LiteralPath $listErrorPath) {
            Remove-Item -LiteralPath $listErrorPath -Force
        }
        if (Test-Path -LiteralPath $infoErrorPath) {
            Remove-Item -LiteralPath $infoErrorPath -Force
        }

        $repakArgsPrefix = @()
        if ($verifiedAesKey) {
            $repakArgsPrefix = @('-a', $verifiedAesKey)
        }

        $listOk = Invoke-RepakCapture $repakExe @($repakArgsPrefix + @('list', $pak.FullName)) $listPath $listErrorPath
        $infoOk = Invoke-RepakCapture $repakExe @($repakArgsPrefix + @('info', $pak.FullName)) $infoPath $infoErrorPath
        if (-not ($listOk -and $infoOk)) {
            Write-Warning "repak could not fully inspect $($pak.FullName). Error output was written next to the generated pak listing files."
        }
    }
}

if ($CollectExtrasIfPresent) {
    Write-Step 'Collecting optional game-side extras when present'

    $extraMap = @(
        @{ Source = (Join-Path $resolvedGameRoot 'generated_project'); Destination = (Join-Path $referencesRoot 'generated_project') },
        @{ Source = (Join-Path $resolvedGameRoot 'sdk_dump_tools\project_generator_input'); Destination = (Join-Path $referencesRoot 'project_generator_input') },
        @{ Source = (Join-Path $resolvedGameRoot 'sdk_dump_tools\dumper7_output'); Destination = (Join-Path $referencesRoot 'dumper7_output') }
    )

    foreach ($entry in $extraMap) {
        if (Test-Path -LiteralPath $entry.Source) {
            Copy-Tree $entry.Source $entry.Destination
        }
    }

    $worklogPath = Join-Path $resolvedGameRoot 'sdk_dump_tools\WORKLOG.md'
    if (Test-Path -LiteralPath $worklogPath) {
        Ensure-Directory (Join-Path $referencesRoot 'sdk_dump_tools')
        Copy-Item -LiteralPath $worklogPath -Destination (Join-Path $referencesRoot 'sdk_dump_tools\WORKLOG.md') -Force
    }
}

$summary = [ordered]@{
    game_root = $resolvedGameRoot
    generated_at = (Get-Date).ToString('s')
    outputs = [ordered]@{
        jmap = (Test-Path -LiteralPath (Join-Path $dumpsRoot 'RoboQuest.jmap'))
        jmap_all = (Test-Path -LiteralPath (Join-Path $dumpsRoot 'RoboQuest.all.jmap'))
        aes_candidates = (Test-Path -LiteralPath $aesJsonPath)
        aes_verified_key = [bool]$verifiedAesKey
        ue4ss_uht_dump = (Test-Path -LiteralPath (Join-Path $ue4ssRoot 'UHTHeaderDump'))
        ue4ss_object_dump = (Test-Path -LiteralPath (Join-Path $ue4ssRoot 'UE4SS_ObjectDump.txt'))
        sdk_generated = (Test-Path -LiteralPath $sdkOutRoot) -and ((Get-ChildItem -LiteralPath $sdkOutRoot -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)
        pak_listings = (Test-Path -LiteralPath $pakRoot)
    }
}
$summaryPath = Join-Path $referencesRoot 'dump_summary.json'
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath

Write-Host ''
Write-Host "Dump summary written to $summaryPath" -ForegroundColor Green
