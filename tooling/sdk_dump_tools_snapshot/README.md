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

Typical output location:

- `references/sdk_dump_tools/out/RoboQuest.generated.genny`
- `references/sdk_generated`

The repo-level dump orchestrator uses this snapshot directly.
