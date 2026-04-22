# RoboQuest Modding Kit

This repo is a public bootstrap workspace for RoboQuest modding and reverse-engineering on UE 4.26.2.

It includes:

- a working UE4SS v3.0.1 RoboQuest runtime patch set
- RoboQuest-specific generator and helper scripts
- a bundled Suzie plugin snapshot patched for RoboQuest on UE 4.26
- sample mod templates for UE4SS, sidecar `.pak` workflows, and larger content-mod scaffolds
- an end-to-end dump script that can point at a local RoboQuest install, recover AES candidates, and collect the useful modding artifacts
- a minimal SDK-generation tool snapshot
- small ready-to-run tool binaries
- setup/bootstrap scripts for a fresh machine
- documentation for rebuilding the local workspace from a user's own RoboQuest install
- documentation for the bundled dynamic `jmap` plugin workflow
- the running notes from the `jmap` mirror work

It does not commit RoboQuest-derived dump trees, extracted assets, generated Unreal projects, or IDA databases. Those are meant to be regenerated locally from a user's own game install.

## Start Here

1. Read `docs/01_quick_start.md`.
2. Run `tooling/setup/bootstrap_repo_workspace.ps1 -CloneExternalSources`.
3. Run `tooling/setup/doctor_moddingkit.ps1 -GameRoot '<your RoboQuest install root>'`.
4. Run `tooling/setup/dump_modding_artifacts.ps1 -GameRoot '<your RoboQuest install root>' -LaunchForUht`.
5. Read `docs/10_generation_pipeline.md`.
6. Generate your local `projects/` outputs from the dumped data.
7. Read `docs/12_first_mods.md`.
8. Read `THIRD_PARTY_NOTICES.md` before redistributing any of the bundled binaries.

The setup scripts auto-detect UE 4.26 from common install paths, `UE426_ROOT`, and the Windows registry. Users only need to pass `-EngineRoot` when that auto-detection fails.

## What Is Included

- `runtime/`
  - Working UE4SS runtime files, release zips, and patch-analysis artifacts.
- `tooling/`
  - Tool binaries, RoboQuest helper script snapshot, SDK-generation snapshot, and setup scripts.
- `templates/`
  - tested starter mods and staging trees for first-run mod creation.
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
- Mod doctor:
  - `tooling/setup/doctor_moddingkit.ps1`
- Suzie installer:
  - `tooling/setup/install_suzie.ps1`
- Mod packaging/install:
  - `tooling/setup/package_mod.ps1`
  - `tooling/setup/install_mod.ps1`
  - `tooling/setup/uninstall_mod.ps1`
- AES candidate scan:
  - `tooling/setup/dump_aes_keys.py`
- Sample mods:
  - `templates/ue4ss/HelloRoboLogMod`
  - `templates/pak/HelloPakMod`
  - `templates/pak/PlayableClassMenuSample`
- Bundled plugin template:
  - `templates/plugins/Suzie`
- SDK generation snapshot:
  - `tooling/sdk_dump_tools_snapshot/`
- Workspace bootstrap:
  - `tooling/setup/bootstrap_repo_workspace.ps1`
  - `tooling/setup/bootstrap_external_sources.ps1`
- Current learnings:
  - `docs/07_jmap_static_mirror_learnings.md`
- Dynamic class workflow:
  - `docs/14_suzie_dynamic_classes.md`
- Repo/legal metadata:
  - `LICENSE`
  - `CONTRIBUTING.md`
  - `THIRD_PARTY_NOTICES.md`

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
- load the RoboQuest dump dynamically through the bundled Suzie plugin
- inspect the current generator logic and notes

It is a builder/bootstrap repo, not a redistributable RoboQuest SDK.

When regenerating an existing local project output, use `tooling/setup/generate_editor_project.ps1 -Clean` so the script is explicitly allowed to replace the generated output tree.
