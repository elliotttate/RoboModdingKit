"""ida_find_ue4ss_ftext_error.py — locate the FText scan-failure push
sites in UE4SS.dll so we can binary-patch them to non-fatal.

Two places we need:
  1. patternsleuth_bind's handle! expansion for FText — pushes the
     ResolveError into errors.0 when the scan fails.
  2. Signatures.cpp's Lua fallback path — emplace_back("Lua script
     'FText_Constructor.lua' did not return a valid address ...").

Both are reachable from the FText-specific error string. We search the
.rdata segment for those strings, follow the single xref to code, print
the containing function and the next 64 bytes so we can eyeball the
push call to NOP out.
"""
import os

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_kernwin
    import ida_name
    import idaapi
    import idautils
    import idc
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")


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


def hex_at(ea: int, n: int) -> str:
    b = ida_bytes.get_bytes(ea, n) or b""
    return " ".join(f"{x:02X}" for x in b)


def describe_code_ref(string_ea: int, label: str) -> None:
    log(f"=== {label} @ {string_ea:#x} ===")
    xrefs = list(idautils.XrefsTo(string_ea, 0))
    log(f"  xrefs: {len(xrefs)}")
    for xr in xrefs[:8]:
        fn = ida_funcs.get_func(xr.frm)
        fstart = fn.start_ea if fn else 0
        fsize = fn.end_ea - fn.start_ea if fn else 0
        fname = ida_name.get_ea_name(fstart) if fn else ""
        log(f"  xref at {xr.frm:#x}  in {fname or '?'} @ {fstart:#x} size={fsize}")
        log(f"    bytes around ref: {hex_at(max(xr.frm-8, 0), 48)}")


def main() -> None:
    ida_auto.auto_wait()

    # Strings we look for — they're the literal error messages unique to the
    # FText code paths in both Rust's handle! and C++'s Lua fallback.
    targets = [
        (b"FText::FText(FString&&)\x00", "Rust handle! err name"),
        (b"FText_Constructor.lua\x00", "signature filename"),
        (b"Lua script 'FText_Constructor.lua' did not return a valid address for FText::FText.\x00",
            "C++ emplace_back message"),
    ]
    for pat, label in targets:
        hits = find_bytes_all(pat)
        log(f"{label!r}: {len(hits)} match(es)")
        for h in hits[:4]:
            describe_code_ref(h, label)

    log("Done.")
    idc.qexit(0)


if __name__ == "__main__":
    main()
