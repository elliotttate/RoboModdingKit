"""ida_find_nullsub2.py — find a small function whose *padding-context*
signature (preceding CC bytes + function prologue) is unique in the image.

UE4SS's Lua scanner returns matchAddress at the FIRST byte matched. Our
OnMatchFound adds the padding length back to land on the function entry.

Why this helps
--------------
Nullsub bodies are all identical (`C3`, or `48 83 EC 28 E8 … 48 83 C4 28 C3`),
so a raw-prologue AOB can't single one out. But function boundaries are
aligned to 16 bytes and MSVC fills the gaps with `CC` (int3). Including
the PRECEDING int3 bytes in the AOB makes each boundary unique.
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
    ida_kernwin.msg(f"[nullsub2] {msg}\n")


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


def count_preceding_cc(ea: int, max_back: int = 16) -> int:
    """Return how many 0xCC bytes precede `ea`, up to max_back."""
    n = 0
    for i in range(1, max_back + 1):
        b = ida_bytes.get_bytes(ea - i, 1)
        if b == b"\xcc":
            n += 1
        else:
            break
    return n


def main() -> None:
    ida_auto.auto_wait()

    # Scan every small named function.
    best = None  # (pad_len, prologue_len, ea, name, aob_bytes)
    chosen = []
    for fn_ea in idautils.Functions():
        fn = ida_funcs.get_func(fn_ea)
        if not fn:
            continue
        size = fn.end_ea - fn_ea
        name = ida_name.get_ea_name(fn_ea) or f"sub_{fn_ea:X}"
        if size > 24:
            continue
        pad = count_preceding_cc(fn_ea, 12)
        if pad < 4:
            continue
        prologue_len = min(size, 14)
        body = ida_bytes.get_bytes(fn_ea, prologue_len) or b""
        pre = b"\xcc" * pad
        aob = pre + body
        if len(aob) < pad + 4:
            continue
        hits = find_bytes_all(aob)
        if len(hits) == 1:
            chosen.append((pad, prologue_len, fn_ea, name, aob))
            if best is None or (prologue_len, pad) > (best[1], best[0]):
                best = (pad, prologue_len, fn_ea, name, aob)

    log(f"{len(chosen)} small funcs with unique CC-padded prologues.")
    for pad, prologue_len, fn_ea, name, aob in chosen[:10]:
        aob_str = " ".join(f"{b:02X}" for b in aob)
        log(f"  {fn_ea:#x}  pad={pad}  prologue={prologue_len}  name={name}")
        log(f"    aob  = {aob_str}")
        log(f"    offset_in_aob = {pad}  (OnMatchFound returns matchAddress + {pad})")

    if best:
        pad, prologue_len, fn_ea, name, aob = best
        log("BEST candidate (most bytes of prologue + most padding):")
        aob_str = " ".join(f"{b:02X}" for b in aob)
        log(f"  ea={fn_ea:#x} name={name} pad={pad} prologue_len={prologue_len}")
        log(f"  aob = {aob_str}")

    idc.qexit(0)


if __name__ == "__main__":
    main()
