function Resolve-UE426Root {
    param(
        [string]$PreferredPath
    )

    $candidates = New-Object System.Collections.Generic.List[string]

    if ($PreferredPath) {
        $candidates.Add($PreferredPath)
    }

    if ($env:UE426_ROOT) {
        $candidates.Add($env:UE426_ROOT)
    }

    foreach ($path in @(
        'E:\Epic Games\UE_4.26',
        'D:\Epic Games\UE_4.26',
        'C:\Program Files\Epic Games\UE_4.26',
        'C:\Program Files (x86)\Epic Games\UE_4.26'
    )) {
        $candidates.Add($path)
    }

    foreach ($regPath in @(
        'HKLM:\SOFTWARE\EpicGames\Unreal Engine\4.26',
        'HKLM:\SOFTWARE\WOW6432Node\EpicGames\Unreal Engine\4.26'
    )) {
        try {
            $value = (Get-ItemProperty -Path $regPath -ErrorAction Stop).InstalledDirectory
            if ($value) {
                $candidates.Add($value)
            }
        } catch {
        }
    }

    foreach ($regPath in @(
        'HKCU:\SOFTWARE\Epic Games\Unreal Engine\Builds',
        'HKLM:\SOFTWARE\Epic Games\Unreal Engine\Builds'
    )) {
        try {
            $props = Get-ItemProperty -Path $regPath -ErrorAction Stop
            foreach ($property in $props.PSObject.Properties) {
                if ($property.Name -in 'PSPath', 'PSParentPath', 'PSChildName', 'PSDrive', 'PSProvider') {
                    continue
                }
                $value = [string]$property.Value
                if ($value -match 'UE_4\.26' -or $value -match '4\.26') {
                    $candidates.Add($value)
                }
            }
        } catch {
        }
    }

    foreach ($candidate in $candidates) {
        if (-not $candidate) {
            continue
        }

        $trimmed = $candidate.Trim('"')
        if (-not (Test-Path -LiteralPath $trimmed)) {
            continue
        }

        $resolved = (Resolve-Path -LiteralPath $trimmed).Path
        if (Test-Path -LiteralPath (Join-Path $resolved 'Engine\Binaries\Win64\UE4Editor.exe')) {
            return $resolved
        }
        if (Test-Path -LiteralPath (Join-Path $resolved 'Binaries\Win64\UE4Editor.exe')) {
            return (Split-Path $resolved -Parent)
        }
    }

    throw 'UE 4.26 could not be auto-detected. Pass -EngineRoot or set UE426_ROOT.'
}
