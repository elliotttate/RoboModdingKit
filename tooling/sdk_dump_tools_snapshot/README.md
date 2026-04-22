# SDK Dump Tools Snapshot

This is a minimal snapshot of the local `sdk_dump_tools` workflow needed to regenerate the flat SDK headers from:

- UE4SS `UHTHeaderDump`
- `UE4SS_ObjectDump.txt`

Included:

- `emit_genny_from_ue4ss.py`
- `postprocess_generated_sdk.py`
- `main.cpp`
- `CMakeLists.txt`
- `build_emit.cmd`
- `run_emit.cmd`
- `bin/rq_sdkgenny_emit.exe`

The repo-level dump orchestrator uses the prebuilt `bin/rq_sdkgenny_emit.exe` directly. `run_emit.cmd` is only needed when you want to run the emitter by hand, and `build_emit.cmd` is only needed when you explicitly want to rebuild the emitter from source with a local `sdkgenny` checkout.

Typical output location:

- `references/sdk_dump_tools/out/RoboQuest.generated.genny`
- `references/sdk_generated`

Optional rebuild notes:

- `build_emit.cmd <path-to-sdkgenny-checkout>`
- `run_emit.cmd <input.genny> <output_dir> [path-to-sdkgenny-checkout]`

The bootstrap path does not require rebuilding this tool.
