# Kit Layout

## `runtime/`

- `UE4SS_working_runtime/`
  - Copied working UE4SS runtime files and Mods folder.
- `UE4SS_patch_analysis/`
  - Patched/original DLLs and patch logs/plans.
- `ue4ss_release_zips/`
  - Copied UE4SS release and experimental zip files.

## `projects/`

- Placeholder for locally generated Unreal projects.
- Recommended output:
  - `projects/RoboQuest_jmap_426_local`

## `references/`

- Placeholder for local dump/reference outputs generated from the user's own RoboQuest install.
- Typical local subfolders:
  - `references/dumps`
  - `references/ue4ss`
  - `references/sdk_dump_tools`
  - `references/sdk_generated`
  - `references/kismet_json`
  - `references/pseudocode`
  - `references/sdk_dump_tools`
  - `references/ida`
  - `references/paks`

## `tooling/`

- `bin`
  - `jmap_dumper.exe`
  - `repak.exe`
  - `retoc.exe`
  - `kismet-analyzer.exe`
- `roboquest_scripts_snapshot`
  - Copied snapshot of the core RoboQuest helper scripts, including the `jmap` generator.
- `sdk_dump_tools_snapshot`
  - Minimal SDK-generation snapshot used to rebuild `references/sdk_generated` from UE4SS outputs.
- `setup`
  - Repo bootstrap helpers and local-layout helpers.
- `external_sources`
  - Local clone destination for open-source dependencies.

## `templates/`

- `ue4ss/HelloRoboLogMod`
  - minimal log-writing UE4SS sample mod
- `pak/HelloPakMod`
  - minimal sidecar pak sample mod staging tree

## `docs/`

- Top-level usage and workflow docs.

## `manifests/`

- Small repo metadata notes.
