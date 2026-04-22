# HelloPakMod

This is the smallest useful pak mod sample in the kit.

What it does:

- stages a marker file under `RoboQuest/Content/RoboModdingKit/HelloPakMod`
- packages that staging tree into a sidecar `.pak`
- can be installed into `RoboQuest/Content/Paks/~mods`

Use it to verify that:

- `package_mod.ps1` can build a RoboQuest-compatible `.pak`
- `install_mod.ps1` and `uninstall_mod.ps1` can manage sidecar pak mods
- RoboQuest mounts the sample pak at startup
