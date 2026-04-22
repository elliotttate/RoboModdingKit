# Mod Templates

This folder contains small starter mods and scaffolds for RoboQuest:

- `ue4ss/HelloRoboLogMod`
  - a minimal UE4SS Lua mod that writes a line to `UE4SS.log` when the game starts
- `pak/HelloPakMod`
  - a minimal pak mod staging tree that packages a marker file into a sidecar `.pak`
- `pak/PlayableClassMenuSample`
  - a sidecar pak scaffold for authoring new player classes and menu-entry overrides
- `plugins/Suzie`
  - a bundled Suzie source snapshot patched and validated against the RoboQuest `jmap` dump on UE 4.26

Use the setup scripts under `tooling/setup` to package, install, and remove these templates.
