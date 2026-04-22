# Editor Project And jmap

## Goal

Generate a local UE 4.26 project mirror from RoboQuest dumps and the UE4SS UHT dump.

Recommended local output:

- `projects/RoboQuest_jmap_426_local`

## Required Inputs

- `references/dumps/RoboQuest.jmap` or `references/dumps/RoboQuest.all.jmap`
- UE4SS `UHTHeaderDump` generated locally from your RoboQuest install
- Unreal Engine 4.26

The repo can auto-detect UE 4.26 from common install locations, `UE426_ROOT`, or Windows registry entries. Only pass `-EngineRoot` if auto-detection fails.

## Preferred Wrapper Scripts

Materialize the engine-reference tree from your installed UE 4.26:

```powershell
& '.\tooling\setup\materialize_engine_reference.ps1'
```

Generate the local project:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles
```

Generate and build in one pass:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build
```

Generate, build, and include the bundled Suzie plugin plus `Content/DynamicClasses/RoboQuest.jmap`:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build
```

Skip Suzie installation if you only want the static mirror:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -SkipSuzie -GenerateProjectFiles -Build
```

If auto-detection fails:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' `
  -EngineRoot 'D:\Epic Games\UE_4.26' `
  -GenerateProjectFiles `
  -Build
```

## What The Wrapper Does

- auto-detects UE 4.26 unless `-EngineRoot` is provided
- materializes `tooling/generated/engine_module_reference` from the installed engine
- picks the best available dump in `references/dumps`
- uses `references/ue4ss/UHTHeaderDump`
- uses copied config from `references/generated_project` when available
- uses copied plugin descriptors from `references/generated_project/Plugins` when available, so project-owned plugin modules emit under `Plugins/` instead of being flattened into `Source/`
- writes the local Unreal project to `projects/RoboQuest_jmap_426_local`
- installs the bundled `templates/plugins/Suzie` plugin unless `-SkipSuzie` is passed
- copies a local RoboQuest `.jmap` dump to `Content/DynamicClasses/RoboQuest.jmap` for the Suzie workflow
- optionally runs UBT project-file generation and a full editor build

## Manual Script Entry Points

The underlying scripts are:

- `tooling/roboquest_scripts_snapshot/jmap_generate_uproject.py`
- `tooling/roboquest_scripts_snapshot/jmap_to_uht.py`

## External jmap Tooling

- `tooling/bin/jmap_dumper.exe`
- `tooling/external_sources/jmap`

## Main jmap Mirror Learnings

The current notes file is:

- `docs/07_jmap_static_mirror_learnings.md`

That document records the major generator fixes, include canonicalization rules, and 4.26-specific build/editor findings.

For the dynamic-class path, see:

- `docs/14_suzie_dynamic_classes.md`
