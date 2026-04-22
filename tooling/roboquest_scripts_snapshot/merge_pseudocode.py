#!/usr/bin/env python3
"""merge_pseudocode.py — enrich the uproject with Hex-Rays pseudocode.

What it does
------------
1. Builds an index file at `_reference/PSEUDOCODE_INDEX.md` listing every
   decompiled function grouped by owning class (inferred from vtbl_ or
   explicit class::method naming).
2. For every UE4SS-generated .cpp stub in Source/, if a pseudocode file
   exists whose name matches the C++ method name, injects it as a
   /* ... */ comment block above the stub's empty body. The stub remains
   compilable; the pseudocode is a reference for future porting.

Matching rules (conservative — we want zero false positives):
  * Pseudocode filename format is `<symbol>.<ea>.c`.
  * Symbol form #1: `ClassName__MethodName` → matches `ClassName::MethodName`.
  * Symbol form #2: `vtbl_ClassName` → skip (multiple slots, not a single fn).
  * Symbol form #3: `PatternsleuthAnchor` (e.g. `FEngineLoop__Init`) → match
    by exact symbol equality against any cpp function name in the project.

If the same cpp has ambiguous matches (two pseudocode files match one
method) we skip it to avoid inserting the wrong one.
"""
from __future__ import annotations

import re
import sys
import os
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_ROOT = REPO_ROOT / "projects" / "RoboQuest_jmap_426_local"
PSEUDOCODE_DIR = Path(os.environ.get("ROBOMODDINGKIT_PSEUDOCODE_DIR", REPO_ROOT / "references" / "pseudocode"))
PROJECT_SRC = Path(os.environ.get("ROBOMODDINGKIT_PROJECT_SRC", DEFAULT_PROJECT_ROOT / "Source"))
INDEX_MD = Path(os.environ.get("ROBOMODDINGKIT_PSEUDOCODE_INDEX", DEFAULT_PROJECT_ROOT / "_reference" / "PSEUDOCODE_INDEX.md"))

CPP_FN_DEF = re.compile(
    r"^([A-Za-z_][\w:<>,\s*&]*?\s)(\w+)::(\w+)\s*\(([^)]*)\)\s*\{\s*\}\s*$",
    re.MULTILINE,
)


def parse_pseudocode_header(path: Path) -> tuple[int, str]:
    """Return (ea, name) from the first line of a pseudocode .c file."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            first = f.readline()
    except OSError:
        return 0, ""
    m = re.search(r"ea = (0x[0-9a-fA-F]+)\s+name = (\S+)", first)
    if not m:
        return 0, ""
    return int(m.group(1), 16), m.group(2)


def build_pseudocode_map() -> dict[str, list[Path]]:
    """Return a map from method-name → list of pseudocode .c paths that
    correspond to that name. Many names will point to one file; ambiguous
    names (multiple files) are kept as a list so we can skip them."""
    by_name: dict[str, list[Path]] = defaultdict(list)
    for c_path in PSEUDOCODE_DIR.glob("*.c"):
        _, name = parse_pseudocode_header(c_path)
        if not name:
            continue
        by_name[name].append(c_path)
        # Also index demangled form: `ClassName__Method` → `Method`
        if "__" in name:
            _, _, method_only = name.rpartition("__")
            by_name[method_only].append(c_path)
    return by_name


def write_index(by_name: dict[str, list[Path]]) -> None:
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Hex-Rays pseudocode index",
        "",
        "Decompiled by IDA 9.0 Hex-Rays x64 from the RoboQuest shipping binary.",
        f"Total files: {sum(len(v) for v in by_name.values())} entries over {len(by_name)} symbol names.",
        "",
        "## By class (from `ClassName__Method` filenames)",
        "",
    ]
    classes: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    patternsleuth: list[tuple[str, Path]] = []
    vtables: list[tuple[str, Path]] = []
    other: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for name, paths in sorted(by_name.items()):
        for p in paths:
            if p in seen:
                continue
            seen.add(p)
            if "__" in name and not name.startswith("vtbl_"):
                cls, _, method = name.partition("__")
                classes[cls].append((method, p))
            elif name.startswith("vtbl_"):
                vtables.append((name, p))
            elif name in {"FEngineLoop__Init", "FEngineLoop__Tick", "UGameEngine__Tick",
                          "StaticConstructObject_Internal", "UObject__SkipFunction",
                          "FUObjectHashTables__Get", "FFrame__StepExplicitProperty",
                          "StaticFindObjectFast", "WinMain"}:
                patternsleuth.append((name, p))
            else:
                other.append((name, p))

    for cls in sorted(classes):
        lines.append(f"### `{cls}`")
        for method, p in sorted(classes[cls]):
            lines.append(f"- `{method}` — [{p.name}](../../../pseudocode/{p.name})")
        lines.append("")

    lines += ["## Patternsleuth-anchored symbols", ""]
    for name, p in sorted(patternsleuth):
        lines.append(f"- `{name}` — [{p.name}](../../../pseudocode/{p.name})")
    lines += ["", "## Vtable anchors", ""]
    for name, p in sorted(vtables):
        lines.append(f"- `{name}` — [{p.name}](../../../pseudocode/{p.name})")
    lines += ["", "## Other named functions", ""]
    for name, p in sorted(other):
        lines.append(f"- `{name}` — [{p.name}](../../../pseudocode/{p.name})")

    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {INDEX_MD}")


def inject_pseudocode(by_name: dict[str, list[Path]]) -> None:
    """Walk every .cpp in Source/, try to match each stub body to a
    pseudocode .c file, inject as a comment."""
    injected = skipped = 0
    cpp_files = list(PROJECT_SRC.rglob("*.cpp"))
    print(f"Scanning {len(cpp_files)} cpp files for matches...")
    for cpp in cpp_files:
        try:
            text = cpp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = list(CPP_FN_DEF.finditer(text))
        if not matches:
            continue
        changed = False
        new_text = text
        for m in matches:
            cls = m.group(2)
            method = m.group(3)
            key = f"{cls}__{method}"
            paths = by_name.get(key) or by_name.get(method) or []
            # Require a single-match to inject.
            if len(paths) != 1:
                continue
            pseudocode = paths[0].read_text(encoding="utf-8", errors="replace")
            # Strip the original header comment; re-wrap as a block
            comment = f"/* ---- IDA Hex-Rays pseudocode for {cls}::{method} ----\n"
            comment += pseudocode.rstrip() + "\n*/\n"
            # Inject above the matched cpp function definition
            start = m.start()
            new_text = new_text[:start] + comment + new_text[start:]
            changed = True
            injected += 1
        if changed:
            try:
                cpp.write_text(new_text, encoding="utf-8")
            except OSError:
                skipped += 1
    print(f"Injected {injected} pseudocode comments across .cpp stubs. skipped={skipped}")


def main() -> int:
    if not PSEUDOCODE_DIR.is_dir():
        print(f"no pseudocode dir at {PSEUDOCODE_DIR}", file=sys.stderr)
        return 1
    by_name = build_pseudocode_map()
    write_index(by_name)
    inject_pseudocode(by_name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
