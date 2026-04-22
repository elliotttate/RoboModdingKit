# RoboQuest Modding Kit

This repo is a public bootstrap workspace for RoboQuest modding and reverse-engineering on UE 4.26.2.

It includes:

- a working UE4SS v3.0.1 RoboQuest runtime patch set
- RoboQuest-specific generator and helper scripts
- an end-to-end dump script that can point at a local RoboQuest install and collect the useful modding artifacts
- a minimal SDK-generation tool snapshot
- small ready-to-run tool binaries
- setup/bootstrap scripts for a fresh machine
- documentation for rebuilding the local workspace from a user's own RoboQuest install
- the running notes from the `jmap` mirror work

It does not commit RoboQuest-derived dump trees, extracted assets, generated Unreal projects, or IDA databases. Those are meant to be regenerated locally from a user's own game install.

## Start Here

1. Read `docs/01_quick_start.md`.
2. Run `tooling/setup/bootstrap_repo_workspace.ps1 -CloneExternalSources`.
3. Run `tooling/setup/dump_modding_artifacts.ps1 -GameRoot '<your RoboQuest install root>' -LaunchForUht`.
4. Read `docs/10_generation_pipeline.md`.
5. Generate your local `projects/` outputs from the dumped data.

The setup scripts auto-detect UE 4.26 from common install paths, `UE426_ROOT`, and the Windows registry. Users only need to pass `-EngineRoot` when that auto-detection fails.

## What Is Included

- `runtime/`
  - Working UE4SS runtime files, release zips, and patch-analysis artifacts.
- `tooling/`
  - Tool binaries, RoboQuest helper script snapshot, SDK-generation snapshot, and setup scripts.
- `docs/`
  - Workflow docs, generation notes, and mirror learnings.
- `projects/`
  - Placeholder folder for locally generated Unreal projects.
- `references/`
  - Placeholder folder for locally generated dumps and SDK artifacts.
- `manifests/`
  - Small repo metadata notes.

## Key Included Files

- Working UE4SS runtime:
  - `runtime/UE4SS_working_runtime/Win64/UE4SS.dll`
- UE4SS patch-analysis snapshot:
  - `runtime/UE4SS_patch_analysis/`
- Generator scripts:
  - `tooling/roboquest_scripts_snapshot/jmap_generate_uproject.py`
  - `tooling/roboquest_scripts_snapshot/jmap_to_uht.py`
- Dump pipeline:
  - `tooling/setup/dump_modding_artifacts.ps1`
- SDK generation snapshot:
  - `tooling/sdk_dump_tools_snapshot/`
- Workspace bootstrap:
  - `tooling/setup/bootstrap_repo_workspace.ps1`
  - `tooling/setup/bootstrap_external_sources.ps1`
- Current learnings:
  - `docs/07_jmap_static_mirror_learnings.md`

## Local Prerequisites

- Unreal Engine 4.26
- Visual Studio Build Tools / MSVC usable by UE4
- Python 3.x
- git
- RoboQuest installed locally

## Scope

This repo is intended to help RoboQuest modders:

- patch and deploy UE4SS
- regenerate local dump/reference artifacts
- rebuild the `jmap`-generated UE 4.26 editor project
- inspect the current generator logic and notes

It is a builder/bootstrap repo, not a redistributable RoboQuest SDK.
