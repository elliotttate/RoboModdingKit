# Dump From Game

Use this when you want to point the repo at a local RoboQuest install and collect the most useful modding artifacts in one pass.

## Command

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -LaunchForUht `
  -CollectExtrasIfPresent `
  -GeneratePakListing
```

## What It Does

- deploys the included UE4SS runtime into `RoboQuest\Binaries\Win64`
- attaches `jmap_dumper.exe` to the running game if a process is available
- writes:
  - `references/dumps/RoboQuest.jmap`
  - `references/dumps/RoboQuest.all.jmap`
- scans the Shipping executable for AES key candidates and writes:
  - `references/crypto/aes_candidates.json`
- launches the game for a UE4SS-driven `UHTHeaderDump` when `-LaunchForUht` is supplied
- copies:
  - `references/ue4ss/UHTHeaderDump`
  - `references/ue4ss/UE4SS_ObjectDump.txt`
  - `references/ue4ss/UE4SS.log`
- regenerates:
  - `references/sdk_dump_tools/out/RoboQuest.generated.genny`
  - `references/sdk_generated`
- optionally copies game-side extras when already present:
  - `generated_project`
  - `sdk_dump_tools/project_generator_input`
  - `sdk_dump_tools/dumper7_output`
  - `sdk_dump_tools/WORKLOG.md`
- optionally writes `.pak` listings under `references/paks`, using the verified AES key when the base pak index is encrypted

## Notes

- If the game is already running before runtime deployment, `jmap` can still attach to it, but the UE4SS-generated outputs only reflect that session if UE4SS was already loaded.
- The script writes into `RoboQuest\Binaries\Win64` and backs up the first-run copies of `UE4SS.dll`, `UE4SS-settings.ini`, `dwmapi.dll`, and the existing `Mods` tree under `RoboModdingKit_backup`.
- Use `tooling/setup/restore_game_runtime_backup.ps1` if you want to put those original runtime files and the backed-up `Mods` tree back.
- `references/crypto/aes_candidates.json` ranks unique candidates by entropy and records which key, if any, was verified against a local pak via `repak`.
- The cleanest full run is:
  1. close RoboQuest
  2. run the script with `-LaunchForUht`
  3. let the script launch RoboQuest and let `UHTDumper` exit it
- The script writes `references/dump_summary.json` so you can confirm which outputs were produced.
- Pak listing failures are written next to the generated `.list.txt` / `.info.txt` files instead of flooding the console.
