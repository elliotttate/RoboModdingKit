# Dump From Game

Use this when you want to point the repo at a local RoboQuest install and collect the most useful modding artifacts in one pass.

## Command

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'E:\SteamLibrary\steamapps\common\RoboQuest' `
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
- optionally writes `.pak` listings under `references/paks`

## Notes

- If the game is already running before runtime deployment, `jmap` can still attach to it, but the UE4SS-generated outputs only reflect that session if UE4SS was already loaded.
- The cleanest full run is:
  1. close RoboQuest
  2. run the script with `-LaunchForUht`
  3. let the script launch RoboQuest and let `UHTDumper` exit it
- The script writes `references/dump_summary.json` so you can confirm which outputs were produced.
