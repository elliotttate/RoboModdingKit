# Suzie Dynamic Classes

## Goal

Load the RoboQuest `jmap` dump directly into the generated UE 4.26 editor project through the bundled Suzie plugin.

This gives you a dynamic-class path alongside the static `jmap` mirror. The static mirror is still the main project-reconstruction workflow. Suzie is useful when you want the dump loaded into the editor without regenerating a large native source surface first.

## What The Kit Bundles

- `templates/plugins/Suzie`
  - bundled Suzie source snapshot, patched and validated for RoboQuest on UE 4.26
- `tooling/setup/install_suzie.ps1`
  - copies the bundled plugin into a generated project
  - copies a local RoboQuest dump to `Content/DynamicClasses/RoboQuest.jmap`
  - enables `Suzie` inside the generated `.uproject`

## Default Flow

`generate_editor_project.ps1` installs Suzie by default.

```powershell
& '.\tooling\setup\generate_editor_project.ps1' -GenerateProjectFiles -Build
```

If you already have a generated project and want to add Suzie later:

```powershell
& '.\tooling\setup\install_suzie.ps1' `
  -ProjectRoot '.\projects\RoboQuest_jmap_426_local'
```

If you want to force a specific dump:

```powershell
& '.\tooling\setup\install_suzie.ps1' `
  -ProjectRoot '.\projects\RoboQuest_jmap_426_local' `
  -DumpPath '.\references\dumps\RoboQuest.jmap'
```

## Expected Outputs

After installation, the generated project should contain:

- `Plugins/Suzie`
- `Content/DynamicClasses/RoboQuest.jmap`
- a `Plugins` entry for `Suzie` in `RoboQuest.uproject`

## Validation Markers

The RoboQuest-tested validation path was:

- generated UE 4.26 project build succeeds
- editor launches
- `Saved/Logs/RoboQuest.log` contains:
  - `LogSuzie: Display: Suzie plugin starting`
  - `LogSuzie: Display: Found 1 JSON class definition files`
  - `LogSuzie: Display: Processing JSON class definition: RoboQuest.jmap`
  - `LogSuzie: Display: Finished processing 22342 reflected objects from dump`

Those markers mean the bundled plugin loaded the RoboQuest dump successfully.

## Notes

- The bundled Suzie plugin is included as source, not a prebuilt binary.
- It is meant to be built inside the generated RoboQuest UE 4.26 editor project.
- The kit prefers `references/dumps/RoboQuest.jmap` for the Suzie path, then falls back to the other local dump variants if needed.
