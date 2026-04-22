# UE4SS And Runtime

## Working Runtime Copy

The working runtime copy is:

- `runtime/UE4SS_working_runtime/Win64`

Important files:

- `UE4SS.dll`
- `UE4SS-settings.ini`
- `dwmapi.dll`
- `Mods/`

## Why This Runtime Matters

This setup contains the UE4SS v3.0.1 path that was patched to get RoboQuest past the `FText::FText(FString&&)` scan problem in this shipping build.

Reference artifacts:

- `runtime/UE4SS_patch_analysis/UE4SS_original.dll`
- `runtime/UE4SS_patch_analysis/ftext_patch_plan.json`
- `runtime/UE4SS_patch_analysis/*.log`

## UE4SS Source / Patch Workspace

If you want the source-side patch tree and build workspace, clone the external sources:

- `tooling/setup/bootstrap_external_sources.ps1`
- `tooling/external_sources/RE-UE4SS-v301`

## UE4SS Release Archives

Included for reference:

- `runtime/ue4ss_release_zips/UE4SS_v3.0.1.zip`
- `runtime/ue4ss_release_zips/UE4SS_v3.0.1-946-g265115c0.zip`

## UHT Dump

The UE4SS UHT dump is not committed in this public repo. Generate it locally by deploying the runtime and enabling `UHTDumper`.

That dump is useful for:

- real C++ class/type spellings
- header basenames
- delegate headers
- reflected include hints

## Typical Runtime Deployment

If you want to apply the working runtime to a RoboQuest install, the main files to compare or deploy are:

- `UE4SS.dll`
- `UE4SS-settings.ini`
- `dwmapi.dll`
- `Mods/`

The kit copy is a reference deployment. Check the current target game's `Binaries/Win64` folder before overwriting anything.

## Notes

- The runtime folder is a working local reference, not a full copied game install.
- If you deploy it into another RoboQuest install, keep the game-specific loader setup consistent.
- The included `UE4SS-settings.ini` keeps crash dumping enabled. UE4SS minidumps are written into `RoboQuest\Binaries\Win64` as `crash_*.dmp` when the runtime crashes.
- `runtime/UE4SS_patch_analysis/ftext_patch_plan.json` records the expected input/output SHA-256 values for the known-good UE4SS patch path so automated patchers can reject mismatched inputs.
