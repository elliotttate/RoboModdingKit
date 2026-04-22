# First Mods

This repo now includes two tested starter paths:

- a UE4SS Lua mod
- a sidecar `.pak` mod

## 1. Run A Quick Health Check

```powershell
& '.\tooling\setup\doctor_moddingkit.ps1' `
  -GameRoot 'C:\Games\RoboQuest'
```

## 2. First UE4SS Mod

Install the sample mod directly from the template:

```powershell
& '.\tooling\setup\install_mod.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -SourcePath '.\templates\ue4ss\HelloRoboLogMod'
```

Launch RoboQuest, then check:

- `RoboQuest\Binaries\Win64\UE4SS.log`

Expected marker:

- `[HelloRoboLogMod] Loaded.`

Optional packaging step:

```powershell
& '.\tooling\setup\package_mod.ps1' `
  -SourcePath '.\templates\ue4ss\HelloRoboLogMod'
```

That produces a distributable `.zip` under `tooling/generated/mod_packages`.

Remove it later with:

```powershell
& '.\tooling\setup\uninstall_mod.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -Name 'HelloRoboLogMod' `
  -Type UE4SS
```

## 3. First Pak Mod

Package the sample pak template:

```powershell
& '.\tooling\setup\package_mod.ps1' `
  -SourcePath '.\templates\pak\HelloPakMod'
```

Pak templates can declare packaging settings in `robomod.json`, including:

- `mount_point`
- `version`
- `compression`
- `path_hash_seed`

Install the built pak:

```powershell
& '.\tooling\setup\install_mod.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -SourcePath '.\tooling\generated\mod_packages\HelloPakMod.pak'
```

This copies the sample mod to:

- `RoboQuest\Content\Paks\~mods\HelloPakMod.pak`

You can confirm the file contents with:

```powershell
$RepoRoot = (Resolve-Path '.').Path
& (Join-Path $RepoRoot 'tooling\bin\repak.exe') list `
  (Join-Path $RepoRoot 'tooling\generated\mod_packages\HelloPakMod.pak')
```

Remove it later with:

```powershell
& '.\tooling\setup\uninstall_mod.ps1' `
  -GameRoot 'C:\Games\RoboQuest' `
  -Name 'HelloPakMod' `
  -Type Pak
```

## 4. Where To Go Next

- use `docs/04_editor_project_and_jmap.md` to rebuild the local editor project
- use `docs/03_ue4ss_and_runtime.md` to understand the included runtime
- use `docs/13_troubleshooting.md` when a step fails
