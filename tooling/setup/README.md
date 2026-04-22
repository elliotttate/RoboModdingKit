# Kit Setup

Use `bootstrap_repo_workspace.ps1` first to create the expected local folders for this repo.

Use `bootstrap_external_sources.ps1` to clone the external tool source trees on a fresh machine.

Use `dump_modding_artifacts.ps1` to point the repo at a local RoboQuest install and collect the useful modding outputs, including AES key candidates for encrypted pak inspection.

Use `generate_editor_project.ps1` to turn the collected dumps into a local UE 4.26 project. It auto-detects UE 4.26 unless you pass `-EngineRoot`. Re-runs against an existing output root should use `-Clean`, and stale engine-reference headers can be rebuilt with `-RefreshEngineReference`.

Use `restore_game_runtime_backup.ps1` to put the original `UE4SS.dll`, `UE4SS-settings.ini`, `dwmapi.dll`, and backed-up `Mods` tree back into the game after a dump run if you want to revert the runtime deployment.

Example workspace bootstrap:

```powershell
& '.\tooling\setup\bootstrap_repo_workspace.ps1' -CloneExternalSources
```

Example dump run:

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -LaunchForUht `
  -CollectExtrasIfPresent `
  -GeneratePakListing
```

Example project generation:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build -Clean
```

Example runtime restore:

```powershell
& '.\tooling\setup\restore_game_runtime_backup.ps1' `
  -GameRoot 'C:\Games\RoboQuest'
```
