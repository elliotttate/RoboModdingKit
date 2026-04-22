"""ida_verify_aob.py — verify an AOB pattern matches exactly the expected EA.

Reports every match in the entire image so we know whether the AOB is unique
(zero false positives) and hits the intended function.
"""
import os

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_kernwin
    import ida_name
    import idaapi
    import idc
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")


def log(msg: str) -> None:
    ida_kernwin.msg(f"[verify] {msg}\n")


def find_all_bytes(data: bytes) -> list[int]:
    hits: list[int] = []
    cur = 0
    while True:
        ea = ida_bytes.find_bytes(data, cur)
        if ea is None or ea == idaapi.BADADDR:
            break
        hits.append(ea)
        cur = ea + 1
    return hits


def main() -> None:
    ida_auto.auto_wait()
    # Our AOB (no wildcards for this initial check).
    target = bytes.fromhex("48 89 5C 24 18 48 89 6C 24 20 56 57 41 56 48 83 EC 30 4C 8B B2 98 00 00 00 41 8B E8 48 8B DA 48 8B F9".replace(" ", ""))
    hits = find_all_bytes(target)
    log(f"AOB length: {len(target)} bytes")
    log(f"matches: {len(hits)}")
    for ea in hits[:10]:
        f = ida_funcs.get_func(ea)
        fstart = f.start_ea if f else 0
        fname = ida_name.get_ea_name(fstart) if f else ""
        log(f"  {ea:#x}  in_func={fstart:#x} ({fname})")

    # Show what's actually at 0x143C4AC20
    expected = 0x143C4AC20
    actual = ida_bytes.get_bytes(expected, 48) or b""
    log(f"bytes @ expected {expected:#x}: {' '.join(f'{x:02X}' for x in actual)}")

    # Short-and-unique alternative: try just the first 20 bytes and see how many match
    short = target[:20]
    short_hits = find_all_bytes(short)
    log(f"first 20 bytes: {len(short_hits)} matches")

    idc.qexit(0)


if __name__ == "__main__":
    main()
