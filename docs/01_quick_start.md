# Quick Start

## First Run On A Fresh Machine

1. Run:

```powershell
& '.\tooling\setup\bootstrap_repo_workspace.ps1' -CloneExternalSources
```

2. Install Unreal Engine 4.26.
3. Make sure RoboQuest is installed locally.
4. Run the doctor check:

```powershell
& '.\tooling\setup\doctor_moddingkit.ps1' `
  -GameRoot 'C:\Games\RoboQuest'
```

5. Dump the useful modding artifacts from your local game install:

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -LaunchForUht `
  -CollectExtrasIfPresent `
  -GeneratePakListing
```

6. Read `docs/10_generation_pipeline.md`.
7. Generate the local editor project:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build
```

If `projects/RoboQuest_jmap_426_local` already exists, rerun that command with `-Clean`.

8. Read `docs/12_first_mods.md` and try one of the included sample mods.

## If You Want A Working UE4SS Runtime

- Start in `runtime/UE4SS_working_runtime/Win64`
- Main files:
  - `UE4SS.dll`
  - `UE4SS-settings.ini`
  - `dwmapi.dll`
  - `Mods/`

This is the current known-good runtime setup used against RoboQuest. The `UHTHeaderDump` is not committed; generate it locally with the included `UHTDumper` mod or the dump script.

## If You Want To Rebuild The Editor Project

- Use `tooling/roboquest_scripts_snapshot/jmap_generate_uproject.py`
- Use `tooling/roboquest_scripts_snapshot/jmap_to_uht.py`
- Put local outputs under:
  - `references/`
  - `projects/`
- Engine target: UE 4.26

## If You Want The Tooling

- Ready-to-run binaries are in `tooling/bin`
- RoboQuest-specific helper scripts are in `tooling/roboquest_scripts_snapshot`
- SDK generation helpers are in `tooling/sdk_dump_tools_snapshot`
- External source trees can be cloned into `tooling/external_sources`
- Starter mods are in `templates`

## Suggested First Reading Order

1. `README.md`
2. `docs/02_kit_layout.md`
3. `docs/09_portable_repo.md`
4. `docs/10_generation_pipeline.md`
5. `docs/11_dump_from_game.md`
6. `docs/12_first_mods.md`
7. `docs/03_ue4ss_and_runtime.md`
8. `docs/04_editor_project_and_jmap.md`
9. `docs/05_dumps_sdk_assets.md`
10. `docs/06_tooling_reference.md`
11. `docs/13_troubleshooting.md`
12. `docs/07_jmap_static_mirror_learnings.md`
