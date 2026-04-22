"""ida_hexrays_dump.py — batch Hex-Rays decompiler on every IDA function.

IDA 9.0 + x64 Hex-Rays licensed here. We iterate over every function IDA
discovered during analysis (not just ones in jmap, since jmap's UFunction
address is the UObject pointer on the heap, not the native code EA) and
decompile each one to its own .c file under OUT_DIR.

By the time this script runs:
  * apply_jmap has named 2,200+ vtable slots as vtbl_<Class>.
  * apply_jmap has named the patternsleuth anchors (GMalloc, GEngine,
    UGameEngine::Tick, FEngineLoop::Tick, StaticConstructObject_Internal,
    etc.) so Hex-Rays pseudocode references them by name.

Env vars:
  OUT_DIR     — directory for .c output (will be created)
  SKIP_IF_EXISTS=1 — skip functions whose output file already exists
                    (useful for resuming an interrupted run)
  MAX_FUNCS   — stop after N functions, for testing
"""
import os
import sys

try:
    import ida_auto
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
    ida_kernwin.msg(f"[hexrays] {msg}\n")


def sanitize_filename(s: str) -> str:
    out = []
    for ch in s:
        if ch.isalnum() or ch in "._-":
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)[:200]  # Windows long-path guard


def decompile_to_string(ea: int) -> str | None:
    try:
        cfunc = ida_hexrays.decompile(ea)
    except Exception as exc:
        return None
    if not cfunc:
        return None
    try:
        return str(cfunc)
    except Exception:
        return None


def main() -> None:
    out_dir = os.environ.get("OUT_DIR")
    if not out_dir:
        log("ERROR: OUT_DIR env var required.")
        idc.qexit(1)
    os.makedirs(out_dir, exist_ok=True)

    skip_if_exists = os.environ.get("SKIP_IF_EXISTS") == "1"
    max_funcs_s = os.environ.get("MAX_FUNCS")
    max_funcs = int(max_funcs_s) if max_funcs_s else None

    if not ida_hexrays.init_hexrays_plugin():
        log("ERROR: Hex-Rays plugin failed to initialize.")
        idc.qexit(2)

    log("Waiting for auto-analysis...")
    ida_auto.auto_wait()

    named_only = os.environ.get("NAMED_ONLY", "1") == "1"

    log("Enumerating functions...")
    all_eas = list(idautils.Functions())
    if named_only:
        # Keep only functions with a non-default name. IDA 9 marks auto-
        # generated `sub_<ea>` names with FF_HASNAME clear and real names
        # with FF_HASNAME set — `idc.get_name_ea_simple` check is cheaper.
        func_eas = []
        for ea in all_eas:
            name = ida_name.get_ea_name(ea) or ""
            if name and not name.startswith("sub_") and not name.startswith("nullsub_"):
                func_eas.append(ea)
    else:
        func_eas = all_eas
    total = len(func_eas)
    log(f"Functions to decompile: {total} (of {len(all_eas)} total)")

    ok = fail = skipped = 0
    for i, ea in enumerate(func_eas):
        if max_funcs is not None and (ok + fail) >= max_funcs:
            break
        name = ida_name.get_ea_name(ea) or f"sub_{ea:X}"
        fn = idaapi.get_func(ea)
        if fn is None:
            continue
        # Skip thunks / library functions — they decompile to trivial one-liners
        # that aren't worth the noise or the decompile time.
        if fn.flags & (idaapi.FUNC_THUNK | idaapi.FUNC_LIB):
            continue

        out_path = os.path.join(out_dir, sanitize_filename(f"{name}.{ea:X}.c"))
        if skip_if_exists and os.path.exists(out_path):
            skipped += 1
            continue

        text = decompile_to_string(ea)
        if not text:
            fail += 1
            continue
        try:
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(f"// ea = {ea:#x} name = {name}\n\n")
                out.write(text)
                out.write("\n")
            ok += 1
        except OSError:
            fail += 1

        if (ok + fail) % 500 == 0:
            log(f"progress: {i+1}/{total} ok={ok} fail={fail}")

    log(f"DONE: ok={ok} fail={fail} skipped={skipped} total={total}")
    # don't save DB — we didn't modify anything, saves time
    idc.qexit(0)


if __name__ == "__main__":
    main()
