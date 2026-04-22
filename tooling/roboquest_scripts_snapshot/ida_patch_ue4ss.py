"""ida_patch_ue4ss.py — generate a binary patch file for UE4SS.dll.

What this does
--------------
UE4SS's `ScanError(sv, bool IsFatal=true)` compiles `IsFatal = true` to
`mov byte ptr [this+0x20], 1` right after the emplace-back call
(`C6 47 20 01`). Every time the FText scan fails, one of four call sites
pushes a fatal ScanError into the errors vector; UE4SS then retries
indefinitely and eventually aborts.

We identify the FText-specific emplaces by xrefs to the literal
"Lua script 'FText_Constructor.lua' did not return a valid address..."
string, then for each xref look forward 40 bytes for the immediate
`C6 47 20 01` sequence (the bIsFatal store). We emit a JSON patch plan:
each entry is {offset_in_file, old_byte, new_byte} that turns that 1 → 0.

Output
------
  ue4ss_patch/ftext_patch_plan.json — list of patch sites (file-offset
    form, ready for a non-IDA byte-flipper to apply).
"""
import json
from pathlib import Path

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_kernwin
    import ida_name
    import idaapi
    import idautils
    import idc
    import ida_loader
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_INPUT_SHA256 = "8AC18FBFFC1EF96B0662D4A2D537B3F224C26D65CAABA7989A9404C566102B26"
EXPECTED_OUTPUT_SHA256 = "C397DD1019BDD33BCD81C48DF95C5BF0BC6B3C2D1E26EDFEE42ACB47C3CADB15"


def log(msg: str) -> None:
    ida_kernwin.msg(f"[patch] {msg}\n")


def find_bytes_all(data: bytes) -> list[int]:
    hits: list[int] = []
    cur = 0
    while True:
        ea = ida_bytes.find_bytes(data, cur)
        if ea is None or ea == idaapi.BADADDR:
            break
        hits.append(ea)
        cur = ea + 1
    return hits


def find_is_fatal_store_after(start_ea: int, max_search: int = 64) -> int:
    """Find `C6 47 20 01` in the next max_search bytes starting at
    start_ea. Returns the address of the immediate `01` byte to patch,
    or 0 if not found."""
    pattern = bytes([0xC6, 0x47, 0x20, 0x01])
    for off in range(max_search):
        b = ida_bytes.get_bytes(start_ea + off, 4)
        if b == pattern:
            return start_ea + off + 3  # index of the `01`
    return 0


def ea_to_file_offset(ea: int) -> int:
    """Convert an in-memory EA to a file offset using IDA's segment info."""
    return ida_loader.get_fileregion_offset(ea)


def main() -> None:
    ida_auto.auto_wait()

    target = b"Lua script 'FText_Constructor.lua' did not return a valid address for FText::FText.\x00"
    hits = find_bytes_all(target)
    log(f"FText error string at {len(hits)} location(s)")
    if len(hits) != 1:
        log("expected exactly 1 — aborting")
        idc.qexit(1)

    string_ea = hits[0]
    patches = []
    seen: set[int] = set()

    for xr in idautils.XrefsTo(string_ea, 0):
        site = xr.frm
        fatal_store_ea = find_is_fatal_store_after(site)
        if fatal_store_ea == 0 or fatal_store_ea in seen:
            continue
        seen.add(fatal_store_ea)
        file_off = ea_to_file_offset(fatal_store_ea)
        fn = ida_funcs.get_func(site)
        fn_name = ida_name.get_ea_name(fn.start_ea) if fn else "?"
        patches.append({
            "description": f"FText error emplace in {fn_name}",
            "xref_ea": f"{site:#x}",
            "is_fatal_ea": f"{fatal_store_ea:#x}",
            "file_offset": file_off,
            "old_byte": 1,
            "new_byte": 0,
        })
        log(f"  patch {fatal_store_ea:#x}  file_off=0x{file_off:x}  fn={fn_name}")

    plan_path = REPO_ROOT / "runtime" / "UE4SS_patch_analysis" / "ftext_patch_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with plan_path.open("w", encoding="utf-8") as f:
        json.dump({
            "dll": "UE4SS.dll",
            "expected_input_sha256": EXPECTED_INPUT_SHA256,
            "expected_output_sha256": EXPECTED_OUTPUT_SHA256,
            "patches": patches,
        }, f, indent=2)
    log(f"wrote {plan_path} with {len(patches)} patch(es)")
    idc.qexit(0)


if __name__ == "__main__":
    main()
