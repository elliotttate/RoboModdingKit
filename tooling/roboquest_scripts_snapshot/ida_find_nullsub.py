"""ida_find_nullsub.py — locate a small, safe-to-call function in the DB.

Why we need one
---------------
UE4SS v3.0.1 validates a user-supplied FText_Constructor.lua address by
calling it as `FText::FText(FString&&)` with an FString("bCanBeDamaged").
If the returned address isn't a real ctor, the call corrupts memory and
crashes. But if we hand it a *nullsub* — a function whose body is just
`RET` (or a few mov/xor instructions followed by RET) — it returns
cleanly. UE4SS's subsequent `text == L"bCanBeDamaged"` check fails, the
scan marks FText as not-resolved, and the overall boot proceeds.

What this script picks
----------------------
A function that:
  1. Has FUNC_THUNK or `nullsub_` naming hint (IDA already classified it).
  2. Is <= 24 bytes (small body, unlikely to touch memory).
  3. Has a *unique* prologue among the top-K bytes so it can be AOB-matched.

For each candidate we print a working 18-byte AOB that UE4SS can resolve to
exactly that entry point.
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
    ida_kernwin.msg(f"[nullsub] {msg}\n")


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


def main() -> None:
    ida_auto.auto_wait()

    # Collect every function, look for small ones with nullsub naming.
    candidates: list[tuple[int, int, str]] = []  # (ea, size, name)
    for fn_ea in idautils.Functions():
        fn = ida_funcs.get_func(fn_ea)
        if not fn:
            continue
        size = fn.end_ea - fn_ea
        name = ida_name.get_ea_name(fn_ea) or f"sub_{fn_ea:X}"
        if size > 24:
            continue
        # Prefer IDA's nullsub_* tagging.
        if not name.startswith("nullsub_"):
            continue
        candidates.append((fn_ea, size, name))

    log(f"Found {len(candidates)} small nullsub_* functions.")

    # For each, compute a uniquely-matching 18-byte AOB (must not overlap
    # other nullsubs or instructions). Start with full prologue; trim if
    # ambiguous.
    chosen: list[tuple[int, int, str, bytes]] = []
    for ea, size, name in candidates:
        full = ida_bytes.get_bytes(ea, min(size, 18)) or b""
        if len(full) < 6:
            continue
        # Verify uniqueness
        hits = find_bytes_all(full)
        if len(hits) != 1:
            continue
        chosen.append((ea, size, name, full))

    log(f"{len(chosen)} nullsubs have unique 18-byte prologues.")
    for ea, size, name, aob in chosen[:10]:
        aob_str = " ".join(f"{b:02X}" for b in aob)
        log(f"  {ea:#x}  size={size}  name={name}")
        log(f"    aob = {aob_str}")

    # Also: any function consisting of just RET (0xC3) — the tiniest possible.
    ret_hits = find_bytes_all(bytes([0xC3]))
    log(f"Single-RET bytes found: {len(ret_hits)} (not all are function starts)")
    # Pair each with the function boundary
    bare_rets: list[tuple[int, str]] = []
    for ea in ret_hits:
        fn = ida_funcs.get_func(ea)
        if fn and fn.start_ea == ea and fn.end_ea - ea <= 1:
            bare_rets.append((ea, ida_name.get_ea_name(ea) or f"sub_{ea:X}"))
    log(f"Single-byte RET functions: {len(bare_rets)}")

    idc.qexit(0)


if __name__ == "__main__":
    main()
