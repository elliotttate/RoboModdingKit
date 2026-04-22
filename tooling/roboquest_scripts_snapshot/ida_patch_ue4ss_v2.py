"""ida_patch_ue4ss_v2.py — locate the *patternsleuth_bind* FText push site.

The v1 patch targeted the C++ Signatures.cpp emplace which only fires if
an FText_Constructor.lua exists AND its scan returns a bad address. The
actual failure we see (`[PS] Scan failed ... Fatal Error: PS scan timed
out`) is driven by the Rust side in patternsleuth_bind/src/lib.rs — the
`handle!` macro pushes a Box<ResolveError> into `errors.0` when FText
resolution fails.

After Rust + MSVC compilation, each `handle!` expansion is its own copy.
We identify the FText-specific one by the nearby "FText::FText(FString&&)"
name literal, which is passed as `$name` to the macro. From that string
we follow back to the LEA in the code, find the `errors.0.push` call that
follows, and patch it to an effective NOP.

Specifically we look for:
  * LEA referencing "FText::FText(FString&&)" (the $name literal)
  * The conditional jump on `Ok/Err` just after
  * In the Err branch, a `CALL` to Vec::push (or Box::new + push)
We turn that CALL instruction (5 bytes `E8 xx xx xx xx`) into five NOP
bytes (`90 90 90 90 90`). The error simply never gets recorded.
"""
import json

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_kernwin
    import ida_name
    import ida_loader
    import idaapi
    import idautils
    import idc
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")


def log(msg: str) -> None:
    ida_kernwin.msg(f"[patch2] {msg}\n")


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


def ea_to_file_offset(ea: int) -> int:
    return ida_loader.get_fileregion_offset(ea)


def main() -> None:
    ida_auto.auto_wait()

    name_literal = b"FText::FText(FString&&)\x00"
    hits = find_bytes_all(name_literal)
    log(f"'FText::FText(FString&&)' string: {len(hits)} location(s)")
    if not hits:
        idc.qexit(1)

    patches = []
    for string_ea in hits:
        log(f"string @ {string_ea:#x}")
        for xr in idautils.XrefsTo(string_ea, 0):
            fn = ida_funcs.get_func(xr.frm)
            if not fn:
                continue
            log(f"  xref at {xr.frm:#x}  in fn {fn.start_ea:#x} size={fn.end_ea-fn.start_ea}")
            # From the xref, scan the next ~256 bytes for CALL instructions.
            # In a standard Rust `handle!` expansion for Err, the sequence is:
            #   - LEA to $name literal (already found — xr.frm)
            #   - LEA to $lua literal
            #   - CALL warning formatter
            #   - CALL warning formatter
            #   - Box::new(err) / push  ← we want this last call
            call_eas = []
            ea = xr.frm
            end = fn.end_ea
            while ea < end and len(call_eas) < 16:
                sz = idc.get_item_size(ea)
                if sz <= 0:
                    break
                mnem = idc.print_insn_mnem(ea).lower()
                if mnem == "call":
                    call_eas.append(ea)
                ea += sz
            log(f"    {len(call_eas)} CALL instructions after xref")
            for i, ce in enumerate(call_eas[:10]):
                target = idc.get_operand_value(ce, 0)
                tn = ida_name.get_ea_name(target) if target else ""
                log(f"      [{i}] call @ {ce:#x} -> {target:#x} ({tn})")
            # Heuristic: the LAST call in this stretch is the push into
            # errors.0 — the previous 2-3 are fmt!/warning! calls. NOPing
            # it is equivalent to dropping the error without touching the
            # happy path.
            if call_eas:
                nop_ea = call_eas[-1]
                # CALL with rel32 = 5 bytes; verify
                instr_size = idc.get_item_size(nop_ea)
                if instr_size != 5:
                    log(f"      !! call at {nop_ea:#x} is not 5 bytes (got {instr_size}) — skipping")
                    continue
                off = ea_to_file_offset(nop_ea)
                patches.append({
                    "description": f"NOP Vec::push at FText err branch in fn {fn.start_ea:#x}",
                    "call_ea": f"{nop_ea:#x}",
                    "file_offset": off,
                    "old_bytes": "E8 ?? ?? ?? ??",
                    "new_bytes": "90 90 90 90 90",
                    "patch_length": 5,
                })

    out = "E:/RoboQuestReverse/ue4ss_patch/ftext_patch_plan_v2.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"patches": patches, "dll": "UE4SS.dll"}, f, indent=2)
    log(f"wrote {out} with {len(patches)} NOP patch(es)")
    idc.qexit(0)


if __name__ == "__main__":
    main()
