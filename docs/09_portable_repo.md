# Portable GitHub Repo Plan

The current local kit can be useful as-is on this machine, but a GitHub repo should be treated differently.

## What Should Go In Git

- docs
- manifests
- PowerShell/bootstrap scripts
- the copied RoboQuest helper script snapshot
- small configuration files
- optionally small open-source tool binaries if you want convenience

## What Should Not Be Assumed To Live In Git

- RoboQuest game files
- extracted game content
- full dump outputs
- giant generated SDK trees
- IDA databases
- any local-only junction structure

Those items are either too large, derived from the game install, or both.

## Recommended Fresh-Machine Flow

1. Clone the modding kit repo.
2. Run `tooling/setup/bootstrap_external_sources.ps1`.
3. Install UE 4.26 and ensure RoboQuest is locally installed.
4. Run `tooling/setup/dump_modding_artifacts.ps1` against the local RoboQuest install.
5. Run `tooling/setup/generate_editor_project.ps1` to build the local UE 4.26 project.

## Existing Local Pipeline Reference

The original reverse-workspace README already records the local pipeline stages and tool order:

- dump reflection with `jmap`
- extract assets with `retoc` and `repak`
- run the IDA scripts
- use UE4SS for UHT-compatible headers
- build and open the generated 4.26 editor project

That reference is useful source material for turning the kit into a reproducible public repo, but the outputs themselves should usually be local artifacts, not committed repo content.

## Practical Recommendation

Treat the GitHub version as a builder/bootstrap repo, not as a full pre-expanded archive of all generated assets.
