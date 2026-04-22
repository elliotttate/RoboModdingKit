# Contributing

## Scope

This repo is a bootstrap workspace for RoboQuest modding. Contributions should improve the scripts, documentation, and reproducible local-generation flow without committing large game-derived outputs.

## Preferred Workflow

1. Keep changes focused on scripts, docs, or small helper artifacts.
2. Do not commit RoboQuest game files, extracted content, large generated SDK trees, or editor build outputs.
3. If you change the dump or project-generation flow, rerun the smoke path:
   - `tooling/setup/bootstrap_repo_workspace.ps1 -CloneExternalSources`
   - `tooling/setup/dump_modding_artifacts.ps1 -GameRoot '<your RoboQuest root>' -LaunchForUht -CollectExtrasIfPresent -GeneratePakListing`
   - `tooling/setup/generate_editor_project.ps1 -GenerateProjectFiles -Build -Clean`
4. Update the relevant docs when behavior changes.

## Style

- PowerShell and `.cmd` files should keep Windows-friendly line endings.
- Python files should keep LF line endings.
- Prefer portable paths and explicit arguments over machine-local hardcoded paths.
- Treat third-party runtime/tool binaries carefully and update `THIRD_PARTY_NOTICES.md` when those snapshots change.
