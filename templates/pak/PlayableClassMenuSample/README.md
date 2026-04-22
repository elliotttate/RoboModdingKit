# PlayableClassMenuSample

This is a starter sidecar pak sample for mods that:

- add one or more new player-class rows
- stage new class assets under a mod-owned `/Game/Mods/...` path
- override menu widgets so the new classes are reachable from the title screen or basecamp

What it ships by default:

- authoring notes under `authoring/`
- placeholder stage files that prove the pak mounts in the right content roots
- a `robomod.json` that packages with the kit scripts unchanged

Game-side anchors used by this sample:

- `FPlayerClassRow`
- `DT_PlayerClasses`
- `AAInteractiveBasecampMenu::MenuClass`
- `URQBlueprintLibrary::SyncLoadAllActivePlayerClassRowNames`

Suggested workflow:

1. Duplicate an existing shipped class row in the local editor project and build the new class assets under `/Game/Mods/PlayableClassMenuSample`.
2. Add or override the menu widgets that should surface the new class in the title flow, basecamp flow, or both.
3. Replace the placeholder files under `stage/` with the cooked `.uasset`, `.uexp`, and optional `.ubulk` output.
4. Package with `tooling/setup/package_mod.ps1` and install with `tooling/setup/install_mod.ps1`.

This template does not change gameplay on its own. Until the placeholder stage files are replaced with cooked assets, the packaged mod only serves as a mount-path sanity check and authoring scaffold.
