"""ida_find_ftext.py — locate FText::FText(FString&&) in the RoboQuest IDA db.

Strategy
--------
1. Walk IDA's string table looking for the MSVC RTTI type-descriptor name
   `.?AVFText@@`.
2. Find the DATA containing the string — that's the tail of a
   RTTITypeDescriptor (preceded by vftable ptr + spare ptr).
3. For every xref pointing *at the TypeDescriptor*, assume it's either a
   Complete Object Locator (COL) or a Base Class Descriptor. Walk them to
   find the COL (offset -0xC from vtable pointer → COL pointer).
4. With the vtable found, enumerate the class's virtual methods. The
   destructor slot is one of them; FText has a small virtual surface.
5. From references to the RTTI structures, find every function that
   constructs an FText — candidates for `FText::FText(FString&&)`.
6. Print each candidate with its first 32 bytes so we can pick the right
   one and extract the 22-byte AOB UE4SS needs.

The script works purely from the already-analyzed .i64 database — no
re-analysis required.
"""
import binascii
import os

try:
    import ida_auto
    import ida_bytes
    import ida_funcs
    import ida_kernwin
    import ida_name
    import ida_segment
    import ida_strlist
    import idaapi
    import idautils
    import idc
except ImportError as e:
    raise SystemExit(f"Must run inside IDA: {e}")


def log(msg: str) -> None:
    ida_kernwin.msg(f"[ftext] {msg}\n")


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


def find_string_ea(target: str) -> list[int]:
    """Match both ASCII-NUL-terminated and UTF-16-LE-NUL-terminated forms."""
    ascii_hits = find_bytes_all(target.encode("ascii") + b"\x00")
    wide_hits = find_bytes_all(target.encode("utf-16-le") + b"\x00\x00")
    return ascii_hits + wide_hits


def hex_at(ea: int, n: int = 32) -> str:
    b = ida_bytes.get_bytes(ea, n) or b""
    return " ".join(f"{x:02X}" for x in b)


def candidate_functions_from_rtti(type_desc_ea: int) -> list[int]:
    """Given a RTTITypeDescriptor EA, walk xrefs to reach the COL, then
    the vtable, then enumerate virtual methods."""
    candidates: set[int] = set()
    # xrefs TO the TypeDescriptor include COLs and BaseClassDescriptors
    for xr in idautils.XrefsTo(type_desc_ea, 0):
        src = xr.frm
        # Check if this looks like a COL: COL is a 20-byte struct starting with
        # `signature`, `offset`, `cdOffset`, `pTypeDescriptor`, `pClassDescriptor`.
        # The field offset for pTypeDescriptor in COL is +0x0C.
        col_candidate = src - 0x0C
        # vtable sits at `this - 0x08` where `this` holds a pointer to COL.
        # So search xrefs to col_candidate for vtable addresses.
        for xr2 in idautils.XrefsTo(col_candidate, 0):
            vtbl_field = xr2.frm  # where the COL pointer lives
            vtbl_ea = vtbl_field + 8  # vtable[0] starts right after COL ptr
            # Walk virtual methods until first bad pointer.
            ea = vtbl_ea
            slot = 0
            while True:
                fn = ida_bytes.get_qword(ea)
                if fn == 0 or fn == idaapi.BADADDR:
                    break
                if ida_funcs.get_func(fn) is None:
                    break
                candidates.add(fn)
                slot += 1
                ea += 8
                if slot > 32:  # FText has < 32 virtuals
                    break
    return sorted(candidates)


def constructor_candidates_from_xrefs(type_desc_ea: int) -> list[int]:
    """Callers that `lea` the TypeDescriptor (or directly reference the
    class's vtable) often include the constructor, which writes the
    vtable pointer into the new object."""
    candidates: set[int] = set()
    for xr in idautils.XrefsTo(type_desc_ea, 0):
        f = ida_funcs.get_func(xr.frm)
        if f:
            candidates.add(f.start_ea)
    return sorted(candidates)


def main() -> None:
    ida_auto.auto_wait()

    # Sanity: verify find_bytes works at all on this DB.
    sanity = find_string_ea("UnrealEngine4")
    log(f"sanity: found {len(sanity)} 'UnrealEngine4' matches; first={sanity[0] if sanity else 'none'}")

    # Check whether MSVC RTTI class names survive at all — look for any
    # generic '.?AV' or '.?AU' prefix strings (common classes/structs).
    any_rtti = find_bytes_all(b".?AV")
    log(f"rtti-prefix '.?AV' present: {len(any_rtti)} occurrences — {'RTTI present' if any_rtti else 'RTTI stripped'}")

    # Dump every RTTI class name — filter for FText/Text/String relevance.
    if any_rtti:
        matched = []
        for ea in any_rtti:
            s = ida_bytes.get_bytes(ea, 96)
            if not s:
                continue
            nul = s.find(b"\x00")
            if nul <= 4:
                continue
            name = s[:nul].decode("ascii", "ignore")
            if "Text" in name or "String" in name or "Name" in name or "Locale" in name:
                matched.append((ea, name))
        log(f"RTTI names mentioning Text/String/Name/Locale: {len(matched)}")
        for ea, name in matched[:80]:
            log(f"  {ea:#x}  {name}")

    # MSVC RTTI name for `class FText`: ".?AVFText@@"
    # FText has no virtuals so no RTTI TD — we target its *history* classes,
    # which do have virtuals.
    for name in (
        ".?AVFTextHistory@@",
        ".?AVFTextHistory_Base@@",
        ".?AVFTextHistory_NamedFormat@@",
        ".?AVFTextHistory_Transform@@",
        ".?AVFTextHistory_AsNumber@@",
        ".?AVFTextHistory_StringTableEntry@@",
        ".?AUITextData@@",
        ".?AVFTextSnapshot@@",
        ".?AVFTextStringHelper@@",
        ".?AVFText@@",
    ):
        hits = find_string_ea(name)
        log(f"Searched '{name}': {len(hits)} match(es).")
        for i, ea in enumerate(hits[:20]):
            log(f"  hit {i}: {ea:#x}  bytes={hex_at(ea, 24)}")
        if name == ".?AVFText@@" and hits:
            for h in hits[:5]:
                # The string lives at offset +0x10 inside the TypeDescriptor
                # (vftable ptr 8B, spare 8B, then name).
                type_desc = h - 0x10
                log(f"  -> candidate TypeDescriptor at {type_desc:#x}")
                cands = constructor_candidates_from_xrefs(type_desc)
                log(f"     {len(cands)} function candidates from TD xrefs:")
                for fn in cands[:30]:
                    fname = ida_name.get_ea_name(fn) or f"sub_{fn:X}"
                    log(f"       {fn:#x}  {fname}  prologue={hex_at(fn, 32)}")
                vtbl_cands = candidate_functions_from_rtti(type_desc)
                log(f"     {len(vtbl_cands)} virtual methods from vtable walk:")
                for fn in vtbl_cands[:16]:
                    fname = ida_name.get_ea_name(fn) or f"sub_{fn:X}"
                    log(f"       vtbl {fn:#x}  {fname}  prologue={hex_at(fn, 32)}")

    # Also — for each of the patternsleuth's 12 AOB patterns that failed,
    # try matching them without the | marker to see which bytes differ.
    log("Search complete.")
    idc.qexit(0)


if __name__ == "__main__":
    main()
