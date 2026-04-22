# Portable Repo Notes

This repository is intentionally structured as a builder/bootstrap repo rather than a full pre-expanded archive.

## What Belongs In Git

- docs
- manifests and metadata
- setup/bootstrap scripts
- RoboQuest-specific helper-script snapshots
- small configuration files
- small redistributed tool/runtime binaries with attribution

## What Stays Local

- RoboQuest game files
- extracted content
- fresh dump outputs
- generated Unreal projects
- large SDK trees
- IDA databases and personal reverse-engineering workspaces

Those artifacts are either derived from a local game install, too large for a clean public repo, or both.

## Expected Fresh-Machine Flow

1. Clone the repo.
2. Run `tooling/setup/bootstrap_repo_workspace.ps1 -CloneExternalSources`.
3. Install UE 4.26 and make sure RoboQuest is installed locally.
4. Run `tooling/setup/dump_modding_artifacts.ps1` against the local RoboQuest install.
5. Run `tooling/setup/generate_editor_project.ps1` to build the local UE 4.26 project.

## Practical Recommendation

Treat the repo as a reproducible workspace generator. The committed content should explain the pipeline and carry the small helper/runtime pieces; the large game-derived outputs should usually be regenerated locally.
