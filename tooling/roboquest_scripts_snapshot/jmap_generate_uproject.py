#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


COMPILE_SHIM_HEADERS: dict[tuple[str, str], str] = {
    ("AIModule", "BTNode.h"): """#include "BehaviorTree/BTNode.h"
""",
    ("AIModule", "BTTask_BlueprintBase.h"): """#include "BehaviorTree/Tasks/BTTask_BlueprintBase.h"
""",
    ("AIModule", "BTTaskNode.h"): """#include "BehaviorTree/BTTaskNode.h"
""",
    ("AIModule", "IntervalCountdown.h"): """#include "AITypes.h"
""",
    ("AIModule", "NavLinkProxy.h"): """#include "Navigation/NavLinkProxy.h"
""",
    ("CoreUObject", "DateTime.h"): """#include "Misc/DateTime.h"
""",
    ("CoreUObject", "Guid.h"): """#include "Misc/Guid.h"
""",
    ("CoreUObject", "Object.h"): """#include "UObject/Object.h"
""",
    ("CoreUObject", "PrimaryAssetId.h"): """#include "UObject/PrimaryAssetId.h"
""",
    ("CoreUObject", "PrimaryAssetType.h"): """#include "UObject/PrimaryAssetId.h"
""",
    ("Engine", "ActorBeginCursorOverSignatureDelegate.h"): """#include "GameFramework/Actor.h"
""",
    ("Engine", "AssetManager.h"): """#include "Engine/AssetManager.h"
""",
    ("Engine", "BoxComponent.h"): """#include "Components/BoxComponent.h"
""",
    ("Engine", "BlueprintAsyncActionBase.h"): """#include "Kismet/BlueprintAsyncActionBase.h"
""",
    ("Engine", "BlueprintFunctionLibrary.h"): """#include "Kismet/BlueprintFunctionLibrary.h"
""",
    ("Engine", "DataAsset.h"): """#include "Engine/DataAsset.h"
""",
    ("Engine", "DataTableRowHandle.h"): """#include "Engine/DataTable.h"
""",
    ("Engine", "CharacterMovementComponent.h"): """#include "GameFramework/CharacterMovementComponent.h"
""",
    ("Engine", "GameViewportClient.h"): """#include "Engine/GameViewportClient.h"
""",
    ("Engine", "DirectoryPath.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "EAttachLocation.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "ECollisionChannel.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "ECollisionEnabled.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "ENetworkSmoothingMode.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "EComponentMobility.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "EEndPlayReason.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "ENetDormancy.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "EAspectRatioAxisConstraint.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "ETravelType.h"): """#include "Engine/EngineBaseTypes.h"
""",
    ("Engine", "LightingChannels.h"): """#include "Engine/EngineTypes.h"
""",
    ("Engine", "PrimaryDataAsset.h"): """#include "Engine/DataAsset.h"
""",
    ("Engine", "SaveGame.h"): """#include "GameFramework/SaveGame.h"
""",
    ("Engine", "SkeletalMeshActor.h"): """#include "Animation/SkeletalMeshActor.h"
""",
    ("Engine", "LocalPlayer.h"): """#include "Engine/LocalPlayer.h"
""",
    ("Engine", "ParticleSystemComponent.h"): """#include "Particles/ParticleSystemComponent.h"
""",
    ("Engine", "TableRowBase.h"): """#include "Engine/DataTable.h"
""",
    ("Engine", "UniqueNetIdRepl.h"): """#include "GameFramework/OnlineReplStructs.h"
""",
    ("JsonUtilities", "JsonObjectWrapper.h"): """struct FJsonObjectWrapper {
    FString JsonString;
};""",
    ("MovieScene", "MovieSceneByteChannel.h"): """struct FMovieSceneByteChannel {
    uint8 Opaque[0x20];
};""",
    ("MovieScene", "MovieSceneEvalTemplate.h"): """#include "Evaluation/MovieSceneEvalTemplate.h"
""",
    ("MovieScene", "MovieSceneTrackTemplateProducer.h"): """#include "Compilation/IMovieSceneTrackTemplateProducer.h"
""",
    ("MovieSceneTracks", "MovieSceneParameterSectionTemplate.h"): """struct FMovieSceneParameterSectionTemplate {
    uint8 Opaque[0x20];
};""",
    ("OnlineSubsystemUtils", "BlueprintSessionResult.h"): """#include "FindSessionsCallbackProxy.h"
""",
    ("OnlineSubsystemUtils", "BlueprintFindSessionsResultDelegateDelegate.h"): """#include "FindSessionsCallbackProxy.h"
""",
    ("OnlineSubsystemUtils", "EmptyOnlineDelegateDelegate.h"): """#include "Net/OnlineBlueprintCallProxyBase.h"
""",
    ("OnlineSubsystemUtils", "OnlineBlueprintCallProxyBase.h"): """#include "Net/OnlineBlueprintCallProxyBase.h"
""",
    ("PhysicsCore", "EPhysicalSurface.h"): """#include "Chaos/ChaosEngineInterface.h"
""",
    ("InputCore", "Key.h"): """#include "InputCoreTypes.h"
""",
    ("SlateCore", "FontOutlineSettings.h"): """#include "Fonts/SlateFontInfo.h"
""",
    ("SlateCore", "SlateColor.h"): """#include "Styling/SlateColor.h"
""",
    ("SlateCore", "ESlateColorStylingMode.h"): """#include "Styling/SlateColor.h"
""",
    ("UMG", "CustomWidgetNavigationDelegateDelegate.h"): """#include "Blueprint/WidgetNavigation.h"
""",
    ("UMG", "ContentWidget.h"): """#include "Components/ContentWidget.h"
""",
    ("UMG", "EditableText.h"): """#include "Components/EditableText.h"
""",
    ("UMG", "ESlateVisibility.h"): """#include "Components/SlateWrapperTypes.h"
""",
    ("UMG", "EVirtualKeyboardType.h"): """#include "Components/SlateWrapperTypes.h"
""",
    ("UMG", "WidgetTransform.h"): """#include "Slate/WidgetTransform.h"
""",
    ("UMG", "UserWidget.h"): """#include "Blueprint/UserWidget.h"
""",
}

REFERENCE_INCLUDE_EXCLUDE_MODULES = {
    "AIModule",
    "CoreUObject",
    "Engine",
    "GameplayTasks",
    "InputCore",
    "MediaAssets",
    "OnlineSubsystemUtils",
    "SlateCore",
    "UMG",
}


def short_owner_module(path: str) -> str | None:
    match = re.match(r"^/Script/([^/.]+)", path)
    return match.group(1) if match else None


def iter_script_modules(value: Any):
    if isinstance(value, str):
        module = short_owner_module(value)
        if module:
            yield module
    elif isinstance(value, dict):
        for nested in value.values():
            yield from iter_script_modules(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from iter_script_modules(nested)


def load_uht_helpers(script_path: Path):
    spec = importlib.util.spec_from_file_location("jmap_to_uht", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load helper module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_engine_plugin_modules(engine_root: Path) -> dict[str, str]:
    if (engine_root / "Engine").exists():
        install_root = engine_root
    elif engine_root.name == "Engine":
        install_root = engine_root.parent
    else:
        install_root = engine_root

    plugins_root = install_root / "Engine" / "Plugins"
    module_owners: dict[str, str] = {}
    if not plugins_root.exists():
        return module_owners

    for plugin_file in plugins_root.rglob("*.uplugin"):
        try:
            raw = plugin_file.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except Exception:
            try:
                relaxed = re.sub(r",(\s*[}\]])", r"\1", raw)
                payload = json.loads(relaxed)
            except Exception:
                continue

        for module in payload.get("Modules", []):
            name = module.get("Name")
            if name and name not in module_owners:
                module_owners[name] = str(plugin_file)

    return module_owners


def collect_engine_source_modules(engine_root: Path) -> set[str]:
    if (engine_root / "Engine").exists():
        install_root = engine_root
    elif engine_root.name == "Engine":
        install_root = engine_root.parent
    else:
        install_root = engine_root

    module_names: set[str] = set()
    scan_roots = [
        install_root / "Engine" / "Source",
        install_root / "Engine" / "Plugins",
    ]
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for build_file in scan_root.rglob("*.cs"):
            name = build_file.name
            if name.lower().endswith(".build.cs"):
                module_names.add(name[: -len(".build.cs")])
    return module_names


def parse_modules_arg(raw: str, objects: dict[str, dict], engine_modules: set[str]) -> list[str]:
    if raw == "ALL":
        modules = sorted(
            {
                module
                for path in objects
                if (module := short_owner_module(path)) and module not in engine_modules
            }
        )
        return modules
    return [module.strip() for module in raw.split(",") if module.strip()]


def collect_module_paths(objects: dict[str, dict], module: str) -> list[str]:
    prefix = f"/Script/{module}."
    return [path for path in objects if path.startswith(prefix)]


def collect_engine_cpp_names(objects: dict[str, dict], engine_modules: set[str], uht_helpers) -> set[str]:
    names: set[str] = set()
    for path, obj in objects.items():
        if obj.get("type") != "Class":
            continue
        module = short_owner_module(path)
        if module and module in engine_modules:
            names.add(uht_helpers.class_cpp_name(path, obj, objects))
    return names


def infer_dependencies(
    module: str,
    module_paths: list[str],
    objects: dict[str, dict],
    generated_modules: set[str],
    engine_modules: set[str],
    external_modules: set[str] | None = None,
) -> list[str]:
    deps = {"Core", "CoreUObject", "Engine"}
    for path in module_paths:
        for dep in iter_script_modules(objects[path]):
            if dep == module:
                continue
            if dep in generated_modules or dep in engine_modules or (external_modules and dep in external_modules):
                deps.add(dep)
    if "AIModule" in deps:
        deps.add("GameplayTasks")
    if "OnlineSubsystemUtils" in deps:
        deps.add("OnlineSubsystem")
    if module in {"RedpointEOSAuthDiscord", "RedpointEOSAuthSteam"}:
        deps.add("OnlineSubsystemRedpointEOS")
    if module == "OnlineSubsystemGOG":
        deps.add("PacketHandler")
        deps.add("NetCore")
    if module in deps:
        deps.remove(module)
    return sorted(deps)


def collect_enabled_plugins(
    modules: list[str],
    objects: dict[str, dict],
    plugin_module_owners: dict[str, str],
    skipped_engine_plugin_modules: list[dict[str, str]],
) -> list[str]:
    plugin_names = {
        Path(skipped["owner"]).stem
        for skipped in skipped_engine_plugin_modules
    }
    for module in modules:
        for path in collect_module_paths(objects, module):
            for dep in iter_script_modules(objects[path]):
                owner = plugin_module_owners.get(dep)
                if owner:
                    plugin_names.add(Path(owner).stem)
    return sorted(plugin_names)


def ensure_directory_junction(link_path: Path, target_path: Path):
    if link_path.exists():
        return
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        copy_tree_if_present(target_path, link_path)


def materialize_public_reference_headers(dest_root: Path, source_root: Path) -> set[str]:
    modules: set[str] = set()
    dest_root.mkdir(parents=True, exist_ok=True)
    for entry in source_root.iterdir():
        if not entry.is_dir():
            continue
        public_dir = entry / "Public"
        if not public_dir.exists():
            continue
        modules.add(entry.name)
        ensure_directory_junction(dest_root / entry.name / "Public", public_dir)
    return modules


def materialize_compile_shims(dest_root: Path) -> set[str]:
    modules: set[str] = set()
    for (module, header_name), stub_body in COMPILE_SHIM_HEADERS.items():
        modules.add(module)
        header_path = dest_root / module / "Public" / header_name
        header_path.parent.mkdir(parents=True, exist_ok=True)
        text = "#pragma once\n" + f"{stub_body}\n"
        header_path.write_text(text, encoding="utf-8")
    return modules


def write_build_cs(
    path: Path,
    module: str,
    dependencies: list[str],
    reference_include_modules: list[str] | None = None,
    compile_shim_modules: list[str] | None = None,
):
    deps = ",\n            ".join(f'"{dep}"' for dep in dependencies)
    include_block = ""
    if compile_shim_modules:
        shim_entries = ",\n            ".join(
            f'Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "_compile_shims", "{dep}", "Public"))'
            for dep in sorted(compile_shim_modules)
        )
        include_block += (
            "\n"
            "        PublicIncludePaths.AddRange(new string[] {\n"
            f"            {shim_entries}\n"
            "        });\n"
        )
    if reference_include_modules:
        include_entries = ",\n            ".join(
            f'Path.GetFullPath(Path.Combine(ModuleDirectory, "..", "..", "_engine_module_reference", "{dep}", "Public"))'
            for dep in sorted(reference_include_modules)
            if dep not in REFERENCE_INCLUDE_EXCLUDE_MODULES
        )
        if include_entries:
            include_block += (
                "\n"
                "        PublicIncludePaths.AddRange(new string[] {\n"
                f"            {include_entries}\n"
                "        });\n"
            )
    text = (
        "using UnrealBuildTool;\n"
        "using System.IO;\n\n"
        f"public class {module} : ModuleRules {{\n"
        f"    public {module}(ReadOnlyTargetRules Target) : base(Target) {{\n"
        "        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;\n"
        "        bLegacyPublicIncludePaths = false;\n"
        "        ShadowVariableWarningLevel = WarningLevel.Warning;\n\n"
        "        PublicDependencyModuleNames.AddRange(new string[] {\n"
        f"            {deps}\n"
        "        });\n"
        f"{include_block}"
        "    }\n"
        "}\n"
    )
    path.write_text(text, encoding="utf-8")


def write_target_cs(path: Path, project_name: str, target_type: str, modules: list[str]):
    class_name = f"{project_name}{'' if target_type == 'Game' else target_type}Target"
    module_entries = ", ".join(f'"{module}"' for module in modules)
    text = (
        "using UnrealBuildTool;\n"
        "using System.Collections.Generic;\n\n"
        f"public class {class_name} : TargetRules\n"
        "{\n"
        f"\tpublic {class_name}(TargetInfo Target) : base(Target)\n"
        "\t{\n"
        f"\t\tType = TargetType.{target_type};\n"
        "\t\tDefaultBuildSettings = BuildSettingsVersion.V2;\n"
        f"\t\tExtraModuleNames.AddRange(new string[] {{ {module_entries} }});\n"
        "\t}\n"
        "}\n"
    )
    path.write_text(text, encoding="utf-8")


def write_module_header(path: Path):
    text = (
        "#pragma once\n\n"
        '#include "Modules/ModuleManager.h"\n'
    )
    path.write_text(text, encoding="utf-8")


def write_module_cpp(path: Path, module: str, root_module: str):
    if module == root_module:
        text = (
            f'#include "{module}.h"\n\n'
            f'IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, {module}, "{module}");\n'
        )
    else:
        text = (
            f'#include "{module}.h"\n\n'
            f"IMPLEMENT_MODULE(FDefaultModuleImpl, {module});\n"
        )
    path.write_text(text, encoding="utf-8")


def write_uproject(
    path: Path,
    project_name: str,
    modules: list[str],
    engine_association: str,
    plugins: list[str],
):
    payload = {
        "FileVersion": 3,
        "EngineAssociation": engine_association,
        "Category": "",
        "Description": f"Generated mirror project for {project_name} from trumank/jmap.",
        "Modules": [
            {
                "Name": module,
                "Type": "Runtime",
                "LoadingPhase": "Default",
                "AdditionalDependencies": ["Engine", "CoreUObject"],
            }
            for module in modules
        ],
        "Plugins": [{"Name": plugin, "Enabled": True} for plugin in plugins],
    }
    path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")


def copy_tree_if_present(source: Path, dest: Path):
    if not source.exists():
        return
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest)


def normalize_uht_dump_header_text(uht_helpers, text: str) -> str:
    extract_includes = getattr(uht_helpers, "_extract_uht_dump_includes", None)
    normalize_header = getattr(uht_helpers, "normalize_include_header", None)
    if extract_includes is None and normalize_header is None:
        return text

    desired_includes = sorted(extract_includes(text)) if callable(extract_includes) else []

    lines = text.splitlines()
    rewritten_lines: list[str] = []
    existing_includes: set[str] = set()
    for line in lines:
        match = re.match(r'^\s*#include\s+"([^"]+)"', line)
        if match:
            header = match.group(1)
            if header.endswith(".generated.h"):
                existing_includes.add(header)
                rewritten_lines.append(line)
                continue
            if callable(normalize_header):
                normalized = normalize_header(header)
                if normalized is None:
                    continue
                if normalized != header:
                    line = f'#include "{normalized}"'
                    header = normalized
            existing_includes.add(header)
        rewritten_lines.append(line)

    missing_includes = [header for header in desired_includes if header not in existing_includes]
    if not missing_includes:
        suffix = "\n" if text.endswith("\n") else ""
        return "\n".join(rewritten_lines) + suffix

    insert_at = None
    for idx, line in enumerate(rewritten_lines):
        stripped = line.strip()
        if stripped.startswith('#include "') and stripped.endswith('.generated.h"'):
            insert_at = idx
            break
    if insert_at is None:
        insert_at = next((idx + 1 for idx, line in enumerate(rewritten_lines) if line.strip() == "#pragma once"), 0)

    rewritten = list(rewritten_lines[:insert_at])
    rewritten.extend(f'#include "{header}"' for header in missing_includes)
    rewritten.extend(rewritten_lines[insert_at:])
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(rewritten) + suffix


def copy_uht_dump_delegate_headers(uht_dump_root: Path | None, module: str, public_dir: Path, uht_helpers):
    if not uht_dump_root:
        return
    module_public = uht_dump_root / module / "Public"
    if not module_public.exists():
        return

    for header in module_public.glob("*Delegate*.h"):
        try:
            text = header.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = header.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "UDELEGATE(" not in text and "DECLARE_DYNAMIC_" not in text:
            continue
        dest = public_dir / header.name
        if dest.exists():
            continue
        dest.write_text(normalize_uht_dump_header_text(uht_helpers, text), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jmap", help="Input .jmap JSON path")
    parser.add_argument("--project-name", default="RoboQuest", help="Unreal project name")
    parser.add_argument("--root-module", default="RoboQuest", help="Primary game module")
    parser.add_argument("--modules", default="ALL", help="Comma-separated modules to emit or ALL")
    parser.add_argument("--out-dir", required=True, help="Output project directory")
    parser.add_argument("--engine-association", default="4.26", help="uproject EngineAssociation value")
    parser.add_argument("--engine-root", help="Unreal install root used to exclude engine/plugin-owned modules")
    parser.add_argument("--engine-reference-root", help="Optional flat engine module reference tree used for missing 4.26-style public headers")
    parser.add_argument("--copy-config-from", help="Copy Config/ from an existing project")
    parser.add_argument("--uht-dump-root", help="Optional UE4SS UHTHeaderDump root used for name/header overrides")
    args = parser.parse_args()

    tool_dir = Path(__file__).resolve().parent
    uht_helpers = load_uht_helpers(tool_dir / "jmap_to_uht.py")
    uht_helpers.configure_uht_dump(args.uht_dump_root)
    uht_dump_root = Path(args.uht_dump_root).resolve() if args.uht_dump_root else None

    jmap_path = Path(args.jmap).resolve()
    out_dir = Path(args.out_dir).resolve()
    source_root = out_dir / "Source"
    config_root = out_dir / "Config"

    with jmap_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    objects = data["objects"]
    engine_modules = set(uht_helpers.ENGINE_MODULES)
    if args.engine_root:
        engine_modules.update(collect_engine_source_modules(Path(args.engine_root).resolve()))
    engine_cpp_names = collect_engine_cpp_names(objects, engine_modules, uht_helpers)
    modules = parse_modules_arg(args.modules, objects, engine_modules)
    skipped_engine_plugin_modules: list[dict[str, str]] = []
    plugin_module_owners: dict[str, str] = {}
    if args.engine_root:
        plugin_module_owners = collect_engine_plugin_modules(Path(args.engine_root).resolve())
        filtered_modules: list[str] = []
        for module in modules:
            if module == args.root_module:
                filtered_modules.append(module)
                continue
            owner = plugin_module_owners.get(module)
            if owner:
                skipped_engine_plugin_modules.append({"name": module, "owner": owner})
                continue
            filtered_modules.append(module)
        modules = filtered_modules
    generated_modules = set(modules)
    if args.root_module not in generated_modules:
        raise RuntimeError(f"Root module {args.root_module} was filtered out; choose a different root module.")

    out_dir.mkdir(parents=True, exist_ok=True)
    source_root.mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)

    engine_reference_modules: set[str] = set()
    compile_shim_modules = materialize_compile_shims(out_dir / "_compile_shims")
    if args.engine_reference_root:
        engine_reference_root = Path(args.engine_reference_root).resolve()
        if engine_reference_root.exists():
            engine_reference_modules = materialize_public_reference_headers(
                out_dir / "_engine_module_reference",
                engine_reference_root,
            )

    if args.copy_config_from:
        copy_tree_if_present(Path(args.copy_config_from).resolve(), config_root)

    enabled_plugins = collect_enabled_plugins(
        modules,
        objects,
        plugin_module_owners,
        skipped_engine_plugin_modules,
    )
    write_uproject(
        out_dir / f"{args.project_name}.uproject",
        args.project_name,
        modules,
        args.engine_association,
        enabled_plugins,
    )
    write_target_cs(source_root / f"{args.project_name}.Target.cs", args.project_name, "Game", modules)
    write_target_cs(source_root / f"{args.project_name}Editor.Target.cs", args.project_name, "Editor", modules)

    for skipped in skipped_engine_plugin_modules:
        print(f"[skip] {skipped['name']}: provided by engine plugin {skipped['owner']}")

    skipped_collision_types: list[dict[str, str]] = []
    summary: list[tuple[str, int, list[str]]] = []
    for module in modules:
        module_paths = collect_module_paths(objects, module)
        public_dir = source_root / module / "Public"
        private_dir = source_root / module / "Private"
        public_dir.mkdir(parents=True, exist_ok=True)
        private_dir.mkdir(parents=True, exist_ok=True)
        copy_uht_dump_delegate_headers(uht_dump_root, module, public_dir, uht_helpers)
        write_module_header(public_dir / f"{module}.h")
        write_module_cpp(private_dir / f"{module}.cpp", module, args.root_module)

        emitted = 0
        for path in module_paths:
            obj = objects[path]
            short = uht_helpers.obj_short_name(path)
            if short.startswith("Default__"):
                continue

            obj_type = obj.get("type")
            if obj_type == "Enum":
                uht_helpers.emit_enum(path, obj, public_dir, source=str(jmap_path))
                emitted += 1
            elif obj_type == "ScriptStruct":
                uht_helpers.emit_struct(path, obj, objects, public_dir, source=str(jmap_path))
                emitted += 1
            elif obj_type == "Class":
                cpp_name = uht_helpers.class_cpp_name(path, obj, objects)
                if cpp_name in uht_helpers.ENGINE_COLLISION_NAMES or cpp_name in engine_cpp_names:
                    skipped_collision_types.append(
                        {"module": module, "object_path": path, "cpp_name": cpp_name}
                    )
                    print(f"[skip] {path}: collides with engine class name {cpp_name}")
                    continue
                uht_helpers.emit_class(path, obj, objects, public_dir, private_dir, source=str(jmap_path))
                emitted += 1

        dependencies = infer_dependencies(
            module,
            module_paths,
            objects,
            generated_modules,
            engine_modules,
            set(plugin_module_owners),
        )
        write_build_cs(
            source_root / module / f"{module}.Build.cs",
            module,
            dependencies,
            [dep for dep in dependencies if dep in engine_reference_modules],
            [dep for dep in dependencies if dep in compile_shim_modules],
        )
        summary.append((module, emitted, dependencies))
        print(f"[emit] {module}: {emitted} types, {len(dependencies)} deps")

    summary_path = out_dir / "jmap_generation_summary.json"
    summary_payload = {
        "jmap": str(jmap_path),
        "project_name": args.project_name,
        "root_module": args.root_module,
        "skipped_engine_plugin_modules": skipped_engine_plugin_modules,
        "skipped_collision_types": skipped_collision_types,
        "modules": [
            {"name": module, "emitted_types": emitted, "dependencies": deps}
            for module, emitted, deps in summary
        ],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8")
    print(f"[done] wrote project to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
