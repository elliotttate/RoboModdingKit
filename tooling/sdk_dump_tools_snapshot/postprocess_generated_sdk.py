from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from emit_genny_from_ue4ss import (
    KNOWN_EXTERNAL_SIZES,
    PRIMITIVE_SIZES,
    FieldDecl,
    TypeRef,
    iter_type_names,
    parse_field_decl,
)


TYPE_START_RE = re.compile(
    r"^\s*(class|struct)\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*:\s*[^{}]+)?(?:\s+0x[0-9A-Fa-f]+)?\s*\{$"
)
ENUM_START_RE = re.compile(
    r"^\s*enum\s+class\s+(?P<name>[A-Za-z_]\w*)\s*:\s*[A-Za-z_]\w*\s*\{$"
)
NS_START_RE = re.compile(r"^\s*namespace\s+(?P<name>[A-Za-z_]\w*)\s*\{$")
RAW_FIELD_GENCY_RE = re.compile(
    r"^\s*byte\s+(?P<name>[A-Za-z_]\w*)(?P<arrays>(?:\[\d+\])*)\s+@(?P<offset>0x[0-9A-Fa-f]+)\s*$"
)
RAW_FIELD_HEADER_RE = re.compile(
    r"^(?P<indent>\s*)byte\s+(?P<name>[A-Za-z_]\w*)(?P<arrays>(?:\[[^\]]+\])*)\s*;\s*//\s*(?P<offset>0x[0-9A-Fa-f]+)\s*$"
)
INCLUDE_RE = re.compile(r'^#include\s+"(?P<path>[^"]+)"\s*$')


@dataclass(frozen=True)
class TypeEntry:
    module: Optional[str]
    name: str
    path: Path


@dataclass(frozen=True)
class FallbackEntry:
    module: str
    owner: str
    field: FieldDecl
    offset: str

    @property
    def key(self) -> tuple[str, str]:
        return self.module, self.owner


def is_primitive_type(type_name: str) -> bool:
    return type_name in PRIMITIVE_SIZES or type_name == "void"


def is_safe_to_restore(field: FieldDecl) -> bool:
    return True


def build_type_inventory(
    sdk_root: Path,
) -> tuple[Dict[tuple[Optional[str], str], TypeEntry], Dict[str, list[TypeEntry]]]:
    by_key: dict[tuple[Optional[str], str], TypeEntry] = {}
    by_name: dict[str, list[TypeEntry]] = defaultdict(list)

    for header in sdk_root.rglob("*.hpp"):
        rel = header.relative_to(sdk_root)
        module: Optional[str]
        if len(rel.parts) == 1:
            module = None
        else:
            module = rel.parts[0]
        entry = TypeEntry(module=module, name=header.stem, path=header)
        by_key[(entry.module, entry.name)] = entry
        by_name[entry.name].append(entry)

    return by_key, by_name


def resolve_type_entry(
    type_name: str,
    current_module: Optional[str],
    by_key: Dict[tuple[Optional[str], str], TypeEntry],
    by_name: Dict[str, list[TypeEntry]],
) -> Optional[TypeEntry]:
    if is_primitive_type(type_name):
        return None

    if "." in type_name:
        module, name = type_name.split(".", 1)
        return by_key.get((module, name))

    if current_module is not None:
        same_module = by_key.get((current_module, type_name))
        if same_module is not None:
            return same_module

    root_type = by_key.get((None, type_name))
    if root_type is not None:
        return root_type

    matches = by_name.get(type_name, [])
    if len(matches) == 1:
        return matches[0]
    return matches[0] if matches else None


def format_cpp_type(
    ref: TypeRef,
    current_module: Optional[str],
    by_key: Dict[tuple[Optional[str], str], TypeEntry],
    by_name: Dict[str, list[TypeEntry]],
) -> str:
    if ref.base.startswith("T") or is_primitive_type(ref.base) or ref.base in KNOWN_EXTERNAL_SIZES:
        base = ref.base
    else:
        entry = resolve_type_entry(ref.base, current_module, by_key, by_name)
        if entry is not None and entry.module is not None:
            base = f"{entry.module}::{entry.name}"
        elif "." in ref.base:
            module, name = ref.base.split(".", 1)
            base = f"{module}::{name}"
        else:
            base = ref.base

    if ref.args:
        base += "<" + ", ".join(
            format_cpp_type(arg, current_module, by_key, by_name) for arg in ref.args
        ) + ">"

    if ref.pointer_depth:
        base += "*" * ref.pointer_depth

    return base


def collect_required_includes(
    field: FieldDecl,
    current_module: Optional[str],
    current_owner: str,
    header_path: Path,
    by_key: Dict[tuple[Optional[str], str], TypeEntry],
    by_name: Dict[str, list[TypeEntry]],
) -> list[str]:
    includes: set[str] = set()

    for type_name in iter_type_names(field.type_ref):
        entry = resolve_type_entry(type_name, current_module, by_key, by_name)
        if entry is None:
            continue
        if entry.path == header_path:
            continue
        if entry.module == current_module and entry.name == current_owner:
            continue
        include_path = Path(os.path.relpath(entry.path, header_path.parent)).as_posix()
        includes.add(include_path)

    return sorted(includes)


def parse_fallback_entries(genny_path: Path) -> list[FallbackEntry]:
    lines = genny_path.read_text(encoding="utf-8").splitlines()
    pending_original: Optional[str] = None
    entries: list[FallbackEntry] = []
    stack: list[tuple[str, Optional[str]]] = []

    for line in lines:
        stripped = line.strip()

        ns_match = NS_START_RE.match(line)
        if ns_match:
            stack.append(("namespace", ns_match.group("name")))
            continue

        type_match = TYPE_START_RE.match(line)
        if type_match:
            stack.append(("type", type_match.group("name")))
            pending_original = None
            continue

        enum_match = ENUM_START_RE.match(line)
        if enum_match:
            stack.append(("enum", enum_match.group("name")))
            continue

        if stripped == "}":
            if stack:
                stack.pop()
            pending_original = None
            continue

        current_module = next(
            (name for kind, name in reversed(stack) if kind == "namespace"),
            None,
        )
        current_owner = next(
            (name for kind, name in reversed(stack) if kind == "type"),
            None,
        )

        if current_module is None or current_owner is None:
            continue

        if stripped.startswith("// original: "):
            pending_original = stripped[len("// original: ") :]
            continue

        if not pending_original:
            continue

        raw_match = RAW_FIELD_GENCY_RE.match(line)
        if raw_match is None:
            if stripped and not stripped.startswith("//"):
                pending_original = None
            continue

        original_field = parse_field_decl(pending_original + ";")
        if original_field is not None:
            entries.append(
                FallbackEntry(
                    module=current_module,
                    owner=current_owner,
                    field=original_field,
                    offset=raw_match.group("offset").lower(),
                )
            )
        pending_original = None

    return entries


def replace_field_line(
    lines: list[str],
    entry: FallbackEntry,
    current_module: Optional[str],
    by_key: Dict[tuple[Optional[str], str], TypeEntry],
    by_name: Dict[str, list[TypeEntry]],
) -> bool:
    for idx, line in enumerate(lines):
        match = RAW_FIELD_HEADER_RE.match(line)
        if match is None:
            continue
        if match.group("name") != entry.field.name:
            continue
        if match.group("offset").lower() != entry.offset:
            continue

        indent = match.group("indent")
        arrays = "".join(f"[{dim}]" for dim in entry.field.array_dims)
        cpp_type = format_cpp_type(entry.field.type_ref, current_module, by_key, by_name)
        lines[idx] = f"{indent}{cpp_type} {entry.field.name}{arrays}; // {entry.offset}"
        return True

    return False


def insert_includes(lines: list[str], include_paths: Iterable[str]) -> list[str]:
    paths = list(include_paths)
    if not paths:
        return lines

    existing = {
        match.group("path")
        for line in lines
        if (match := INCLUDE_RE.match(line))
    }
    to_add = [path for path in paths if path not in existing]
    if not to_add:
        return lines

    insert_at = 1
    for idx, line in enumerate(lines):
        if INCLUDE_RE.match(line):
            insert_at = idx + 1

    new_lines = list(lines)
    for offset, path in enumerate(sorted(to_add)):
        new_lines.insert(insert_at + offset, f'#include "{path}"')
    return new_lines


def process_header(
    header_path: Path,
    current_module: Optional[str],
    owner: str,
    entries: list[FallbackEntry],
    by_key: Dict[tuple[Optional[str], str], TypeEntry],
    by_name: Dict[str, list[TypeEntry]],
) -> tuple[int, int]:
    text = header_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    restored = 0
    skipped = 0
    include_paths: set[str] = set()

    for entry in entries:
        if not is_safe_to_restore(entry.field):
            skipped += 1
            continue

        if replace_field_line(lines, entry, current_module, by_key, by_name):
            restored += 1
            include_paths.update(
                collect_required_includes(
                    entry.field,
                    current_module,
                    owner,
                    header_path,
                    by_key,
                    by_name,
                )
            )
        else:
            skipped += 1

    lines = insert_includes(lines, include_paths)
    header_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return restored, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore safe typed fields in generated SDK headers using .genny fallback metadata."
    )
    parser.add_argument("--genny", type=Path, required=True)
    parser.add_argument("--sdk-root", type=Path, required=True)
    args = parser.parse_args()

    entries = parse_fallback_entries(args.genny)
    by_key, by_name = build_type_inventory(args.sdk_root)

    grouped: dict[tuple[str, str], list[FallbackEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.key].append(entry)

    restored_total = 0
    skipped_total = 0
    missing_headers = 0

    for (module, owner), owner_entries in grouped.items():
        header_entry = by_key.get((module, owner))
        if header_entry is None:
            missing_headers += len(owner_entries)
            continue
        restored, skipped = process_header(
            header_entry.path,
            module,
            owner,
            owner_entries,
            by_key,
            by_name,
        )
        restored_total += restored
        skipped_total += skipped

    print(f"Fallback entries: {len(entries)}")
    print(f"Restored typed fields: {restored_total}")
    print(f"Skipped fields: {skipped_total}")
    print(f"Missing header matches: {missing_headers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
