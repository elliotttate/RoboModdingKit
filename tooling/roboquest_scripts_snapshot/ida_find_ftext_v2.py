"""ida_find_ftext_v2.py — find FText constructors by scanning for the
'OR flags, 0x12' byte pattern that appears in every FText::FText
implementation in UE 4.25 / 4.26 / 4.27 shipping builds.

Reasoning:
  * FText stores a `TFlags<EFlags>` field where `EFlags` includes
    `Transient = 0x2` and `CultureInvariant = 0x10`. Construction from
    a rvalue FString sets both (`0x12`), emitted by MSVC as
    `or byte ptr [this+<off>], 0x12`, which encodes as `83 4B <off> 12`.
  * This is the only place in the binary that sets 0x12 on a byte via
    that specific encoding — on RoboQuest's build only a handful of
    functions match.
  * We walk from each match back to the containing function's prologue
    and print the first 32 bytes — that's our candidate AOB.

We also cross-check against IDA's call-graph: the real constructor is
called directly from several places (FText::FromString, FText::Trim,
etc.). Candidates with the most callers are ranked higher.
"""
import os

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_kernwin
    import ida_name
    import ida_segment
    import idaapi
    import idautils
    import idc
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")


def log(msg: str) -> None:
    ida_kernwin.msg(f"[ftext-v2] {msg}\n")


def find_bytes_all(data: bytes, mask: bytes | None = None) -> list[int]:
    hits: list[int] = []
    cur = 0
    while True:
        if mask is None:
            ea = ida_bytes.find_bytes(data, cur)
        else:
            # find_bytes with mask form: bytes with '?' bytes in pattern
            # IDA 9 accepts a "mask" param: bytes to search, len, and mask
            # where each mask byte = 0xff for exact, 0x00 for wildcard.
            ea = ida_bytes.find_bytes(data, cur, mask=mask)
        if ea is None or ea == idaapi.BADADDR:
            break
        hits.append(ea)
        cur = ea + 1
    return hits


def hex_at(ea: int, n: int = 32) -> str:
    b = ida_bytes.get_bytes(ea, n) or b""
    return " ".join(f"{x:02X}" for x in b)


def main() -> None:
    ida_auto.auto_wait()

    # Pattern: `83 4B ?? 12` = OR BYTE PTR [RBX + disp8], 0x12
    # We search with a wildcard mask.
    pattern = bytes([0x83, 0x4B, 0x00, 0x12])
    mask    = bytes([0xFF, 0xFF, 0x00, 0xFF])

    log(f"Searching for '83 4B ?? 12'...")
    hits = find_bytes_all(pattern, mask)
    log(f"Got {len(hits)} hits")

    # Group by containing function.
    fn_hits: dict[int, list[int]] = {}
    for ea in hits:
        f = ida_funcs.get_func(ea)
        if f is None:
            continue
        fn_hits.setdefault(f.start_ea, []).append(ea)

    log(f"Grouped into {len(fn_hits)} functions.")
    # Rank by number of hits inside + number of callers (cross-refs TO the function).
    ranked: list[tuple[int, int, int, int, int]] = []
    for fn_ea, instr_eas in fn_hits.items():
        caller_count = sum(1 for _ in idautils.XrefsTo(fn_ea, 0))
        fn = ida_funcs.get_func(fn_ea)
        size = (fn.end_ea - fn.start_ea) if fn else 0
        ranked.append((fn_ea, len(instr_eas), caller_count, size, instr_eas[0]))

    # Typical FText::FText is small (<0x150 bytes), has many callers (>5),
    # and contains the '0x12' pattern exactly once.
    ranked.sort(key=lambda r: (-r[2], r[3], -r[1]))
    log(f"Top candidates (by caller count ↑, size ↑, hit count ↑):")
    for fn_ea, nhits, ncallers, size, first_hit in ranked[:20]:
        name = ida_name.get_ea_name(fn_ea) or f"sub_{fn_ea:X}"
        log(f"  {fn_ea:#x}  size={size:>4d}  hits={nhits}  callers={ncallers:>4d}  name={name}")
        log(f"    prologue24 = {hex_at(fn_ea, 24)}")
        log(f"    around hit = {hex_at(first_hit - 8, 16)}")

    idc.qexit(0)


if __name__ == "__main__":
    main()
