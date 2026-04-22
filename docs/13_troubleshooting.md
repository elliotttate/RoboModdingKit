# Troubleshooting

## UE 4.26 Was Not Found

Run:

```powershell
& '.\tooling\setup\doctor_moddingkit.ps1' -GameRoot 'C:\Games\RoboQuest'
```

If auto-detection still fails, pass `-EngineRoot` explicitly to:

- `generate_editor_project.ps1`
- `materialize_engine_reference.ps1`

## dump_modding_artifacts.ps1 Fails Early

Check:

- Python 3 is installed
- RoboQuest is installed locally
- the game path points at the install root, not `Binaries\Win64`

The doctor script will catch all three.

## UE4SS Did Not Produce UHTHeaderDump

Check:

- the included runtime was deployed to `RoboQuest\Binaries\Win64`
- `UHTDumper` is enabled in `Mods\mods.txt`
- RoboQuest was launched through `dump_modding_artifacts.ps1 -LaunchForUht`

If RoboQuest stays open after `Calling exit()` appears in `UE4SS.log`, the dump script now force-terminates the launched process after the dump finishes.

## AES Candidates Were Found But No Key Verified

Check:

- `references/crypto/aes_candidates.json`
- `references/paks/*.error.txt`

If the base pak format changes, rerun `dump_modding_artifacts.ps1 -GeneratePakListing` and inspect the verification excerpts in `aes_candidates.json`.

## generate_editor_project.ps1 Says The Output Root Already Exists

Re-run with:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -Clean
```

The script refuses to delete a non-empty output tree unless `-Clean` is explicit.

## The Generated Project Builds But The Editor Does Not Open

Check:

- `projects\RoboQuest_jmap_426_local\Saved\Logs\RoboQuest.log`
- `references\ue4ss\UHTHeaderDump`
- `references\dump_summary.json`

The current generator is plugin-aware when `references/generated_project/Plugins` is available, so make sure `dump_modding_artifacts.ps1 -CollectExtrasIfPresent` has been run.

## A Sample Mod Did Not Install

For UE4SS sample mods:

- verify the folder exists under `RoboQuest\Binaries\Win64\Mods\<ModName>`
- verify `Mods\mods.txt` contains `<ModName> : 1`

For pak sample mods:

- verify the file exists under `RoboQuest\Content\Paks\~mods`
- list it with `repak.exe list`

## I Want To Revert The Runtime Changes

Run:

```powershell
& '.\tooling\setup\restore_game_runtime_backup.ps1' `
  -GameRoot 'C:\Games\RoboQuest'
```
