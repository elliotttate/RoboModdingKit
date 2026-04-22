# Dumps, SDK, And Asset References

The fastest way to populate most of this folder is:

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -LaunchForUht `
  -CollectExtrasIfPresent `
  -GeneratePakListing
```

## Dumps

Primary local dump set:

- `references/dumps`

Typical files there:

- `RoboQuest.jmap`
- `RoboQuest.all.jmap`

## UE4SS Output

- `references/ue4ss`

Useful files:

- `UHTHeaderDump/`
- `UE4SS_ObjectDump.txt`
- `UE4SS.log`

## Crypto / Pak Keys

- `references/crypto`

Useful files:

- `aes_candidates.json`

This contains ranked AES key candidates recovered from the Shipping executable. When a local pak is available, the dump pipeline also records which candidate was verified with `repak`.

## Blueprint JSON

- `references/kismet_json`

Use this for Blueprint bytecode analysis and cross-checking reflected behavior.

## Pseudocode

- `references/pseudocode`

Use this for recovered native function context from Hex-Rays exports.

## Flat SDK Output

- `references/sdk_generated`

This is useful for:

- flat type/header names
- checking whether a type exists in the game dump surface
- quick external type references

It is not a clean Unreal-compilable source tree.

## sdk_dump_tools Workspace

- `references/sdk_dump_tools`

Use this for the intermediate `.genny` output and any copied game-side sdk dump extras.

## IDA Material

- `references/ida`

This contains the IDA database and related analysis artifacts when you generate or copy them locally.

## Asset Extraction / Packaging Tools

Relevant binaries:

- `tooling/bin/repak.exe`
- `tooling/bin/retoc.exe`
- `tooling/bin/kismet-analyzer.exe`
- `tooling/bin/jmap_dumper.exe`

Relevant cloned sources:

- `tooling/external_sources/repak`
- `tooling/external_sources/retoc`
- `tooling/external_sources/kismet-analyzer`

Relevant local snapshot:

- `tooling/sdk_dump_tools_snapshot`

## Useful Commands

Example `repak` listing:

```powershell
$RepoRoot = (Resolve-Path '.').Path
& (Join-Path $RepoRoot 'tooling\bin\repak.exe') `
  -a '<aes key>' `
  list 'C:\Path\To\RoboQuest-WindowsNoEditor.pak'
```

Example `retoc` help:

```powershell
$RepoRoot = (Resolve-Path '.').Path
& (Join-Path $RepoRoot 'tooling\bin\retoc.exe') --help
```

Example `kismet-analyzer` run shape:

```powershell
$RepoRoot = (Resolve-Path '.').Path
& (Join-Path $RepoRoot 'tooling\bin\kismet-analyzer.exe') --help
```
