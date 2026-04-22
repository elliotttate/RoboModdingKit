# Repo Notes

## Primary Learnings Doc

- `docs/07_jmap_static_mirror_learnings.md`

That file is the running process log for the `jmap`-generated mirror and related RoboQuest modding discoveries.

## Repo Assumptions

- users regenerate dumps and project outputs from their own RoboQuest install
- users either let the scripts auto-detect UE 4.26 or pass `-EngineRoot`
- generated outputs live under local `references/` and `projects/` paths and are not treated as committed source material

## Practical Notes

- `tooling/setup/dump_modding_artifacts.ps1` redeploys the included UE4SS runtime before collecting dumps
- `tooling/setup/generate_editor_project.ps1 -Clean` is the supported way to replace an existing generated project tree
- `tooling/setup/restore_game_runtime_backup.ps1` restores the original runtime files that the dump step backs up on first run
