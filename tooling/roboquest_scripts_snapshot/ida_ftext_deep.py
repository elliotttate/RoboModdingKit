"""ida_ftext_deep.py — deeper hunt for FText::FText(FString&&).

Approach:
  1. Grab the two candidates from the `83 4B ?? 12` scan and decompile each
     in Hex-Rays to see which one constructs an FText.
  2. Search for secondary markers that also appear in known-good FText
     prologues across patternsleuth's pattern bank:
       a) `BF 60 00 00 00 E8` — mov edi, 0x60; call …  (passing sizeof
          FTextHistoryBase as arg, the pattern-11 marker)
       b) `C7 44 24 ?? 01 00 00 00 C7 44 24 ?? 01 00 00 00` — initializing
          two FSharedRef<ITextData> refcounts to 1 (pattern 6 marker)
  3. For matches of any secondary marker, walk up to the containing
     function and report prologue + size.
  4. Print each candidate's full Hex-Rays pseudocode (truncated) so we
     can eyeball which one is FText::FText.
"""
import os

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_hexrays
    import ida_kernwin
    import ida_name
    import idaapi
    import idautils
    import idc
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")


def log(msg: str) -> None:
    ida_kernwin.msg(f"[ftext-deep] {msg}\n")


def find_bytes_all(data: bytes, mask: bytes | None = None) -> list[int]:
    hits: list[int] = []
    cur = 0
    while True:
        ea = ida_bytes.find_bytes(data, cur, mask=mask) if mask else ida_bytes.find_bytes(data, cur)
        if ea is None or ea == idaapi.BADADDR:
            break
        hits.append(ea)
        cur = ea + 1
    return hits


def hex_at(ea: int, n: int) -> str:
    b = ida_bytes.get_bytes(ea, n) or b""
    return " ".join(f"{x:02X}" for x in b)


def decompile_snippet(ea: int, max_lines: int = 30) -> str:
    try:
        cfunc = ida_hexrays.decompile(ea)
    except Exception as e:
        return f"<decompile error: {e}>"
    if not cfunc:
        return "<no pseudocode>"
    text = str(cfunc)
    lines = text.splitlines()
    return "\n".join(lines[:max_lines])


def examine_candidates(label: str, hits: list[int]) -> list[int]:
    fns: set[int] = set()
    for ea in hits:
        f = ida_funcs.get_func(ea)
        if f:
            fns.add(f.start_ea)
    fns = sorted(fns)
    log(f"[{label}] {len(hits)} hits across {len(fns)} functions")
    for fn_ea in fns[:10]:
        fn = ida_funcs.get_func(fn_ea)
        size = fn.end_ea - fn_ea if fn else 0
        nc = sum(1 for _ in idautils.XrefsTo(fn_ea, 0))
        log(f"  candidate {fn_ea:#x}  size={size}  callers={nc}")
        log(f"    prologue32 = {hex_at(fn_ea, 32)}")
        log(f"    prologue48 = {hex_at(fn_ea, 48)}")
        snippet = decompile_snippet(fn_ea, 20)
        for line in snippet.splitlines():
            log(f"    | {line}")
    return fns


def main() -> None:
    ida_auto.auto_wait()

    if not ida_hexrays.init_hexrays_plugin():
        log("ERROR: Hex-Rays failed to initialize.")
        idc.qexit(2)

    # (A) `83 4B ?? 12` candidates (flag 0x12)
    hits_a = find_bytes_all(bytes([0x83, 0x4B, 0x00, 0x12]),
                             bytes([0xFF, 0xFF, 0x00, 0xFF]))
    examine_candidates("83 4B ?? 12", hits_a)

    # (B) `BF 60 00 00 00 E8` = mov edi, 96; call …
    # Passing 0x60 as the first arg to a call – matches allocating the
    # FTextHistoryBase (size 0x60) in UE 4.25/4.26 FText::FText.
    hits_b = find_bytes_all(bytes([0xBF, 0x60, 0x00, 0x00, 0x00, 0xE8]))
    examine_candidates("BF 60 00 00 00 E8", hits_b)

    # (C) Ref-count init pattern: two consecutive 32-bit 1-stores on stack
    # `C7 44 24 ?? 01 00 00 00 C7 44 24 ?? 01 00 00 00`
    hits_c = find_bytes_all(
        bytes([0xC7, 0x44, 0x24, 0x00, 0x01, 0x00, 0x00, 0x00,
               0xC7, 0x44, 0x24, 0x00, 0x01, 0x00, 0x00, 0x00]),
        bytes([0xFF, 0xFF, 0xFF, 0x00, 0xFF, 0xFF, 0xFF, 0xFF,
               0xFF, 0xFF, 0xFF, 0x00, 0xFF, 0xFF, 0xFF, 0xFF]),
    )
    examine_candidates("C7 44 24 ?? 01 ...", hits_c)

    # (D) Common FText ctor prologue: `40 53 57 48 83 EC`
    # A tight byte sequence that appears at the start of the Deadly Days
    # FText::FromString signature and also at the top of many FText ctor
    # variants. Low false-positive because of the three-instruction
    # ordering (push rbx; push rdi; sub rsp,...).
    hits_d = find_bytes_all(bytes([0x40, 0x53, 0x57, 0x48, 0x83, 0xEC]))
    log(f"(D) '40 53 57 48 83 EC' hits: {len(hits_d)} (likely too many)")

    idc.qexit(0)


if __name__ == "__main__":
    main()
