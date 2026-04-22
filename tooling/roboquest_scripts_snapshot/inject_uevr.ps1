# inject_uevr.ps1 — CreateRemoteThread + LoadLibraryA injector.
#
# Usage: .\inject_uevr.ps1 <target_exe_name_or_pid> <dll_path>
# Example: .\inject_uevr.ps1 RoboQuest-Win64-Shipping E:\Github\UEVR\build\bin\uevr\UEVRBackend.dll
#
# Works by:
#   1. Opening the target process with PROCESS_ALL_ACCESS.
#   2. Allocating writable memory inside the target for the DLL path string.
#   3. Writing the absolute DLL path into that allocation.
#   4. Creating a remote thread whose entry point is LoadLibraryA (from
#      kernel32.dll — same base address in every Win64 process) and whose
#      argument is the remote path.
#   5. Waiting briefly for the thread to return; LoadLibraryA returns the
#      module handle (or 0 on failure).
#
# No external tools required. Pure p/invoke against kernel32.

param(
    [Parameter(Mandatory=$true)] [string]$Target,
    [Parameter(Mandatory=$true)] [string]$DllPath
)

if (-not (Test-Path $DllPath)) { throw "DLL not found: $DllPath" }
$DllPath = (Resolve-Path $DllPath).Path

# Pick the PID
if ($Target -match '^\d+$') {
    $pidTarget = [int]$Target
    $proc = Get-Process -Id $pidTarget -ErrorAction Stop
} else {
    $name = $Target -replace '\.exe$',''
    $proc = Get-Process -Name $name -ErrorAction Stop | Select -First 1
    if (-not $proc) { throw "No process named $Target" }
    $pidTarget = $proc.Id
}
Write-Host "Target PID: $pidTarget ($($proc.ProcessName))"

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Diagnostics;

public class Injector {
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr OpenProcess(uint access, bool inheritHandle, int pid);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr VirtualAllocEx(IntPtr hProc, IntPtr addr, uint size, uint alloc, uint protect);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool WriteProcessMemory(IntPtr hProc, IntPtr addr, byte[] buf, uint size, IntPtr written);

    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Ansi)]
    public static extern IntPtr GetProcAddress(IntPtr hModule, string procName);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr GetModuleHandleA(string name);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern IntPtr CreateRemoteThread(IntPtr hProc, IntPtr attrs, uint stack, IntPtr startAddr, IntPtr param, uint flags, out uint tid);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern uint WaitForSingleObject(IntPtr h, uint ms);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetExitCodeThread(IntPtr h, out uint code);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool CloseHandle(IntPtr h);
}
"@

$PROCESS_ALL_ACCESS = 0x1F0FFF
$MEM_COMMIT_RESERVE = 0x3000
$PAGE_READWRITE = 0x04
$INFINITE = 0xFFFFFFFF

$hProc = [Injector]::OpenProcess($PROCESS_ALL_ACCESS, $false, $pidTarget)
if ($hProc -eq [IntPtr]::Zero) {
    throw "OpenProcess failed (err=$([System.Runtime.InteropServices.Marshal]::GetLastWin32Error()))"
}

$bytes = [System.Text.Encoding]::ASCII.GetBytes($DllPath + [char]0)
$remotePath = [Injector]::VirtualAllocEx($hProc, [IntPtr]::Zero, [uint32]$bytes.Length, $MEM_COMMIT_RESERVE, $PAGE_READWRITE)
if ($remotePath -eq [IntPtr]::Zero) { throw "VirtualAllocEx failed" }

$ok = [Injector]::WriteProcessMemory($hProc, $remotePath, $bytes, [uint32]$bytes.Length, [IntPtr]::Zero)
if (-not $ok) { throw "WriteProcessMemory failed (err=$([System.Runtime.InteropServices.Marshal]::GetLastWin32Error()))" }

$kernel = [Injector]::GetModuleHandleA("kernel32.dll")
$loadLib = [Injector]::GetProcAddress($kernel, "LoadLibraryA")
if ($loadLib -eq [IntPtr]::Zero) { throw "GetProcAddress(LoadLibraryA) failed" }

[uint32]$tid = 0
$hThread = [Injector]::CreateRemoteThread($hProc, [IntPtr]::Zero, 0, $loadLib, $remotePath, 0, [ref]$tid)
if ($hThread -eq [IntPtr]::Zero) { throw "CreateRemoteThread failed" }

Write-Host "Remote thread tid=$tid, waiting..."
$null = [Injector]::WaitForSingleObject($hThread, 30000)

[uint32]$code = 0
$null = [Injector]::GetExitCodeThread($hThread, [ref]$code)
Write-Host "LoadLibraryA return (truncated to 32-bit): 0x$($code.ToString('X'))"
[Injector]::CloseHandle($hThread) | Out-Null
[Injector]::CloseHandle($hProc) | Out-Null
Write-Host "Done."
