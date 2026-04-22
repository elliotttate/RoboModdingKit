# Kit Setup

Use `bootstrap_repo_workspace.ps1` first to create the expected local folders for this repo.

Use `bootstrap_external_sources.ps1` to clone the external tool source trees on a fresh machine.

Use `dump_modding_artifacts.ps1` to point the repo at a local RoboQuest install and collect the useful modding outputs.

Use `generate_editor_project.ps1` to turn the collected dumps into a local UE 4.26 project. It auto-detects UE 4.26 unless you pass `-EngineRoot`.

Example workspace bootstrap:

```powershell
& '.\tooling\setup\bootstrap_repo_workspace.ps1' -CloneExternalSources
```

Example dump run:

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'E:\SteamLibrary\steamapps\common\RoboQuest' `
  -LaunchForUht `
  -CollectExtrasIfPresent `
  -GeneratePakListing
```

Example project generation:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build
```
