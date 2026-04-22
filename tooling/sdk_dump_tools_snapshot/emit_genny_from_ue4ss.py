from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


PRIMITIVE_SIZES: dict[str, int] = {
    "bool": 1,
    "byte": 1,
    "uint8": 1,
    "int8": 1,
    "char": 1,
    "wchar_t": 2,
    "uint16": 2,
    "int16": 2,
    "short": 2,
    "ushort": 2,
    "uint32": 4,
    "int32": 4,
    "int": 4,
    "unsigned": 4,
    "float": 4,
    "uint64": 8,
    "int64": 8,
    "double": 8,
    "uintptr_t": 8,
    "size_t": 8,
}

KNOWN_EXTERNAL_SIZES: dict[str, int] = {
    "FColor": 4,
    "FDateTime": 8,
    "FFrameNumber": 4,
    "FGuid": 16,
    "FIntPoint": 8,
    "FIntVector": 12,
    "FLinearColor": 16,
    "FName": 8,
    "FQuat": 16,
    "FRotator": 12,
    "FSoftObjectPath": 24,
    "FString": 16,
    "FTimespan": 8,
    "FTransform": 48,
    "FTwoVectors": 24,
    "FVector": 12,
    "FVector2D": 8,
    "FVector4": 16,
}

GENERIC_SIZES: dict[str, int] = {
    "TArray": 16,
    "TBitArray": 32,
    "TEnumAsByte": 1,
    "TLazyObjectPtr": 8,
    "TMap": 80,
    "TScriptInterface": 16,
    "TSet": 80,
    "TSoftClassPtr": 40,
    "TSoftObjectPtr": 40,
    "TSubclassOf": 8,
    "TWeakObjectPtr": 8,
}

IGNORED_BASES = {"IInterface"}

CLASS_DEF_RE = re.compile(
    r"^(class|struct)\s+(?:[A-Z0-9_]+_API\s+)?(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*:\s*(?P<bases>[^{]+))?\s*\{$"
)
ENUM_DEF_RE = re.compile(
    r"^enum\s+class\s+(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<underlying>[A-Za-z_]\w*)\s*\{$"
)
TOP_LEVEL_OBJECT_RE = re.compile(
    r"^\[(?P<addr>[0-9A-Fa-f]+)\] "
    r"(?P<kind>Class|ScriptStruct|Struct|Enum|Function|DelegateFunction) "
    r"/Script/(?P<module>[^.]+)\.(?P<name>[^ :]+)"
    r"(?: .*?\[sps: (?P<super>[0-9A-Fa-f]+)\])?"
)
TOP_LEVEL_PROPERTY_RE = re.compile(
    r"^\[[0-9A-Fa-f]+\] (?P<prop_kind>\w+)Property "
    r"/Script/(?P<module>[^.]+)\.(?P<owner>[^:]+):(?P<field>[^\s:\[]+) "
    r"\[o: (?P<offset>[0-9A-Fa-f]+)\]"
)


@dataclass
class TypeRef:
    base: str
    args: list["TypeRef"] = field(default_factory=list)
    pointer_depth: int = 0

    def format(self) -> str:
        text = self.base
        if self.args:
            text += "<" + ", ".join(arg.format() for arg in self.args) + ">"
        if self.pointer_depth:
            text += "*" * self.pointer_depth
        return text


@dataclass
class FieldDecl:
    name: str
    type_ref: TypeRef
    array_dims: list[int]
    offset: Optional[int] = None

    def format_type(self) -> str:
        return self.type_ref.format()


@dataclass
class TypeDecl:
    module: str
    name: str
    kind: str
    underlying: Optional[str] = None
    enum_values: list[tuple[str, Optional[str]]] = field(default_factory=list)
    fields: list[FieldDecl] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    delegates: list[str] = field(default_factory=list)
    size: Optional[int] = None
    span_candidate: Optional[int] = None
    parent_size_candidate: Optional[int] = None

    def primary_parent(self) -> Optional[str]:
        for base in self.bases:
            if base in IGNORED_BASES:
                continue
            if base.startswith("II"):
                continue
            return base
        return None

    def field_map(self) -> dict[str, FieldDecl]:
        return {field.name: field for field in self.fields}


def strip_comments(text: str) -> str:
    return re.sub(r"//.*", "", text).strip()


def split_template_args(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in text:
        if ch == "<":
            depth += 1
            cur.append(ch)
        elif ch == ">":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def sanitize_type_name(name: str) -> str:
    return name.replace("::", "_").strip()


def parse_type_expr(text: str) -> TypeRef:
    text = " ".join(text.replace("const ", "").replace("volatile ", "").split())
    text = re.sub(r"\b(class|struct|enum class|enum)\s+", "", text).strip()
    pointer_depth = 0
    while text.endswith("*"):
        pointer_depth += 1
        text = text[:-1].strip()

    if "<" not in text:
        return TypeRef(base=sanitize_type_name(text), pointer_depth=pointer_depth)

    base, rest = text.split("<", 1)
    inner = rest.rsplit(">", 1)[0]
    args = [parse_type_expr(part) for part in split_template_args(inner)]
    return TypeRef(base=sanitize_type_name(base), args=args, pointer_depth=pointer_depth)


def parse_field_decl(text: str) -> Optional[FieldDecl]:
    cleaned = " ".join(strip_comments(text).rstrip(";").split())
    match = re.match(
        r"^(?P<type>.+?)\s+(?P<name>[A-Za-z_]\w*)(?P<arrays>(?:\s*\[\d+\])*)$",
        cleaned,
    )
    if not match:
        return None

    array_dims = [int(num) for num in re.findall(r"\[(\d+)\]", match.group("arrays"))]
    return FieldDecl(
        name=match.group("name"),
        type_ref=parse_type_expr(match.group("type")),
        array_dims=array_dims,
    )


def parse_uht_header(path: Path, module: str) -> list[TypeDecl]:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    i = 0
    decls: list[TypeDecl] = []

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("UENUM"):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("enum class"):
                i += 1
            if i >= len(lines):
                break

            header = lines[i].strip()
            match = ENUM_DEF_RE.match(header)
            if not match:
                i += 1
                continue

            enum_decl = TypeDecl(
                module=module,
                name=match.group("name"),
                kind="enum",
                underlying=match.group("underlying"),
            )
            i += 1
            while i < len(lines):
                cur = strip_comments(lines[i]).strip()
                if cur == "};":
                    break
                if cur:
                    cur = cur.rstrip(",")
                    if cur:
                        if "=" in cur:
                            name, value = [part.strip() for part in cur.split("=", 1)]
                            enum_decl.enum_values.append((name, value))
                        else:
                            enum_decl.enum_values.append((cur, None))
                i += 1
            decls.append(enum_decl)
            i += 1
            continue

        if line.startswith("UCLASS") or line.startswith("USTRUCT"):
            kind = "class" if line.startswith("UCLASS") else "struct"
            i += 1
            while i < len(lines) and "{" not in lines[i]:
                i += 1
            if i >= len(lines):
                break

            header = " ".join(strip_comments(lines[i]).split())
            match = CLASS_DEF_RE.match(header)
            if not match:
                i += 1
                continue

            bases: list[str] = []
            if match.group("bases"):
                for part in match.group("bases").split(","):
                    piece = part.strip()
                    piece = re.sub(r"^public\s+", "", piece).strip()
                    if piece:
                        bases.append(sanitize_type_name(piece))

            type_decl = TypeDecl(
                module=module,
                name=match.group("name"),
                kind=kind,
                bases=bases,
            )

            i += 1
            pending_property = False
            field_accum: list[str] = []
            while i < len(lines):
                cur = lines[i].strip()
                if cur == "};":
                    break

                if cur.endswith(":") and cur[:-1] in {"public", "private", "protected"}:
                    i += 1
                    continue

                if cur.startswith("DECLARE_"):
                    delegate_match = re.match(r"^DECLARE_[^(]+\(\s*([A-Za-z_]\w*)", cur)
                    if delegate_match:
                        type_decl.delegates.append(delegate_match.group(1))
                    i += 1
                    continue

                if cur.startswith("UPROPERTY"):
                    pending_property = True
                    field_accum = []
                    i += 1
                    continue

                if pending_property:
                    field_accum.append(cur)
                    if ";" in cur:
                        field_decl = parse_field_decl(" ".join(field_accum))
                        if field_decl is not None:
                            type_decl.fields.append(field_decl)
                        pending_property = False
                    i += 1
                    continue

                i += 1

            decls.append(type_decl)
            i += 1
            continue

        i += 1

    return decls


def parse_uht_modules(uht_root: Path, modules: list[str]) -> dict[tuple[str, str], TypeDecl]:
    decls: dict[tuple[str, str], TypeDecl] = {}
    for module in modules:
        public_dir = uht_root / module / "Public"
        if not public_dir.is_dir():
            continue
        for header in sorted(public_dir.glob("*.h")):
            for decl in parse_uht_header(header, module):
                decls[(decl.module, decl.name)] = decl
    return decls


def parse_object_dump(
    object_dump: Path, modules: set[str]
) -> tuple[
    dict[tuple[str, str], list[tuple[int, str]]],
    dict[str, tuple[str, str, str]],
]:
    fields_by_owner: dict[tuple[str, str], list[tuple[int, str]]] = {}
    object_by_addr: dict[str, tuple[str, str, str]] = {}

    with object_dump.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()

            obj_match = TOP_LEVEL_OBJECT_RE.match(line)
            if obj_match:
                module = obj_match.group("module")
                name = obj_match.group("name")
                kind = obj_match.group("kind")
                object_by_addr[obj_match.group("addr").lower()] = (module, name, kind)
                continue

            prop_match = TOP_LEVEL_PROPERTY_RE.match(line)
            if not prop_match:
                continue

            module = prop_match.group("module")
            if module not in modules:
                continue

            owner = prop_match.group("owner")
            field_name = prop_match.group("field")
            offset = int(prop_match.group("offset"), 16)
            fields_by_owner.setdefault((module, owner), []).append((offset, field_name))

    for entries in fields_by_owner.values():
        entries.sort(key=lambda item: item[0])

    return fields_by_owner, object_by_addr


def normalize_bases(type_name_to_module: dict[str, str], current_module: str, ref: TypeRef) -> TypeRef:
    base = ref.base
    if "." not in base and base in type_name_to_module and type_name_to_module[base] != current_module:
        base = f"{type_name_to_module[base]}.{base}"
    return TypeRef(
        base=base,
        args=[normalize_bases(type_name_to_module, current_module, arg) for arg in ref.args],
        pointer_depth=ref.pointer_depth,
    )


def gather_referenced_types(decls: Iterable[TypeDecl]) -> set[str]:
    names: set[str] = set()
    for decl in decls:
        for base in decl.bases:
            names.add(base)
        for field in decl.fields:
            stack = [field.type_ref]
            while stack:
                cur = stack.pop()
                names.add(cur.base)
                stack.extend(cur.args)
        for delegate in decl.delegates:
            names.add(delegate)
    return names


def iter_type_names(ref: TypeRef) -> Iterable[str]:
    yield ref.base
    for arg in ref.args:
        yield from iter_type_names(arg)


def decl_aliases(decl: TypeDecl) -> set[str]:
    aliases = {decl.name}
    if decl.kind == "class" and decl.name.startswith(("A", "U")) and len(decl.name) > 1:
        aliases.add(decl.name[1:])
    if decl.kind == "struct" and decl.name.startswith("F") and len(decl.name) > 1:
        aliases.add(decl.name[1:])
    return aliases


def gather_module_delegates(decls: Iterable[TypeDecl]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for decl in decls:
        if decl.delegates:
            result.setdefault(decl.module, set()).update(decl.delegates)
    return result


def dims_product(dims: list[int]) -> int:
    total = 1
    for dim in dims:
        total *= dim
    return total


def format_size(num: int) -> str:
    return f"0x{num:X}"


def choose_placeholder_kind(name: str) -> str:
    if name.startswith("E"):
        return "enum"
    if name.startswith(("A", "U", "I")):
        return "class"
    return "struct"


def order_modules(modules: list[str], decls: dict[tuple[str, str], TypeDecl]) -> list[str]:
    type_name_to_module = {decl.name: decl.module for decl in decls.values()}
    deps: dict[str, set[str]] = {module: set() for module in modules}
    for decl in decls.values():
        for base in decl.bases:
            other = type_name_to_module.get(base)
            if other and other != decl.module:
                deps[decl.module].add(other)
        for field in decl.fields:
            for type_name in iter_type_names(field.type_ref):
                other = type_name_to_module.get(type_name)
                if other and other != decl.module:
                    deps[decl.module].add(other)

    ordered: list[str] = []
    seen: set[str] = set()
    visiting: set[str] = set()

    def visit(module: str) -> None:
        if module in seen:
            return
        if module in visiting:
            return
        visiting.add(module)
        for dep in sorted(deps.get(module, set())):
            visit(dep)
        visiting.remove(module)
        seen.add(module)
        ordered.append(module)

    for module in modules:
        visit(module)

    return ordered


def sort_module_decls(module: str, decls: list[TypeDecl], type_name_to_module: dict[str, str]) -> list[TypeDecl]:
    by_name = {decl.name: decl for decl in decls}
    ordered: list[TypeDecl] = []
    hard_deps: dict[str, set[str]] = {}
    soft_deps: dict[str, set[str]] = {}

    for decl in decls:
        hard: set[str] = set()
        soft: set[str] = set()

        for base in decl.bases:
            if type_name_to_module.get(base) == module and base in by_name:
                hard.add(base)

        for field in decl.fields:
            for type_name in iter_type_names(field.type_ref):
                if (
                    type_name_to_module.get(type_name) == module
                    and type_name in by_name
                    and type_name != decl.name
                ):
                    soft.add(type_name)

        hard_deps[decl.name] = hard
        soft_deps[decl.name] = soft

    remaining = set(by_name)
    resolved: set[str] = set()

    while remaining:
        ready = sorted(
            (
                name
                for name in remaining
                if hard_deps[name].issubset(resolved)
            ),
            key=lambda name: (
                len(soft_deps[name] - resolved),
                by_name[name].kind,
                name,
            ),
        )

        if not ready:
            ready = sorted(
                remaining,
                key=lambda name: (
                    len(hard_deps[name] - resolved),
                    len(soft_deps[name] - resolved),
                    by_name[name].kind,
                    name,
                ),
            )

        next_name = ready[0]
        ordered.append(by_name[next_name])
        resolved.add(next_name)
        remaining.remove(next_name)

    return ordered


def resolve_decl_ref(
    type_name: str, current_module: str, type_name_to_module: dict[str, str]
) -> Optional[tuple[str, str]]:
    if "." in type_name:
        module, name = type_name.split(".", 1)
        return module, name

    module = type_name_to_module.get(type_name)
    if module is None:
        return None

    return module, type_name


def full_decl_name(module: str, name: str) -> str:
    return f"{module}.{name}"


def field_storage_size(
    decl: TypeDecl, field_index: int, size_map: dict[str, int]
) -> Optional[int]:
    field = decl.fields[field_index]
    if field.offset is None:
        return None

    for next_field in decl.fields[field_index + 1 :]:
        if next_field.offset is not None and next_field.offset > field.offset:
            return next_field.offset - field.offset

    decl_size = size_map.get(decl.name)
    if decl_size is not None and decl_size > field.offset:
        return decl_size - field.offset

    field_size = resolve_type_size(field.type_ref, size_map)
    if field_size is None:
        return None

    return field_size * dims_product(field.array_dims)


def unresolved_field_type_names(
    field: FieldDecl,
    current_module: str,
    current_decl_name: str,
    type_name_to_module: dict[str, str],
    emitted_type_names: set[str],
) -> list[str]:
    current_full_name = full_decl_name(current_module, current_decl_name)
    unresolved: list[str] = []
    seen: set[str] = set()

    for type_name in iter_type_names(field.type_ref):
        resolved = resolve_decl_ref(type_name, current_module, type_name_to_module)
        if resolved is None:
            continue

        full_name = full_decl_name(*resolved)
        if full_name == current_full_name or full_name in emitted_type_names or full_name in seen:
            continue

        unresolved.append(full_name)
        seen.add(full_name)

    return unresolved


def has_nested_template_args(ref: TypeRef) -> bool:
    for arg in ref.args:
        if arg.args or has_nested_template_args(arg):
            return True
    return False


def compute_span_candidates(
    decls: dict[tuple[str, str], TypeDecl],
    field_offsets: dict[tuple[str, str], list[tuple[int, str]]],
) -> tuple[dict[str, int], dict[str, int]]:
    spans: dict[str, int] = {}
    parent_candidates: dict[str, int] = {}

    alias_lookup: dict[tuple[str, str], TypeDecl] = {}
    for decl in decls.values():
        for alias in decl_aliases(decl):
            alias_lookup[(decl.module, alias)] = decl

    for key, offsets in field_offsets.items():
        decl = alias_lookup.get(key)
        if decl is None:
            continue

        field_map = decl.field_map()
        matched_offsets: list[int] = []
        for idx, (offset, field_name) in enumerate(offsets):
            field = field_map.get(field_name)
            if field is None:
                continue
            field.offset = offset
            matched_offsets.append(offset)

            if idx + 1 < len(offsets):
                next_offset = offsets[idx + 1][0]
                gap = next_offset - offset
                if gap > 0:
                    count = dims_product(field.array_dims)
                    candidate = gap
                    if count > 1 and gap % count == 0:
                        candidate = gap // count
                    current = spans.get(field.type_ref.base)
                    if current is None or candidate < current:
                        spans[field.type_ref.base] = candidate

        if matched_offsets:
            parent = decl.primary_parent()
            if parent:
                first_offset = matched_offsets[0]
                current_parent = parent_candidates.get(parent)
                if current_parent is None or first_offset < current_parent:
                    parent_candidates[parent] = first_offset

    for decl in decls.values():
        decl.span_candidate = spans.get(decl.name)
        if decl.primary_parent():
            decl.parent_size_candidate = parent_candidates.get(decl.primary_parent())

    return spans, parent_candidates


def guess_generic_size(name: str) -> int:
    return GENERIC_SIZES.get(name, 16 if name.startswith("T") else 1)


def resolve_type_size(ref: TypeRef, size_map: dict[str, int]) -> Optional[int]:
    if ref.pointer_depth > 0:
        return 8

    if ref.base in PRIMITIVE_SIZES:
        return PRIMITIVE_SIZES[ref.base]

    if ref.base in GENERIC_SIZES or ref.base.startswith("T"):
        return guess_generic_size(ref.base)

    return size_map.get(ref.base)


def resolve_decl_sizes(
    decls: dict[tuple[str, str], TypeDecl],
    spans: dict[str, int],
    parent_candidates: dict[str, int],
    referenced_types: set[str],
) -> dict[str, int]:
    size_map: dict[str, int] = {}
    size_map.update(PRIMITIVE_SIZES)
    size_map.update(KNOWN_EXTERNAL_SIZES)

    for decl in decls.values():
        if decl.kind == "enum" and decl.underlying:
            size_map[decl.name] = PRIMITIVE_SIZES.get(decl.underlying, 1)

    for name in referenced_types:
        if name in size_map:
            continue
        if name in parent_candidates:
            size_map[name] = parent_candidates[name]
        elif name in spans:
            size_map[name] = spans[name]

    for _ in range(20):
        changed = False
        for decl in decls.values():
            if decl.name in size_map and decl.kind == "enum":
                continue

            size_lb = 0
            all_known = True
            for field in decl.fields:
                if field.offset is None:
                    continue
                field_size = resolve_type_size(field.type_ref, size_map)
                if field_size is None:
                    all_known = False
                    field_size = 1
                field_end = field.offset + field_size * dims_product(field.array_dims)
                size_lb = max(size_lb, field_end)

            candidates = [candidate for candidate in (decl.span_candidate, decl.parent_size_candidate) if candidate is not None and candidate >= size_lb]
            if candidates:
                new_size = min(candidates)
            elif all_known and size_lb > 0:
                new_size = size_lb
            else:
                continue

            old_size = size_map.get(decl.name)
            if old_size != new_size:
                size_map[decl.name] = new_size
                changed = True

        if not changed:
            break

    for name in referenced_types:
        if name in size_map:
            continue
        if name in parent_candidates:
            size_map[name] = parent_candidates[name]
        elif name in spans:
            size_map[name] = spans[name]
        elif name.startswith("T"):
            size_map[name] = guess_generic_size(name)
        elif name.startswith("E"):
            size_map[name] = 1
        else:
            size_map[name] = 1

    return size_map


def emit_genny(
    decls: dict[tuple[str, str], TypeDecl],
    modules: list[str],
    size_map: dict[str, int],
    referenced_types: set[str],
    out_path: Path,
) -> None:
    modules = order_modules(modules, decls)
    type_name_to_module = {decl.name: decl.module for decl in decls.values()}
    module_delegates = gather_module_delegates(decls.values())
    used_generics = sorted({name for name in referenced_types if name.startswith("T")})
    module_buckets: dict[str, list[TypeDecl]] = {module: [] for module in modules}
    emitted_type_names: set[str] = set()

    for decl in decls.values():
        for idx, field in enumerate(decl.fields):
            decl.fields[idx] = FieldDecl(
                name=field.name,
                type_ref=normalize_bases(type_name_to_module, decl.module, field.type_ref),
                array_dims=field.array_dims,
                offset=field.offset,
            )
        module_buckets[decl.module].append(decl)

    lines: list[str] = []
    lines.extend(
        [
            "// Auto-generated from UE4SS UHTHeaderDump + ObjectDump for RoboQuest.",
            "// Intended as a ReGenny .genny input file and first-pass SdkGenny source.",
            "",
            "type bool 1 [[bool]]",
            "type byte 1 [[u8]]",
            "type char 1",
            "type wchar_t 2",
            "type int8 1 [[i8]]",
            "type uint8 1 [[u8]]",
            "type int16 2 [[i16]]",
            "type uint16 2 [[u16]]",
            "type short 2 [[i16]]",
            "type ushort 2 [[u16]]",
            "type int 4 [[i32]]",
            "type int32 4 [[i32]]",
            "type uint32 4 [[u32]]",
            "type float 4 [[f32]]",
            "type int64 8 [[i64]]",
            "type uint64 8 [[u64]]",
            "type uintptr_t 8 [[u64]]",
            "type size_t 8 [[u64]]",
            "type double 8 [[f64]]",
            "",
        ]
    )

    if "TArray" in used_generics:
        lines.extend(
            [
                "template <typename T> struct TArray 0x10 {",
                "    T* Data @0x0",
                "    int32 Num @0x8",
                "    int32 Max @0xC",
                "}",
                "",
            ]
        )
    if "TMap" in used_generics:
        lines.extend(
            [
                "template <typename K, typename V> struct TMap 0x50 {",
                "    byte Opaque[80] @0x0",
                "}",
                "",
            ]
        )
    if "TSet" in used_generics:
        lines.extend(
            [
                "template <typename T> struct TSet 0x50 {",
                "    byte Opaque[80] @0x0",
                "}",
                "",
            ]
        )
    if "TSubclassOf" in used_generics:
        lines.extend(
            [
                "template <typename T> struct TSubclassOf 0x8 {",
                "    uintptr_t Value @0x0",
                "}",
                "",
            ]
        )
    if "TWeakObjectPtr" in used_generics:
        lines.extend(
            [
                "template <typename T> struct TWeakObjectPtr 0x8 {",
                "    uint32 ObjectIndex @0x0",
                "    uint32 ObjectSerial @0x4",
                "}",
                "",
            ]
        )
    if "TScriptInterface" in used_generics:
        lines.extend(
            [
                "template <typename T> struct TScriptInterface 0x10 {",
                "    uintptr_t ObjectPointer @0x0",
                "    uintptr_t InterfacePointer @0x8",
                "}",
                "",
            ]
        )
    for generic_name in used_generics:
        if generic_name in {"TArray", "TMap", "TSet", "TSubclassOf", "TWeakObjectPtr", "TScriptInterface"}:
            continue
        size = size_map.get(generic_name, guess_generic_size(generic_name))
        if generic_name == "TEnumAsByte":
            lines.extend(
                [
                    "template <typename T> struct TEnumAsByte 0x1 {",
                    "    byte Value @0x0",
                    "}",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"template <typename T> struct {generic_name} {format_size(size)} {{",
                f"    byte Opaque[{size}] @0x0",
                "}",
                "",
            ]
        )

    placeholder_names = sorted(
        name
        for name in referenced_types
        if name not in type_name_to_module
        and name not in PRIMITIVE_SIZES
        and not name.startswith("T")
        and all(name not in delegates for delegates in module_delegates.values())
    )

    for name in placeholder_names:
        placeholder_kind = choose_placeholder_kind(name)
        size = size_map.get(name, 1)
        if placeholder_kind == "enum":
            underlying = "uint8" if size <= 1 else "int32"
            lines.extend(
                [
                    f"enum class {name} : {underlying} {{",
                    "    Dummy = 0,",
                    "}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    f"{placeholder_kind} {name} {format_size(size)} {{",
                    f"    byte Opaque[{max(size, 1)}] @0x0",
                    "}",
                    "",
                ]
            )

    for module in modules:
        lines.append(f"namespace {module} {{")
        lines.append("")
        for delegate_name in sorted(module_delegates.get(module, set())):
            size = size_map.get(delegate_name, 16)
            lines.extend(
                [
                    f"struct {delegate_name} {format_size(size)} {{",
                    f"    byte Opaque[{max(size, 1)}] @0x0",
                    "}",
                    "",
                ]
            )
            emitted_type_names.add(full_decl_name(module, delegate_name))
        for decl in sort_module_decls(module, module_buckets[module], type_name_to_module):
            if decl.kind == "enum":
                underlying = decl.underlying or "uint8"
                lines.append(f"enum class {decl.name} : {underlying} {{")
                next_value = 0
                for name, explicit in decl.enum_values:
                    if explicit is not None:
                        next_value = int(explicit, 0)
                    lines.append(f"    {name} = {next_value},")
                    next_value += 1
                lines.append("}")
                lines.append("")
                emitted_type_names.add(full_decl_name(module, decl.name))
                continue

            size = size_map.get(decl.name)
            size_suffix = f" {format_size(size)}" if size else ""
            parent = decl.primary_parent()
            if parent and "." not in parent and parent in type_name_to_module and type_name_to_module[parent] != module:
                parent = f"{type_name_to_module[parent]}.{parent}"
            parent_suffix = f" : {parent}" if parent else ""
            lines.append(f"{decl.kind} {decl.name}{parent_suffix}{size_suffix} {{")
            for idx, field_decl in enumerate(decl.fields):
                if field_decl.offset is None:
                    continue
                unresolved = unresolved_field_type_names(
                    field_decl,
                    module,
                    decl.name,
                    type_name_to_module,
                    emitted_type_names,
                )
                needs_raw_storage = has_nested_template_args(field_decl.type_ref)
                if unresolved or needs_raw_storage:
                    storage_size = field_storage_size(decl, idx, size_map)
                    if storage_size is None or storage_size < 1:
                        storage_size = max(
                            resolve_type_size(field_decl.type_ref, size_map) or 1,
                            1,
                        )
                    if unresolved:
                        lines.append(
                            f"    // unresolved user-defined type(s): {', '.join(unresolved)}"
                        )
                    if needs_raw_storage:
                        lines.append(
                            "    // original type uses nested template args unsupported by sdkgenny_parser"
                        )
                    original_arrays = "".join(f"[{dim}]" for dim in field_decl.array_dims)
                    lines.append(
                        f"    // original: {field_decl.format_type()} {field_decl.name}{original_arrays}"
                    )
                    byte_suffix = (
                        f"[{storage_size}]"
                        if storage_size > 1
                        else ""
                    )
                    lines.append(
                        f"    byte {field_decl.name}{byte_suffix} @{format_size(field_decl.offset)}"
                    )
                    continue

                arrays = "".join(f"[{dim}]" for dim in field_decl.array_dims)
                lines.append(
                    f"    {field_decl.format_type()} {field_decl.name}{arrays} @{format_size(field_decl.offset)}"
                )
            lines.append("}")
            lines.append("")
            emitted_type_names.add(full_decl_name(module, decl.name))
        lines.append("}")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert RoboQuest UE4SS dumps into a ReGenny .genny file.")
    parser.add_argument("--uht-root", type=Path, required=True)
    parser.add_argument("--object-dump", type=Path, required=True)
    parser.add_argument("--modules", nargs="+", default=["RoboQuest", "RyseUpTool"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    decls = parse_uht_modules(args.uht_root, args.modules)
    field_offsets, _ = parse_object_dump(args.object_dump, set(args.modules))
    spans, parent_candidates = compute_span_candidates(decls, field_offsets)
    referenced_types = gather_referenced_types(decls.values())
    size_map = resolve_decl_sizes(decls, spans, parent_candidates, referenced_types)
    emit_genny(decls, args.modules, size_map, referenced_types, args.output)

    total_fields = sum(len(decl.fields) for decl in decls.values())
    print(f"Wrote {args.output}")
    print(f"Types: {len(decls)}")
    print(f"Fields: {total_fields}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
