"""ida_apply_jmap.py — apply jmap reflection names to an IDA 9.0 database.

IDA 9.0 removed the dedicated `ida_enum` / `ida_struct` modules (consolidated
into `ida_typeinf`), so this script focuses on the naming work — which is
what drives better Hex-Rays pseudocode — and leaves struct/enum type
creation for future work.

Naming applied:
  * Every UFunction at its native entry address → `UFunc_<ShortName>`.
  * Every UClass vtable at the address listed in `class.instance_vtable`
    → `vtbl_<ClassShortName>`.
  * The patternsleuth anchors from <jmap_stem>.resolutions.json
    (GMalloc, GEngine, Main, FEngineLoop::Tick, etc.) → canonical names.

The jmap records runtime addresses from the dumped game process, and IDA's
image base differs because ASLR rebases the exe each launch. We compute the
delta once and subtract it from every pointer so the names land on the
correct static EA.

Env vars (required):
  JMAP_PATH   — absolute path to the .jmap JSON
  RES_PATH    — absolute path to the .resolutions.json sidecar
                (optional; skipped if the file doesn't exist)
"""
import json
import os

try:
    import ida_auto
    import ida_kernwin
    import ida_name
    import ida_segment
    import idaapi
    import idc
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"Must run inside IDA: {e}")


def log(msg: str) -> None:
    ida_kernwin.msg(f"[jmap] {msg}\n")


def short_name(path: str) -> str:
    for sep in ("/", ".", ":"):
        if sep in path:
            path = path.rsplit(sep, 1)[-1]
    return path


def sanitize(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    return "".join(out) or "_"


def addr_in_image(ea: int) -> bool:
    return ida_segment.getseg(ea) is not None


def parse_addr(v) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 16) if v.lower().startswith("0x") else int(v, 16)
    return 0


def compute_rebase(jmap: dict) -> int:
    return parse_addr(jmap.get("image_base_address") or 0) - idaapi.get_imagebase()


def main() -> None:
    jmap_path = os.environ.get("JMAP_PATH")
    res_path = os.environ.get("RES_PATH")
    if not jmap_path:
        log("ERROR: set JMAP_PATH to the .jmap JSON before running.")
        idc.qexit(1)

    log("Waiting for auto-analysis to finish...")
    ida_auto.auto_wait()

    log(f"Reading {jmap_path}")
    with open(jmap_path, "r", encoding="utf-8") as f:
        jmap = json.load(f)

    rebase = compute_rebase(jmap)
    log(f"Rebase delta = {rebase:#x}")

    objects = jmap.get("objects", {})

    # Phase 1: UFunction entry points
    named_funcs = 0
    for path, obj in objects.items():
        if obj.get("type") != "Function":
            continue
        addr_s = obj.get("address")
        if not addr_s:
            continue
        try:
            ea = parse_addr(addr_s) - rebase
        except (ValueError, TypeError):
            continue
        if not addr_in_image(ea):
            continue
        outer = obj.get("outer") or ""
        owner = short_name(outer) if outer else "Unknown"
        sym = sanitize(f"UFunc_{owner}__{short_name(path)}")
        if ida_name.set_name(ea, sym, ida_name.SN_NOWARN | ida_name.SN_FORCE):
            named_funcs += 1
    log(f"Named {named_funcs} UFunction entry points.")

    # Phase 2: vtables
    vt_to_class = {}
    for path, obj in objects.items():
        if obj.get("type") != "Class":
            continue
        vt = obj.get("instance_vtable")
        if vt:
            vt_to_class[vt] = path
    vtables = jmap.get("vtables") or {}
    named_vtbl = 0
    for vt_addr_s in vtables.keys():
        try:
            ea = parse_addr(vt_addr_s) - rebase
        except (ValueError, TypeError):
            continue
        if not addr_in_image(ea):
            continue
        cls = vt_to_class.get(vt_addr_s)
        if not cls:
            continue
        sym = sanitize(f"vtbl_{short_name(cls)}")
        if ida_name.set_name(ea, sym, ida_name.SN_NOWARN | ida_name.SN_FORCE):
            named_vtbl += 1
    log(f"Named {named_vtbl} vtable slots.")

    # Phase 3: patternsleuth anchors
    named_anchors = 0
    if res_path and os.path.exists(res_path):
        with open(res_path, "r", encoding="utf-8") as f:
            res = json.load(f)
        # The resolutions file records addresses from the SAME game session
        # that produced the .jmap, so the same rebase applies.
        dump_base = parse_addr(res.get("image_base_address_at_dump") or 0)
        anchor_rebase = dump_base - idaapi.get_imagebase() if dump_base else rebase
        for name, addr_s in (res.get("resolvers") or {}).items():
            try:
                ea = parse_addr(addr_s) - anchor_rebase
            except (ValueError, TypeError):
                continue
            if not addr_in_image(ea):
                continue
            if ida_name.set_name(ea, sanitize(name), ida_name.SN_NOWARN | ida_name.SN_FORCE):
                named_anchors += 1
        log(f"Named {named_anchors} patternsleuth anchors from {res_path}.")
    else:
        log("No resolutions sidecar — skipping patternsleuth anchors.")

    log("Saving database...")
    idc.save_database("")
    log("Done.")
    idc.qexit(0)


if __name__ == "__main__":
    main()
