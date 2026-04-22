# Generation Pipeline

This is the high-level order for rebuilding the local RoboQuest modding workspace from this public repo on a new machine.

## Prerequisites

- RoboQuest installed locally
- Unreal Engine 4.26 installed locally
- Visual Studio Build Tools / MSVC
- Python 3
- git

## Step 1: Bootstrap External Source Trees

Run:

```powershell
$RepoRoot = (Resolve-Path '.').Path
& (Join-Path $RepoRoot 'tooling\setup\bootstrap_repo_workspace.ps1') -CloneExternalSources
```

This clones the open-source helper repos into:

- `tooling/external_sources`

## Step 2: Generate Local Outputs

The repo includes a direct collection script:

```powershell
& '.\tooling\setup\dump_modding_artifacts.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -LaunchForUht `
  -CollectExtrasIfPresent `
  -GeneratePakListing
```

That script can populate:

- `references/dumps`
- `references/ue4ss`
- `references/sdk_dump_tools`
- `references/sdk_generated`
- `references/paks`
- optional extra folders if they already exist under the local game root

Additional local references such as `kismet_json`, `pseudocode`, and `ida` are still separate workflows.

## Step 3: Generate The Editor Project

Preferred wrapper:

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build
```

When replacing an existing generated output tree, add `-Clean`. If the cached engine-header mirror looks stale after an engine reinstall, add `-RefreshEngineReference`.

The repo will auto-detect UE 4.26 unless you pass `-EngineRoot`.

Underlying scripts:

- `tooling/roboquest_scripts_snapshot/jmap_generate_uproject.py`
- `tooling/roboquest_scripts_snapshot/jmap_to_uht.py`

Useful references:

- `docs/04_editor_project_and_jmap.md`
- `docs/07_jmap_static_mirror_learnings.md`

Recommended output:

- `projects/RoboQuest_jmap_426_local`

## Step 4: Build The Editor Project

Use the UE 4.26 commands described in:

- `docs/04_editor_project_and_jmap.md`

## Step 5: Validate Runtime / Editor Paths

- check the working UE4SS runtime under `runtime/UE4SS_working_runtime/Win64`
- check the generated project under `projects/RoboQuest_jmap_426_local`
- review `references/dump_summary.json`
- review build logs in the generated project root
- use `docs/12_first_mods.md` to verify that both the runtime and sidecar pak paths work on your machine
