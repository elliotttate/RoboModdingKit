# Notes

## Current Primary Learnings Doc

- `docs/07_jmap_static_mirror_learnings.md`

This is the running note file for the jmap-generated mirror and related RoboQuest modding discoveries.

## Environment Assumptions

- RoboQuest target install:
  - `E:\SteamLibrary\steamapps\common\RoboQuest`
- Working engine install:
  - `E:\Epic Games\UE_4.26`

## Important Practical Notes

- Public repo users are expected to regenerate local dumps and project outputs from their own RoboQuest install.
- The local editor project can be regenerated and built with `tooling/setup/generate_editor_project.ps1`.
- The included UE4SS runtime snapshot is a convenience baseline; the dump pipeline will redeploy it into the local game install when needed.
