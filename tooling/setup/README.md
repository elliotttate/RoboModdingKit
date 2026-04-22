# Kit Setup

Use `bootstrap_repo_workspace.ps1` first to create the expected local folders for this repo.

Use `bootstrap_external_sources.ps1` to clone the external tool source trees on a fresh machine.

Use `dump_modding_artifacts.ps1` to point the repo at a local RoboQuest install and collect the useful modding outputs, including AES key candidates for encrypted pak inspection.

Use `generate_editor_project.ps1` to turn the collected dumps into a local UE 4.26 project. It auto-detects UE 4.26 unless you pass `-EngineRoot`. Re-runs against an existing output root should use `-Clean`, and stale engine-reference headers can be rebuilt with `-RefreshEngineReference`.

Use `doctor_moddingkit.ps1` before the rest of the pipeline if you want a quick environment report. Pass `-GeneratedProjectRoot` if your generated project lives somewhere other than the default local output path.

Use `package_mod.ps1`, `install_mod.ps1`, and `uninstall_mod.ps1` for the included sample mods or your own UE4SS/pak mod payloads. For pak mods, `package_mod.ps1` honors `mount_point`, `version`, `compression`, and `path_hash_seed` from `robomod.json` unless you override them on the command line.

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

Example sample pak packaging:

```powershell
& '.\tooling\setup\package_mod.ps1' `
  -SourcePath '.\templates\pak\HelloPakMod'
```

Example runtime restore:

```powershell
& '.\tooling\setup\restore_game_runtime_backup.ps1' `
  -GameRoot 'C:\Games\RoboQuest'
```
