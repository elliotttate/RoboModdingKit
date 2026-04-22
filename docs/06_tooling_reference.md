# Tooling Reference

## Ready-To-Run Binaries

Located in `tooling/bin`:

- `jmap_dumper.exe`
- `repak.exe`
- `retoc.exe`
- `kismet-analyzer.exe`

## RoboQuest-Specific Scripts

Located at:

- `tooling/roboquest_scripts_snapshot`

Examples of useful local scripts there:

- `jmap_generate_uproject.py`
- `jmap_to_uht.py`
- `merge_pseudocode.py`
- `ida_apply_jmap.py`
- `ida_hexrays_dump.py`
- `ida_patch_ue4ss_v2.py`

## Kit Setup Helpers

Located at:

- `tooling/setup/bootstrap_repo_workspace.ps1`
- `tooling/setup/bootstrap_external_sources.ps1`
- `tooling/setup/dump_modding_artifacts.ps1`
- `tooling/setup/dump_aes_keys.py`
- `tooling/setup/doctor_moddingkit.ps1`
- `tooling/setup/generate_editor_project.ps1`
- `tooling/setup/install_suzie.ps1`
- `tooling/setup/package_mod.ps1`
- `tooling/setup/install_mod.ps1`
- `tooling/setup/uninstall_mod.ps1`
- `tooling/setup/restore_game_runtime_backup.ps1`
- `tooling/setup/README.md`

Use these to bootstrap a fresh clone, clone open-source dependencies, dump artifacts from a local RoboQuest install, and generate the local editor project.

## SDK Generation Snapshot

Located at:

- `tooling/sdk_dump_tools_snapshot`

This is the minimal local SDK-generation toolchain used by `dump_modding_artifacts.ps1`.

## External Sources

Located in `tooling/external_sources` after running the bootstrap:

- `jmap`
- `repak`
- `retoc`
- `kismet-analyzer`
- `RE-UE4SS-v301`
- `Suzie`
- `UEVR`
- `uevr-mcp`
- `UE4GameProjectGenerator`
- `sdkgenny`

## Why These Matter

- `jmap`
  - native/reflection dumping
- `repak`
  - Unreal pak work
- `retoc`
  - IoStore and related content workflows
- `kismet-analyzer`
  - Blueprint analysis
- `dump_modding_artifacts.ps1`
  - one-command collection of jmap dumps, AES candidates, UE4SS dumps, SDK output, and optional extras
- `dump_aes_keys.py`
  - AES candidate scan for the Shipping executable, with optional `repak` verification
- `doctor_moddingkit.ps1`
  - preflight check for the engine, game install, key tool binaries, templates, and generated outputs; accepts `-GeneratedProjectRoot` when you keep the generated project outside the default local path
- `install_suzie.ps1`
  - mirrors the bundled Suzie plugin into a generated RoboQuest project, copies `RoboQuest.jmap` to `Content/DynamicClasses`, and enables the plugin in the local `.uproject`
- `package_mod.ps1`
  - packages a UE4SS template into a `.zip` or a staged content tree into a RoboQuest-compatible sidecar `.pak`; pak packaging reads `mount_point`, `version`, `compression`, and `path_hash_seed` from `robomod.json` unless overridden
- `install_mod.ps1`
  - installs a packaged `.pak`, a packaged UE4SS `.zip`, or a loose UE4SS mod directory into the game
- `uninstall_mod.ps1`
  - removes installed sample or custom mods from the game install
- `RE-UE4SS-v301`
  - UE4SS v3.0.1 source tree used for the RoboQuest patch work
- `Suzie`
  - bundled as a RoboQuest-tested UE 4.26 plugin template and also available as an external reference clone
- `UEVR` and `uevr-mcp`
  - useful for live introspection and runtime experiments
- `UE4GameProjectGenerator`
  - additional project-generation reference material
- `sdkgenny`
  - optional rebuild source for `tooling/sdk_dump_tools_snapshot/bin/rq_sdkgenny_emit.exe`

## Direct Tool Paths

- `tooling/bin/jmap_dumper.exe`
- `tooling/bin/repak.exe`
- `tooling/bin/retoc.exe`
- `tooling/bin/kismet-analyzer.exe`

## Notes

- The `tooling/bin` folder contains copied executables.
- The `tooling/external_sources` folder is meant for local clones.
- The RoboQuest-specific scripts are carried in `tooling/roboquest_scripts_snapshot`.
- External-source refs are pinned in `tooling/setup/external_sources.json`.
