#!/usr/bin/env python3
"""
jmap_to_uht.py — Transform a trumank/jmap JSON dump into UHT-compatible
UCLASS/USTRUCT/UENUM C++ headers plus stub .cpp files.

Design notes
------------
Goal: produce a UE 4.26 project source tree that Unreal Header Tool (UHT)
accepts and Unreal Build Tool (UBT) compiles, starting from a reflection
dump of a shipping binary. We cannot recover native function bodies — every
generated function returns a default-constructed value or does nothing.

Scope for this run:
  - Target one /Script/<Module> at a time (default: RoboQuest)
  - Emit one .h/.cpp pair per UClass / UScriptStruct / UEnum
  - Use forward declarations for UObject* / UClass* references (no include
    cascade across every class).
  - Emit minimal UCLASS()/USTRUCT()/UENUM() specifiers — empty parens are
    legal and let UHT generate metadata without us having to perfectly
    reverse-engineer flag → specifier mappings.
  - Emit UPROPERTY() with VisibleAnywhere + BlueprintReadOnly as safe
    defaults; flag-accurate mapping can be layered on later.
  - Emit UFUNCTION() with empty specifiers; signatures reconstructed from
    jmap function properties.

Known limitations (documented so the user can patch):
  - Bitfield bools: jmap reports multiple bools at the same offset with
    byte_mask info; we emit them as uint8_t NAME : 1 inside a UCLASS
    (UHT does accept this but with restrictions). If more than 8 share
    an offset, we fall back to plain bool.
  - Function signatures reconstruct parameter types from property records
    attached to the function (jmap emits them as children).
  - Delegate signatures collapse to FDelegate / FMulticastInlineDelegate
    aliases; user must wire up the real DECLARE_DYNAMIC_DELEGATE macros.
  - Default__<X> CDO objects in the module are skipped (not real types).
  - Classes whose short name collides with an engine class (e.g.
    AAIController, UKismetMathLibrary) are still emitted but annotated
    with a warning comment at the top of the file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Engine-owned short names we never want to silently collide with. If the
# game module has a class with the same short name, we emit a comment so the
# user sees the collision instead of a cryptic UHT error.
ENGINE_COLLISION_NAMES = {
    "AAIController", "AController", "APlayerController", "APawn", "ACharacter",
    "AActor", "AGameMode", "AGameState", "APlayerState", "AHUD",
    "UActorComponent", "USceneComponent", "UPrimitiveComponent",
    "UKismetMathLibrary", "UKismetSystemLibrary", "UGameplayStatics",
    "UBlueprintFunctionLibrary", "UObject",
}

# Short engine names we treat as "already defined by the engine" — when the
# game's class inherits from one, we forward-declare via `class Name;` and
# don't try to emit a header for it.
ENGINE_MODULES = {
    "AIModule", "AnimGraphRuntime", "AnimationCore", "AssetRegistry",
    "AudioMixer", "CoreUObject", "DeveloperSettings", "Engine",
    "EngineSettings", "Foliage", "GameplayTags", "GameplayTasks",
    "InputCore", "JsonUtilities", "Landscape", "LevelSequence",
    "MovieScene", "MovieSceneTracks", "NavigationSystem", "NetCore",
    "Niagara", "NiagaraCore", "OnlineSubsystem", "OnlineSubsystemUtils",
    "PacketHandler", "Paper2D", "PhysicsCore", "PropertyPath", "Renderer",
    "Slate", "SlateCore", "UMG", "UnrealEd", "MediaAssets",
}

# Engine-owned types that are commonly used as base classes by game modules,
# but are not part of the fixed header prologue below. When one of these
# appears as a superclass we need to include the real header so UHT can
# resolve the inheritance chain.
ENGINE_TYPE_HEADERS = {
    "Actor": "GameFramework/Actor.h",
    "AIController": "AIController.h",
    "AssetManager": "Engine/AssetManager.h",
    "BTNode": "BehaviorTree/BTNode.h",
    "BTTask_BlueprintBase": "BehaviorTree/Tasks/BTTask_BlueprintBase.h",
    "BTTaskNode": "BehaviorTree/BTTaskNode.h",
    "EnvQueryTest": "EnvironmentQuery/EnvQueryTest.h",
    "OnlineBlueprintCallProxyBase": "Net/OnlineBlueprintCallProxyBase.h",
    "BlueprintFunctionLibrary": "Kismet/BlueprintFunctionLibrary.h",
    "BlueprintAsyncActionBase": "Kismet/BlueprintAsyncActionBase.h",
    "AnimNotify": "Animation/AnimNotifies/AnimNotify.h",
    "BoxComponent": "Components/BoxComponent.h",
    "CharacterMovementComponent": "GameFramework/CharacterMovementComponent.h",
    "PrimaryDataAsset": "Engine/DataAsset.h",
    "UserWidget": "Blueprint/UserWidget.h",
    "StaticMeshActor": "Engine/StaticMeshActor.h",
    "AnimInstance": "Animation/AnimInstance.h",
    "LocalPlayer": "Engine/LocalPlayer.h",
    "MediaSource": "MediaSource.h",
    "ParticleSystemComponent": "Particles/ParticleSystemComponent.h",
    "WidgetComponent": "Components/WidgetComponent.h",
    "DecalComponent": "Components/DecalComponent.h",
    "ContentWidget": "Components/ContentWidget.h",
    "EditableText": "Components/EditableText.h",
    "ENetworkSmoothingMode": "Engine/EngineTypes.h",
    "GameInstance": "Engine/GameInstance.h",
    "GameViewportClient": "Engine/GameViewportClient.h",
    "MovieSceneNameableTrack": "MovieSceneNameableTrack.h",
    "MovieSceneSection": "MovieSceneSection.h",
    "NetConnection": "Engine/NetConnection.h",
    "TriggerBox": "Engine/TriggerBox.h",
    "DecalActor": "Engine/DecalActor.h",
    "Object": "UObject/Object.h",
    "NavLinkProxy": "Navigation/NavLinkProxy.h",
    "ReverbEffect": "Sound/ReverbEffect.h",
    "SaveGame": "GameFramework/SaveGame.h",
    "SlateColor": "Styling/SlateColor.h",
    "SkeletalMeshActor": "Animation/SkeletalMeshActor.h",
    "NetDriver": "Engine/NetDriver.h",
    "ControlChannel": "Engine/ControlChannel.h",
    "MovieSceneTrackTemplateProducer": "Compilation/IMovieSceneTrackTemplateProducer.h",
}

CANONICAL_INCLUDE_OVERRIDES: dict[str, str | None] = {
    Path(header).name: header
    for header in ENGINE_TYPE_HEADERS.values()
}
CANONICAL_INCLUDE_OVERRIDES.update({
    "EMovieSceneCompletionMode.h": "Evaluation/MovieSceneCompletionMode.h",
    "ENavLinkDirection.h": "AI/Navigation/NavLinkDefinition.h",
    "EAttachLocation.h": "Engine/EngineTypes.h",
    "ActorBeginCursorOverSignatureDelegate.h": "GameFramework/Actor.h",
    "AssetManager.h": "Engine/AssetManager.h",
    "BoxComponent.h": "Components/BoxComponent.h",
    "BlackboardKeySelector.h": "BehaviorTree/BehaviorTreeTypes.h",
    "BTNode.h": "BehaviorTree/BTNode.h",
    "BTTask_BlueprintBase.h": "BehaviorTree/Tasks/BTTask_BlueprintBase.h",
    "BTTaskNode.h": "BehaviorTree/BTTaskNode.h",
    "BlueprintFindSessionsResultDelegateDelegate.h": "FindSessionsCallbackProxy.h",
    "BlueprintSessionResult.h": "FindSessionsCallbackProxy.h",
    "CustomWidgetNavigationDelegateDelegate.h": "Blueprint/WidgetNavigation.h",
    "DataAsset.h": "Engine/DataAsset.h",
    "DataTableRowHandle.h": "Engine/DataTable.h",
    "DateTime.h": None,
    "DirectoryPath.h": "Engine/EngineTypes.h",
    "CharacterMovementComponent.h": "GameFramework/CharacterMovementComponent.h",
    "EditableText.h": "Components/EditableText.h",
    "ECollisionChannel.h": "Engine/EngineTypes.h",
    "ECollisionEnabled.h": "Engine/EngineTypes.h",
    "ESpawnActorCollisionHandlingMethod.h": "Engine/EngineTypes.h",
    "ENetworkSmoothingMode.h": "Engine/EngineTypes.h",
    "EAspectRatioAxisConstraint.h": "Engine/EngineTypes.h",
    "EComponentMobility.h": "Engine/EngineTypes.h",
    "EEndPlayReason.h": "Engine/EngineTypes.h",
    "ENetDormancy.h": "Engine/EngineTypes.h",
    "EPhysicalSurface.h": "Chaos/ChaosEngineInterface.h",
    "ESlateVisibility.h": "Components/SlateWrapperTypes.h",
    "ETravelType.h": "Engine/EngineBaseTypes.h",
    "EVirtualKeyboardType.h": "Components/SlateWrapperTypes.h",
    "EmptyOnlineDelegateDelegate.h": "Net/OnlineBlueprintCallProxyBase.h",
    "ESlateColorStylingMode.h": "Styling/SlateColor.h",
    "Exporter.h": "Exporters/Exporter.h",
    "FontOutlineSettings.h": "Fonts/SlateFontInfo.h",
    "GameInstanceSubsystem.h": "Subsystems/GameInstanceSubsystem.h",
    "GameViewportClient.h": "Engine/GameViewportClient.h",
    "Guid.h": None,
    "Interface.h": "UObject/Interface.h",
    "IntervalCountdown.h": "AITypes.h",
    "Key.h": "InputCoreTypes.h",
    "LightingChannels.h": "Engine/EngineTypes.h",
    "LocalPlayer.h": "Engine/LocalPlayer.h",
    "MovieSceneEvalTemplate.h": "Evaluation/MovieSceneEvalTemplate.h",
    "ParticleSystemComponent.h": "Particles/ParticleSystemComponent.h",
    "PrimaryAssetType.h": "UObject/PrimaryAssetId.h",
    "PrimaryAssetId.h": "UObject/PrimaryAssetId.h",
    "PrimaryDataAsset.h": "Engine/DataAsset.h",
    "SaveGame.h": "GameFramework/SaveGame.h",
    "SkeletalMeshActor.h": "Animation/SkeletalMeshActor.h",
    "SoftObjectPath.h": "UObject/SoftObjectPath.h",
    "SlateColor.h": "Styling/SlateColor.h",
    "TableRowBase.h": "Engine/DataTable.h",
    "UniqueNetIdRepl.h": "GameFramework/OnlineReplStructs.h",
    "ContentWidget.h": "Components/ContentWidget.h",
    "WidgetTransform.h": "Slate/WidgetTransform.h",
})

PROLOGUE_INCLUDE_HEADERS = {
    "UObject/NoExportTypes.h",
    "UObject/ObjectMacros.h",
    "UObject/ScriptDelegates.h",
    "UObject/ScriptInterface.h",
    "Engine/DataTable.h",
    "Engine/EngineTypes.h",
    "GameFramework/Actor.h",
    "GameFramework/Pawn.h",
    "GameFramework/Character.h",
    "GameFramework/Controller.h",
    "GameFramework/PlayerController.h",
    "GameFramework/GameModeBase.h",
    "GameFramework/GameStateBase.h",
    "GameFramework/PlayerState.h",
    "GameFramework/HUD.h",
    "Components/ActorComponent.h",
    "Components/SceneComponent.h",
    "Components/PrimitiveComponent.h",
    "Components/SkeletalMeshComponent.h",
    "Components/StaticMeshComponent.h",
    "TimerManager.h",
}

PROLOGUE_BASENAME_OVERRIDES = {
    Path(header).name: header
    for header in PROLOGUE_INCLUDE_HEADERS
}

SPECIAL_CLASS_DECLARATIONS: dict[tuple[str, str], list[str]] = {
    ("FMODStudio", "UFMODSnapshotReverb"): [
        "    UFMODSnapshotReverb(const FObjectInitializer& ObjectInitializer);",
        "",
        "private:",
        "    virtual bool IsAsset() const override;",
        "",
        "#if WITH_EDITORONLY_DATA",
        "    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;",
        "#endif",
    ],
    ("RyseUpTool", "AASpline_Moving"): [
        "    AASpline_Moving();",
    ],
    ("RyseUpTool", "AJumpingAIController"): [
        "    AJumpingAIController(const FObjectInitializer& ObjectInitializer);",
    ],
}

SPECIAL_CLASS_DEFINITIONS: dict[tuple[str, str], list[str]] = {
    ("FMODStudio", "UFMODSnapshotReverb"): [
        "UFMODSnapshotReverb::UFMODSnapshotReverb(const FObjectInitializer& ObjectInitializer)",
        "    : Super(ObjectInitializer)",
        "{",
        "}",
        "",
        "bool UFMODSnapshotReverb::IsAsset() const",
        "{",
        "    return this != GetClass()->GetDefaultObject();",
        "}",
        "",
        "#if WITH_EDITORONLY_DATA",
        "void UFMODSnapshotReverb::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)",
        "{",
        "}",
        "#endif",
    ],
    ("RyseUpTool", "AASpline_Moving"): [
        "AASpline_Moving::AASpline_Moving()",
        "{",
        "}",
    ],
    ("RyseUpTool", "AJumpingAIController"): [
        "AJumpingAIController::AJumpingAIController(const FObjectInitializer& ObjectInitializer)",
        "    : Super(ObjectInitializer)",
        "{",
        "}",
    ],
}

# Reflected short names that don't map cleanly via the usual UE prefix
# heuristic. Shipping dumps use the UObject path short name (e.g.
# /Script/AIModule.AIController), but the C++ symbol still carries the
# gameplay prefix (AAIController).
CPP_NAME_OVERRIDES = {
    "/Script/AIModule.AIController": "AAIController",
    "/Script/Engine.HUD": "AHUD",
    "/Script/RoboQuest.AAIController": "AAAIController",
    "/Script/RoboQuest.ACharacter": "AACharacter",
    "/Script/RoboQuest.ADecalActor": "AADecalActor",
    "/Script/RoboQuest.AGameMode": "AAGameMode",
    "/Script/RoboQuest.AGameState": "AAGameState",
    "/Script/RoboQuest.APlayerController": "AAPlayerController",
    "/Script/RoboQuest.APlayerState": "AAPlayerState",
}

UHT_DUMP_CPP_NAMES: dict[tuple[str, str, str], str] = {}
UHT_DUMP_HEADER_BY_KEY: dict[tuple[str, str, str], str] = {}
UHT_DUMP_HEADER_BY_SYMBOL: dict[tuple[str, str], str] = {}
UHT_DUMP_FUNCTION_DECLS: dict[tuple[str, str, str], tuple[str, str]] = {}
UHT_DUMP_INCLUDES_BY_KEY: dict[tuple[str, str, str], set[str]] = {}
UHT_DUMP_MEMBER_DECLARES: dict[tuple[str, str, str], list[str]] = {}
UHT_DUMP_MEMBER_DECLARE_FN_NAMES: dict[tuple[str, str, str], set[str]] = {}

_UHT_DUMP_CLASS_RE = re.compile(
    r"^\s*class\s+(?:[A-Za-z_][A-Za-z0-9_]*_API\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*public\b",
    re.MULTILINE,
)
_UHT_DUMP_STRUCT_RE = re.compile(
    r"^\s*struct\s+(?:[A-Za-z_][A-Za-z0-9_]*_API\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?::[^{]+)?\{",
    re.MULTILINE,
)
_UHT_DUMP_ENUM_RE = re.compile(
    r"^\s*enum\s+class\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:",
    re.MULTILINE,
)
_UHT_DUMP_FUNCTION_NAME_RE = re.compile(
    r"^(?:static\s+)?(?:virtual\s+)?(?:[\w:<>~*&]+\s+)+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
)
_DECL_SIGNATURE_RE = re.compile(
    r"^(?P<prefix>(?:(?:static|virtual)\s+)*)"
    r"(?P<ret>.+?)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"\((?P<args>.*)\)"
    r"(?P<suffix>\s+const)?$"
)


# ---------------------------------------------------------------------------
# Helpers

def obj_short_name(path: str) -> str:
    """Return the last segment of a UE object path."""
    return re.split(r"[/.:]", path)[-1]


def short_owner_module(path: str) -> str | None:
    """For /Script/Foo.Bar.Baz return 'Foo', else None."""
    m = re.match(r"^/Script/([^/.]+)", path)
    return m.group(1) if m else None


def module_api_macro(module_name: str | None) -> str:
    if not module_name:
        return ""
    sanitized = re.sub(r"[^A-Za-z0-9]", "", module_name)
    return f"{sanitized.upper()}_API" if sanitized else ""


def sanitize_ident(name: str) -> str:
    """Ensure a bare identifier is valid C++."""
    out = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not out or not (out[0].isalpha() or out[0] == "_"):
        out = "_" + out
    return out


def _has_ue_prefix(name: str, prefix: str) -> bool:
    """Is `name` already prefixed per UE convention (prefix + capital letter)?

    UE C++ prefixes (A, U, I, F, E) are followed by another capital letter to
    avoid ambiguity with real-word names that happen to start with the prefix
    character (e.g. 'Actor' is not 'A' + 'ctor')."""
    return len(name) >= 2 and name[0] == prefix and name[1].isupper()


def normalize_include_header(header: str | None) -> str | None:
    if not header:
        return None
    header = header.replace("\\", "/")
    header = PROLOGUE_BASENAME_OVERRIDES.get(header, header)
    header = CANONICAL_INCLUDE_OVERRIDES.get(header, header)
    if header:
        stem = Path(header).stem
        builtin_candidates = {stem, f"F{stem}", f"E{stem}"}
        if builtin_candidates & BUILTIN_TYPES:
            return None
    if not header or header == "CoreMinimal.h" or header.endswith(".generated.h"):
        return None
    if header in PROLOGUE_INCLUDE_HEADERS:
        return None
    return header


def _extract_uht_dump_decl(header_text: str) -> tuple[str, str] | None:
    if "USTRUCT(" in header_text:
        match = _UHT_DUMP_STRUCT_RE.search(header_text)
        if match:
            return "ScriptStruct", match.group("name")
    if "UENUM(" in header_text:
        match = _UHT_DUMP_ENUM_RE.search(header_text)
        if match:
            return "Enum", match.group("name")
    if "UINTERFACE(" in header_text:
        matches = list(_UHT_DUMP_CLASS_RE.finditer(header_text))
        for match in reversed(matches):
            name = match.group("name")
            if name.startswith("I") and len(name) > 1 and name[1].isupper():
                return "Class", name
        if matches:
            return "Class", matches[-1].group("name")
    if "UCLASS(" in header_text:
        match = _UHT_DUMP_CLASS_RE.search(header_text)
        if match:
            return "Class", match.group("name")
    return None


def _extract_uht_dump_functions(header_text: str) -> dict[str, tuple[str, str]]:
    functions: dict[str, tuple[str, str]] = {}
    lines = header_text.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line.startswith("UFUNCTION("):
            idx += 1
            continue

        specs = line[len("UFUNCTION("):]
        while not specs.rstrip().endswith(")"):
            idx += 1
            if idx >= len(lines):
                return functions
            specs += " " + lines[idx].strip()
        specs = specs.rstrip()[:-1].strip()

        idx += 1
        decl_parts: list[str] = []
        while idx < len(lines):
            candidate = lines[idx].strip()
            if not candidate or candidate.startswith("//"):
                idx += 1
                continue
            decl_parts.append(candidate)
            if candidate.endswith(";"):
                break
            idx += 1

        if not decl_parts:
            continue

        decl = " ".join(decl_parts).rstrip(";").strip()
        decl = _normalize_dump_function_decl(decl)
        match = _UHT_DUMP_FUNCTION_NAME_RE.match(decl)
        if match:
            functions[match.group("name")] = (specs, decl)
        idx += 1
    return functions


def _parse_decl_signature(decl: str) -> tuple[str, str, str, str, str] | None:
    match = _DECL_SIGNATURE_RE.match(decl.strip())
    if not match:
        return None
    prefix = " ".join(match.group("prefix").split())
    if prefix:
        prefix += " "
    ret_type = " ".join(match.group("ret").split())
    name = match.group("name")
    args = " ".join(match.group("args").split())
    suffix = match.group("suffix") or ""
    return prefix, ret_type, name, args, suffix


def _normalize_dump_function_decl(decl: str) -> str:
    # UHT-generated wrappers expect raw enum types in function signatures even
    # when legacy reflected properties use TEnumAsByte for stored fields.
    return re.sub(r"\bTEnumAsByte\s*<\s*([A-Za-z_][A-Za-z0-9_:]*)\s*>", r"\1", decl)


def _extract_uht_dump_includes(header_text: str) -> set[str]:
    includes: set[str] = set()
    for line in header_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('#include "'):
            header = stripped[len('#include "'):]
            if '"' not in header:
                continue
            header = header.split('"', 1)[0]
            header = normalize_include_header(header)
            if not header:
                continue
            includes.add(header)
            continue
        if not stripped.startswith("//CROSS-MODULE INCLUDE V2:"):
            continue
        fallback_match = re.search(r"-FallbackName=(?P<name>[A-Za-z_][A-Za-z0-9_]*)", stripped)
        if not fallback_match:
            continue
        header = fallback_match.group("name")
        if not header.endswith(".h"):
            header = f"{header}.h"
        header = normalize_include_header(header)
        if not header:
            continue
        includes.add(header)
    return includes


def _extract_uht_dump_member_declares(header_text: str) -> tuple[list[str], set[str]]:
    declares: list[str] = []
    fn_names: set[str] = set()
    for line in header_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("DECLARE_DYNAMIC_"):
            continue
        declares.append(stripped)
        match = re.search(r"\(\s*(?P<name>F[A-Za-z_][A-Za-z0-9_]*)\s*,", stripped)
        if match:
            delegate_name = match.group("name")
            if len(delegate_name) > 1 and delegate_name[0] == "F" and delegate_name[1].isupper():
                fn_names.add(f"{delegate_name[1:]}__DelegateSignature")
    return declares, fn_names


def configure_uht_dump(root: str | Path | None) -> None:
    UHT_DUMP_CPP_NAMES.clear()
    UHT_DUMP_HEADER_BY_KEY.clear()
    UHT_DUMP_HEADER_BY_SYMBOL.clear()
    UHT_DUMP_FUNCTION_DECLS.clear()
    UHT_DUMP_INCLUDES_BY_KEY.clear()
    UHT_DUMP_MEMBER_DECLARES.clear()
    UHT_DUMP_MEMBER_DECLARE_FN_NAMES.clear()
    if not root:
        return

    root_path = Path(root)
    if not root_path.exists():
        return

    for header in root_path.rglob("*.h"):
        try:
            relative = header.relative_to(root_path)
        except ValueError:
            continue
        if len(relative.parts) < 3 or relative.parts[1] != "Public":
            continue
        module = relative.parts[0]
        short_name = header.stem
        try:
            header_text = header.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            header_text = header.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        decl = _extract_uht_dump_decl(header_text)
        if not decl:
            continue
        obj_type, symbol = decl
        key = (module, short_name, obj_type)
        header_name = Path(*relative.parts[2:]).as_posix()
        UHT_DUMP_CPP_NAMES[key] = symbol
        UHT_DUMP_HEADER_BY_KEY[key] = header_name
        UHT_DUMP_HEADER_BY_SYMBOL[(module, symbol)] = header_name
        UHT_DUMP_INCLUDES_BY_KEY[key] = _extract_uht_dump_includes(header_text)
        declares, declare_fn_names = _extract_uht_dump_member_declares(header_text)
        if declares:
            UHT_DUMP_MEMBER_DECLARES[key] = declares
            UHT_DUMP_MEMBER_DECLARE_FN_NAMES[key] = declare_fn_names
        for fn_name, fn_decl in _extract_uht_dump_functions(header_text).items():
            UHT_DUMP_FUNCTION_DECLS[(module, short_name, fn_name)] = fn_decl


def uht_dump_cpp_name(obj_path: str, obj: dict) -> str | None:
    module = short_owner_module(obj_path)
    if not module:
        return None
    return UHT_DUMP_CPP_NAMES.get((module, obj_short_name(obj_path), obj.get("type", "")))


def reflected_header_filename(obj_path: str, obj: dict, objects: dict) -> str:
    module = short_owner_module(obj_path)
    key = (module or "", obj_short_name(obj_path), obj.get("type", ""))
    header = UHT_DUMP_HEADER_BY_KEY.get(key)
    if header:
        return header
    return f'{class_cpp_name(obj_path, obj, objects)}.h'


def uht_dump_header_for_symbol(module: str | None, symbol: str) -> str | None:
    if module:
        return UHT_DUMP_HEADER_BY_SYMBOL.get((module, symbol))
    return None


def header_basename_for_symbol(module: str | None, symbol: str) -> str:
    header = uht_dump_header_for_symbol(module, symbol)
    if header:
        return header
    return f"{symbol}.h"


def uht_dump_function_decl(module: str | None, owner_short_name: str, fn_name: str) -> tuple[str, str] | None:
    if module:
        return UHT_DUMP_FUNCTION_DECLS.get((module, owner_short_name, fn_name))
    return None


def uht_dump_header_includes(obj_path: str, obj: dict) -> set[str]:
    module = short_owner_module(obj_path)
    if not module:
        return set()
    key = (module, obj_short_name(obj_path), obj.get("type", ""))
    return set(UHT_DUMP_INCLUDES_BY_KEY.get(key, set()))


def uht_dump_member_declares(obj_path: str, obj: dict) -> list[str]:
    module = short_owner_module(obj_path)
    if not module:
        return []
    key = (module, obj_short_name(obj_path), obj.get("type", ""))
    return list(UHT_DUMP_MEMBER_DECLARES.get(key, []))


def uht_dump_member_delegate_signature_names(obj_path: str, obj: dict) -> set[str]:
    module = short_owner_module(obj_path)
    if not module:
        return set()
    key = (module, obj_short_name(obj_path), obj.get("type", ""))
    return set(UHT_DUMP_MEMBER_DECLARE_FN_NAMES.get(key, set()))


def class_cpp_name(obj_path: str, obj: dict, objects: dict) -> str:
    """Replicate jmap/header.rs::get_class_name — add A/U/I/F prefixes only
    when the reflected name isn't already prefixed per UE convention."""
    if obj_path in CPP_NAME_OVERRIDES:
        return CPP_NAME_OVERRIDES[obj_path]
    dump_name = uht_dump_cpp_name(obj_path, obj)
    if dump_name:
        return dump_name
    name = obj_short_name(obj_path)
    t = obj.get("type")
    if t == "Enum":
        return name if _has_ue_prefix(name, "E") else f"E{name}"
    if t == "ScriptStruct":
        return name if _has_ue_prefix(name, "F") else f"F{name}"
    if t == "Class":
        flags = obj.get("class_cast_flags", "") or ""
        super_path = obj.get("super_struct")
        if super_path == "/Script/CoreUObject.Interface":
            return name if _has_ue_prefix(name, "I") else f"I{name}"
        if "CASTCLASS_AActor" in flags:
            return name if _has_ue_prefix(name, "A") else f"A{name}"
        return name if _has_ue_prefix(name, "U") else f"U{name}"
    return name


# ---------------------------------------------------------------------------
# Property type → C++ type mapping

# Map jmap property `type` tag → C++ type. Keys match jmap's JSON tag strings
# (e.g. "StructProperty"). Parametric tags (Array, Map, Set, Struct, Object,
# Class, Interface, Enum, Byte, Delegate, Optional) are handled below.
PRIMITIVE_TYPE_MAP = {
    "StrProperty": "FString",
    "NameProperty": "FName",
    "TextProperty": "FText",
    "FieldPathProperty": "FFieldPath",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "UInt16Property": "uint16",
    "UInt32Property": "uint32",
    "UInt64Property": "uint64",
    "Int8Property": "int8",
    "Int16Property": "int16",
    "IntProperty": "int32",
    "Int64Property": "int64",
    "Utf8StrProperty": "FString",
    "AnsiStrProperty": "FString",
}


def local_reflected_header(obj_path: str, objects: dict[str, dict]) -> str | None:
    module = short_owner_module(obj_path)
    if not module or obj_path not in objects:
        return None
    obj = objects[obj_path]
    if obj.get("type") not in ("Class", "ScriptStruct", "Enum"):
        return None
    name = class_cpp_name(obj_path, obj, objects)
    if name in BUILTIN_TYPES:
        return None
    key = (module, obj_short_name(obj_path), obj.get("type", ""))
    if module in ENGINE_MODULES:
        header = ENGINE_TYPE_HEADERS.get(name)
        if not header and len(name) > 1 and name[0] in "AUFIE" and name[1].isupper():
            header = ENGINE_TYPE_HEADERS.get(name[1:])
        if header:
            return normalize_include_header(header)
        dump_header = UHT_DUMP_HEADER_BY_KEY.get(key)
        return normalize_include_header(dump_header)
    dump_header = UHT_DUMP_HEADER_BY_KEY.get(key)
    if dump_header:
        return normalize_include_header(dump_header)
    return normalize_include_header(reflected_header_filename(obj_path, obj, objects))


def enum_cpp_form(obj_path: str | None, objects: dict[str, dict]) -> str | None:
    if not obj_path or obj_path not in objects:
        return None
    obj = objects[obj_path]
    if obj.get("type") != "Enum":
        return None
    form = obj.get("cpp_form")
    return str(form) if form else None


def enum_type_expr(obj_path: str, objects: dict[str, dict], *, byte_wrapper: bool) -> str:
    name = class_cpp_name(obj_path, objects.get(obj_path, {"type": "Enum"}), objects)
    form = enum_cpp_form(obj_path, objects)
    if form == "Namespaced":
        scoped = f"{name}::Type"
        return f"TEnumAsByte<{scoped}>" if byte_wrapper else scoped
    if form == "EnumClass":
        return name
    return f"TEnumAsByte<{name}>" if byte_wrapper else name


def property_type_name(
    prop: dict,
    objects: dict,
    forward_decls: set[str],
    required_headers: set[str] | None = None,
) -> str:
    """Map a jmap property dict (with top-level `type` tag and peer extras)
    to a C++ type expression."""
    if not isinstance(prop, dict):
        return "int32"

    def delegate_cpp_name(delegate_prop: dict) -> str:
        signature = delegate_prop.get("signature_function")
        if signature:
            base = obj_short_name(signature)
            if base.endswith("__DelegateSignature"):
                base = base[:-len("__DelegateSignature")]
            return base if _has_ue_prefix(base, "F") else f"F{base}"
        base = sanitize_ident(delegate_prop.get("name", "Delegate"))
        return base if _has_ue_prefix(base, "F") else f"F{base}"

    tag = prop.get("type", "")
    if tag in PRIMITIVE_TYPE_MAP:
        return PRIMITIVE_TYPE_MAP[tag]
    if tag == "BoolProperty":
        return "bool"
    if tag == "StructProperty":
        s = prop.get("struct")
        if s:
            name = class_cpp_name(s, objects.get(s, {"type": "ScriptStruct"}), objects)
            header = local_reflected_header(s, objects)
            if header and required_headers is not None:
                required_headers.add(header)
            if short_owner_module(s) in ENGINE_MODULES or s not in objects:
                forward_decls.add(name)
            return name
        return "int32"
    if tag == "ArrayProperty":
        inner = prop.get("inner") or {}
        return f"TArray<{property_type_name(inner, objects, forward_decls, required_headers)}>"
    if tag == "MapProperty":
        k = prop.get("key_prop") or {}
        v = prop.get("value_prop") or {}
        return (
            f"TMap<"
            f"{property_type_name(k, objects, forward_decls, required_headers)}, "
            f"{property_type_name(v, objects, forward_decls, required_headers)}>"
        )
    if tag == "SetProperty":
        k = prop.get("key_prop") or {}
        return f"TSet<{property_type_name(k, objects, forward_decls, required_headers)}>"
    if tag == "EnumProperty":
        e = prop.get("enum")
        if e:
            header = local_reflected_header(e, objects)
            if header and required_headers is not None:
                required_headers.add(header)
            return enum_type_expr(e, objects, byte_wrapper=False)
        return "uint8"
    if tag == "ByteProperty":
        e = prop.get("enum")
        if e:
            header = local_reflected_header(e, objects)
            if header and required_headers is not None:
                required_headers.add(header)
            return enum_type_expr(e, objects, byte_wrapper=True)
        return "uint8"
    if tag == "ObjectProperty":
        cls = prop.get("property_class")
        if cls:
            name = class_cpp_name(cls, objects.get(cls, {"type": "Class"}), objects)
            forward_decls.add(name)
            return f"{name}*"
        return "UObject*"
    if tag == "ClassProperty":
        mc = prop.get("meta_class")
        if mc:
            name = class_cpp_name(mc, objects.get(mc, {"type": "Class"}), objects)
            forward_decls.add(name)
            return f"TSubclassOf<{name}>"
        return "UClass*"
    if tag == "WeakObjectProperty":
        cls = prop.get("property_class")
        inner = class_cpp_name(cls, objects.get(cls, {"type": "Class"}), objects) if cls else "UObject"
        forward_decls.add(inner)
        return f"TWeakObjectPtr<{inner}>"
    if tag == "SoftObjectProperty":
        cls = prop.get("property_class")
        inner = class_cpp_name(cls, objects.get(cls, {"type": "Class"}), objects) if cls else "UObject"
        forward_decls.add(inner)
        return f"TSoftObjectPtr<{inner}>"
    if tag == "SoftClassProperty":
        mc = prop.get("meta_class")
        inner = "UObject"
        if mc:
            inner = class_cpp_name(mc, objects.get(mc, {"type": "Class"}), objects)
            forward_decls.add(inner)
        return f"TSoftClassPtr<{inner}>"
    if tag == "LazyObjectProperty":
        return "TLazyObjectPtr<UObject>"
    if tag == "InterfaceProperty":
        iface = prop.get("interface_class")
        if iface:
            name = class_cpp_name(iface, objects.get(iface, {"type": "Class"}), objects)
            forward_decls.add(name)
            return f"TScriptInterface<{name}>"
        return "TScriptInterface<IInterface>"
    if tag == "DelegateProperty":
        return delegate_cpp_name(prop)
    if tag in ("MulticastInlineDelegateProperty", "MulticastSparseDelegateProperty",
               "MulticastDelegateProperty"):
        return delegate_cpp_name(prop)
    return "int32"


# ---------------------------------------------------------------------------
# UPROPERTY / UFUNCTION specifier derivation (minimal — can be extended)

def uproperty_specifiers(prop: dict) -> str:
    """Return text inside UPROPERTY(...). Conservative — prefer safety."""
    flags = prop.get("flags", "") or ""
    specs: list[str] = []
    if "CPF_Edit" in flags:
        specs.append("EditAnywhere")
    else:
        specs.append("VisibleAnywhere")
    if "CPF_BlueprintVisible" in flags:
        specs.append("BlueprintReadWrite" if "CPF_BlueprintReadOnly" not in flags else "BlueprintReadOnly")
    if "CPF_SaveGame" in flags:
        specs.append("SaveGame")
    if "CPF_Transient" in flags:
        specs.append("Transient")
    if "CPF_Config" in flags:
        specs.append("Config")
    if "CPF_Net" in flags:
        specs.append("Replicated")
    return ", ".join(specs)


def ufunction_specifiers(fn: dict) -> str:
    flags = fn.get("function_flags", "") or ""
    specs: list[str] = []
    if "FUNC_BlueprintCallable" in flags:
        specs.append("BlueprintCallable")
    if "FUNC_BlueprintEvent" in flags:
        specs.append("BlueprintImplementableEvent" if "FUNC_Native" not in flags else "BlueprintNativeEvent")
    if "FUNC_Exec" in flags:
        specs.append("Exec")
    if "FUNC_Net" in flags:
        if "FUNC_NetServer" in flags:
            specs.append("Server, Reliable")
        elif "FUNC_NetClient" in flags:
            specs.append("Client, Reliable")
        else:
            specs.append("NetMulticast, Reliable")
        if "FUNC_NetValidate" in flags:
            specs.append("WithValidation")
    if "FUNC_Static" in flags:
        specs.append("Category=\"Generated\"")
    else:
        specs.append("Category=\"Generated\"")
    return ", ".join(dict.fromkeys(specs))


def uclass_specifiers(obj: dict) -> str:
    flags = obj.get("class_flags", "") or ""
    specs: list[str] = []
    if "CLASS_Abstract" in flags:
        specs.append("Abstract")
    if "CLASS_Config" in flags:
        specs.append("Config=Game")
    if "CLASS_DefaultConfig" in flags:
        specs.append("DefaultConfig")
    if "CLASS_PerObjectConfig" in flags:
        specs.append("PerObjectConfig")
    return ", ".join(dict.fromkeys(specs))


def uinterface_uclass_name(path: str) -> str:
    name = obj_short_name(path)
    return name if _has_ue_prefix(name, "U") else f"U{name}"


def uinterface_specifiers(obj: dict, blueprintable: bool) -> str:
    flags = obj.get("class_flags", "") or ""
    specs: list[str] = ["Blueprintable" if blueprintable else "BlueprintType"]
    if not blueprintable:
        specs.append("meta=(CannotImplementInterfaceInBlueprint)")
    if "CLASS_MinimalAPI" in flags:
        specs.append("MinimalAPI")
    return ", ".join(dict.fromkeys(specs))


# ---------------------------------------------------------------------------
# Emitters

HEADER_PROLOGUE = """// Auto-generated from jmap reflection dump. Bodies are stubs.
// Source: {source}
// Module: {module}
// Generated by tools/jmap_to_uht.py — edit freely after inspection.
#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "UObject/ObjectMacros.h"
#include "UObject/ScriptDelegates.h"
#include "UObject/ScriptInterface.h"
#include "Engine/DataTable.h"
#include "Engine/EngineTypes.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/Character.h"
#include "GameFramework/Controller.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/HUD.h"
#include "Components/ActorComponent.h"
#include "Components/SceneComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "TimerManager.h"
{extra_includes}
{forward_decls}
"""

# Types that are defined by CoreMinimal.h / standard engine headers we bulk-
# include in the prologue. Never forward-declare these — it would conflict
# with their real declarations.
BUILTIN_TYPES = {
    "bool", "float", "double",
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64",
    "FString", "FName", "FText", "FFieldPath",
    "FScriptDelegate", "FMulticastScriptDelegate",
    # Math / containers from CoreMinimal
    "FVector", "FVector2D", "FVector4", "FIntVector", "FIntPoint",
    "FRotator", "FQuat", "FTransform", "FMatrix", "FPlane",
    "FColor", "FLinearColor", "FBox", "FBox2D", "FSphere", "FRay",
    "FDateTime", "FTimespan", "FGuid", "FMD5Hash", "FTimerHandle",
    # Networking / quantized vector helpers
    "FVector_NetQuantize", "FVector_NetQuantize10",
    "FVector_NetQuantize100", "FVector_NetQuantizeNormal",
    # Engine standard types (from headers we bulk-include)
    "FHitResult", "FDamageEvent", "FOverlapResult",
    "FTableRowBase",
}


def fwd_decl_block(forwards: set[str]) -> str:
    if not forwards:
        return ""
    lines = []
    for f in sorted(forwards):
        if not f or f in BUILTIN_TYPES:
            continue
        if f.startswith(("U", "A", "I")) and len(f) > 1 and f[1].isupper():
            lines.append(f"class {f};")
        elif f.startswith("F") and len(f) > 1 and f[1].isupper():
            lines.append(f"struct {f};")
        elif f.startswith("E") and len(f) > 1 and f[1].isupper():
            # enums need the actual definition; skip forward-decl.
            pass
        else:
            lines.append(f"class {f};")
    return "\n".join(lines) + ("\n" if lines else "")


def include_for_super_type(super_name: str, super_mod: str | None) -> str:
    if not super_name or super_name in BUILTIN_TYPES:
        return ""
    if super_mod and super_mod in ENGINE_MODULES:
        header = ENGINE_TYPE_HEADERS.get(super_name)
        if not header and len(super_name) > 1 and super_name[0] in "AUFIE" and super_name[1].isupper():
            header = ENGINE_TYPE_HEADERS.get(super_name[1:])
        if not header:
            header = uht_dump_header_for_symbol(super_mod, super_name)
        header = normalize_include_header(header)
        if header:
            return f'#include "{header}"\n'
        return ""
    dump_header = normalize_include_header(uht_dump_header_for_symbol(super_mod, super_name))
    if dump_header:
        return f'#include "{dump_header}"\n'
    if super_mod and super_mod not in ENGINE_MODULES:
        header = normalize_include_header(header_basename_for_symbol(super_mod, super_name))
        if header:
            return f'#include "{header}"\n'
        return ""
    header = ENGINE_TYPE_HEADERS.get(super_name)
    if not header and len(super_name) > 1 and super_name[0] in "AUFIE" and super_name[1].isupper():
        header = ENGINE_TYPE_HEADERS.get(super_name[1:])
    header = normalize_include_header(header)
    if header:
        return f'#include "{header}"\n'
    return ""


def render_include_block(include_directives: set[str]) -> str:
    if not include_directives:
        return ""
    return "\n".join(sorted(include_directives)) + "\n"


def emit_enum(path: str, obj: dict, out_dir: Path, source: str) -> str:
    cpp_name = sanitize_ident(class_cpp_name(path, obj, {}))
    header_name = reflected_header_filename(path, obj, {})
    generated_header = f'{Path(header_name).stem}.generated.h'
    enum_form = enum_cpp_form(path, {path: obj})
    entries = obj.get("names") or []
    # entries is list<[string, int]>; the string is usually "EFoo::Value".
    prefix = f"{cpp_name}::"
    items: list[tuple[int, str]] = []
    for entry in entries:
        if isinstance(entry, dict):
            k, v = entry.get("name", ""), entry.get("value", 0)
        else:
            k, v = entry[0], entry[1]
        s = k[len(prefix):] if k.startswith(prefix) else k.split("::")[-1]
        items.append((int(v), sanitize_ident(s)))
    items.sort(key=lambda t: t[0])
    lines = [
        HEADER_PROLOGUE.format(source=source, module=path, extra_includes="",
                                forward_decls=""),
        f'#include "{generated_header}"',
        "",
        "UENUM(BlueprintType)",
    ]
    if enum_form == "Namespaced":
        lines.extend([f"namespace {cpp_name} {{", "    enum Type {"])
        item_prefix = "        "
        lines_suffix = ["    };", "}"]
    elif enum_form == "EnumClass":
        lines.extend([f"enum class {cpp_name} : uint8", "{"])
        item_prefix = "    "
        lines_suffix = ["};"]
    else:
        lines.extend([f"enum {cpp_name}", "{"])
        item_prefix = "    "
        lines_suffix = ["};"]
    seen = set()
    for v, s in items:
        if s.endswith("_MAX") and v > 0xFF:
            continue
        # UENUM values must be unique per name within the enum
        if s in seen:
            s = f"{s}_{v}"
        seen.add(s)
        lines.append(f'{item_prefix}{s} = {v} UMETA(DisplayName="{s}"),')
    lines.extend(lines_suffix)
    filename = header_name
    (out_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return filename


def emit_struct(path: str, obj: dict, objects: dict, out_dir: Path, source: str) -> str:
    cpp_name = class_cpp_name(path, obj, objects)
    module_name = short_owner_module(path)
    api_macro = module_api_macro(module_name)
    export_prefix = f"{api_macro} " if api_macro else ""
    header_name = reflected_header_filename(path, obj, objects)
    generated_header = f'{Path(header_name).stem}.generated.h'
    forwards: set[str] = set()
    required_headers: set[str] = set()
    body_lines: list[str] = []
    for prop in obj.get("properties", []) or []:
        t = property_type_name(prop, objects, forwards, required_headers)
        n = sanitize_ident(prop.get("name", "Prop"))
        specs = uproperty_specifiers(prop)
        if specs:
            body_lines.append(f"    UPROPERTY({specs})")
        else:
            body_lines.append(f"    UPROPERTY()")
        body_lines.append(f"    {t} {n};")
        body_lines.append("")

    super_path = obj.get("super_struct")
    super_cpp = ""
    include_directives: set[str] = set()
    include_directives.update(f'#include "{header}"' for header in uht_dump_header_includes(path, obj))
    if super_path:
        super_name = class_cpp_name(super_path, objects.get(super_path, {'type':'ScriptStruct'}), objects)
        super_cpp = f" : public {super_name}"
        super_mod = short_owner_module(super_path)
        super_include = include_for_super_type(super_name, super_mod).strip()
        if super_include:
            include_directives.add(super_include)
        forwards.discard(super_name)
    required_headers.discard(header_name)
    include_directives.update(f'#include "{header}"' for header in required_headers)

    prolog = HEADER_PROLOGUE.format(source=source, module=path,
                                     extra_includes=render_include_block(include_directives),
                                     forward_decls=fwd_decl_block(forwards))
    lines = [
        prolog,
        f'#include "{generated_header}"',
        "",
        "USTRUCT(BlueprintType)",
        f"struct {export_prefix}{cpp_name}{super_cpp}",
        "{",
        "    GENERATED_BODY()",
        "",
    ]
    lines.extend(body_lines)
    lines.append("};")
    lines.append("")
    lines.append(f"FORCEINLINE uint32 GetTypeHash(const {cpp_name}& Value) {{ return 0; }}")
    filename = header_name
    (out_dir / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return filename


def _fn_signature(
    fn: dict,
    objects: dict,
    forwards: set[str],
    required_headers: set[str] | None = None,
    reserved_names: set[str] | None = None,
) -> tuple[str, str, str]:
    """Return (return_type, args, function_flags_text) for a UFunction."""
    params: list[tuple[str, str, bool]] = []  # (type, name, is_return)
    ret_type = "void"
    used_names = set(reserved_names or ())
    fn_flags = fn.get("function_flags", "") or ""
    for p in fn.get("properties", []) or []:
        flags = p.get("flags", "") or ""
        cpp_t = property_type_name(p, objects, forwards, required_headers)
        if p.get("type") == "ByteProperty" and p.get("enum"):
            cpp_t = enum_type_expr(p["enum"], objects, byte_wrapper=False)
        n = sanitize_ident(p.get("name", "P"))
        if "CPF_ReturnParm" not in flags:
            if n in used_names:
                base_name = f"{n}_Arg"
                n = base_name
                suffix = 2
                while n in used_names:
                    n = f"{base_name}{suffix}"
                    suffix += 1
            used_names.add(n)
        if "CPF_ReturnParm" in flags:
            ret_type = cpp_t
            continue
        if "CPF_OutParm" in flags and "CPF_ConstParm" not in flags and "CPF_ReferenceParm" in flags:
            params.append((f"{cpp_t}&", n, False))
        elif "CPF_ConstParm" in flags and "CPF_ReferenceParm" in flags:
            params.append((f"const {cpp_t}&", n, False))
        elif "FUNC_Net" in fn_flags and cpp_t in ("FString", "FText"):
            params.append((f"const {cpp_t}&", n, False))
        else:
            params.append((cpp_t, n, False))
    args = ", ".join(f"{t} {n}" for t, n, _ in params)
    return ret_type, args, fn_flags


def pure_virtual_default_clause(ret_t: str) -> str:
    if ret_t == "void":
        return ""
    if ret_t.endswith("*"):
        return "return nullptr;"
    if ret_t == "bool":
        return "return false;"
    if ret_t in ("int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"):
        return "return 0;"
    if ret_t == "float":
        return "return 0.0f;"
    if ret_t == "double":
        return "return 0.0;"
    if ret_t.startswith(("TArray<", "TMap<", "TSet<")):
        return f"return {ret_t}();"
    return f"return {ret_t}{{}};"


def stub_return_body(ret_t: str) -> str:
    if ret_t == "void":
        return "{ }"
    if ret_t.endswith("*"):
        return "{ return nullptr; }"
    if ret_t == "bool":
        return "{ return false; }"
    if ret_t == "float":
        return "{ return 0.0f; }"
    if ret_t == "double":
        return "{ return 0.0; }"
    if ret_t in ("int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64"):
        return "{ return 0; }"
    if ret_t.startswith(("TArray<", "TMap<", "TSet<")):
        return f"{{ return {ret_t}(); }}"
    return f"{{ return {ret_t}(); }}"


def emit_class(path: str, obj: dict, objects: dict, out_dir: Path, src_dir: Path, source: str) -> tuple[str, str]:
    if obj.get("super_struct") == "/Script/CoreUObject.Interface" or "CLASS_Interface" in (obj.get("class_flags", "") or ""):
        interface_name = class_cpp_name(path, obj, objects)
        owner_short_name = obj_short_name(path)
        module_name = short_owner_module(path)
        uclass_name = uinterface_uclass_name(path)
        header_name = reflected_header_filename(path, obj, objects)
        generated_header = f'{Path(header_name).stem}.generated.h'
        forwards: set[str] = set()
        required_headers: set[str] = set()
        func_decls: list[str] = []
        has_blueprint_event = False

        for child_path in obj.get("children", []) or []:
            child = objects.get(child_path)
            if not child or child.get("type") != "Function":
                continue
            fn_name = sanitize_ident(obj_short_name(child_path))
            ret_t, args, _f_flags = _fn_signature(child, objects, forwards, required_headers)
            specs = ufunction_specifiers(child)
            decl_text = f"{ret_t} {fn_name}({args})"
            override = uht_dump_function_decl(module_name, owner_short_name, fn_name)
            if override:
                specs, dump_decl = override
                parsed_decl = _parse_decl_signature(dump_decl)
                if parsed_decl:
                    prefix, ret_t, _name, args, suffix = parsed_decl
                    decl_text = f"{prefix}{ret_t} {fn_name}({args}){suffix}"
                else:
                    decl_text = dump_decl
            is_blueprint_event = "BlueprintNativeEvent" in specs or "BlueprintImplementableEvent" in specs
            has_blueprint_event = has_blueprint_event or is_blueprint_event
            func_decls.append(f"    UFUNCTION({specs})")
            if is_blueprint_event:
                func_decls.append(f"    {decl_text.rstrip(';')};")
            elif override:
                func_decls.append(f"    {decl_text.rstrip(';')};")
            else:
                default_clause = pure_virtual_default_clause(ret_t)
                func_decls.append(f"    virtual {ret_t} {fn_name}({args}) PURE_VIRTUAL({fn_name}, {default_clause});")

        include_directives: set[str] = {'#include "UObject/Interface.h"'}
        include_directives.update(f'#include "{header}"' for header in uht_dump_header_includes(path, obj))
        required_headers.discard(header_name)
        include_directives.update(f'#include "{header}"' for header in required_headers)

        prolog = HEADER_PROLOGUE.format(
            source=source,
            module=path,
            extra_includes=render_include_block(include_directives),
            forward_decls=fwd_decl_block(forwards),
        )
        interface_specs = uinterface_specifiers(obj, has_blueprint_event)
        uinterface_decl = f"UINTERFACE({interface_specs})" if interface_specs else "UINTERFACE()"
        api_macro = module_api_macro(module_name)
        export_prefix = f"{api_macro} " if api_macro else ""
        header_lines = [
            prolog,
            f'#include "{generated_header}"',
            "",
            uinterface_decl,
            f"class {uclass_name} : public UInterface",
            "{",
            "    GENERATED_BODY()",
            "};",
            "",
            f"class {export_prefix}{interface_name} : public IInterface",
            "{",
            "    GENERATED_BODY()",
            "",
            "public:",
        ]
        header_lines.extend(func_decls)
        header_lines.append("};")

        header_path = out_dir / header_name
        header_path.write_text("\n".join(header_lines) + "\n", encoding="utf-8")

        cpp_lines = [
            "// Auto-generated stub — interface bodies are intentionally omitted.",
            f'#include "{header_name}"',
            "",
        ]
        cpp_path = src_dir / f"{interface_name}.cpp"
        cpp_path.write_text("\n".join(cpp_lines) + "\n", encoding="utf-8")
        return header_path.name, cpp_path.name

    cpp_name = class_cpp_name(path, obj, objects)
    owner_short_name = obj_short_name(path)
    module_name = short_owner_module(path)
    header_name = reflected_header_filename(path, obj, objects)
    generated_header = f'{Path(header_name).stem}.generated.h'
    forwards: set[str] = set()
    required_headers: set[str] = set()
    prop_lines: list[str] = []
    member_declares = uht_dump_member_declares(path, obj)
    member_delegate_signature_names = uht_dump_member_delegate_signature_names(path, obj)
    if member_declares and cpp_name not in BUILTIN_TYPES:
        forwards.add(cpp_name)
    has_replicated_props = False
    reserved_param_names = {
        sanitize_ident(prop.get("name", "Prop"))
        for prop in obj.get("properties", []) or []
    }

    # Properties
    for prop in obj.get("properties", []) or []:
        flags = prop.get("flags", "") or ""
        t = property_type_name(prop, objects, forwards, required_headers)
        n = sanitize_ident(prop.get("name", "Prop"))
        specs = uproperty_specifiers(prop)
        if "CPF_Net" in flags:
            has_replicated_props = True
        if specs:
            prop_lines.append(f"    UPROPERTY({specs})")
        else:
            prop_lines.append(f"    UPROPERTY()")
        prop_lines.append(f"    {t} {n};")
        prop_lines.append("")

    # Functions — look up children that are Functions in this module
    func_decls: list[str] = []
    func_defs: list[str] = []
    for child_path in obj.get("children", []) or []:
        child = objects.get(child_path)
        if not child or child.get("type") != "Function":
            continue
        fn_name = sanitize_ident(obj_short_name(child_path))
        if fn_name in member_delegate_signature_names or (
            member_declares and fn_name.endswith("__DelegateSignature")
        ):
            continue
        ret_t, args, f_flags = _fn_signature(
            child,
            objects,
            forwards,
            required_headers,
            reserved_param_names,
        )
        specs = ufunction_specifiers(child)
        decl_text = None
        decl_suffix = ""
        override = uht_dump_function_decl(module_name, owner_short_name, fn_name)
        if override:
            specs, dump_decl = override
            parsed_decl = _parse_decl_signature(dump_decl)
            if parsed_decl:
                prefix, ret_t, _name, args, decl_suffix = parsed_decl
                decl_text = f"{prefix}{ret_t} {fn_name}({args}){decl_suffix}"
                f_flags = f"{f_flags} FUNC_Static".strip() if prefix.startswith("static ") and "FUNC_Static" not in f_flags else f_flags
            else:
                decl_text = dump_decl
        is_blueprint_native_event = "BlueprintNativeEvent" in specs
        is_blueprint_implementable_event = "BlueprintImplementableEvent" in specs
        is_blueprint_event = is_blueprint_native_event or is_blueprint_implementable_event
        is_rpc = "FUNC_Net" in f_flags or any(
            token in specs for token in ("Server", "Client", "NetMulticast")
        )
        needs_validate = "FUNC_NetValidate" in f_flags or "WithValidation" in specs
        is_static = "FUNC_Static" in f_flags
        is_virtual = "FUNC_Native" in f_flags and not is_static and not is_blueprint_event
        qualifiers = "static " if is_static else ("virtual " if is_virtual else "")
        if decl_text is None:
            decl_text = f"{qualifiers}{ret_t} {fn_name}({args})"
        func_decls.append(f"    UFUNCTION({specs})")
        func_decls.append(f"    {decl_text};")
        if is_blueprint_implementable_event:
            continue

        body = stub_return_body(ret_t)
        if is_rpc or is_blueprint_native_event:
            func_defs.append(
                f"{ret_t} {cpp_name}::{fn_name}_Implementation({args}){decl_suffix} {body}"
            )
            if needs_validate:
                func_defs.append(
                    f"bool {cpp_name}::{fn_name}_Validate({args}){decl_suffix} {{ return true; }}"
                )
        else:
            func_defs.append(f"{ret_t} {cpp_name}::{fn_name}({args}){decl_suffix} {body}")

    super_path = obj.get("super_struct")
    super_cpp = "UObject"
    include_directives: set[str] = set()
    include_directives.update(f'#include "{header}"' for header in uht_dump_header_includes(path, obj))
    if super_path:
        super_cpp = class_cpp_name(super_path, objects.get(super_path, {"type": "Class"}), objects)
        super_mod = short_owner_module(super_path)
        super_include = include_for_super_type(super_cpp, super_mod).strip()
        if super_include:
            include_directives.add(super_include)
        forwards.discard(super_cpp)
    needs_lifetime_replicated_props = has_replicated_props and not any(
        "GetLifetimeReplicatedProps(" in decl for decl in member_declares
    )
    if needs_lifetime_replicated_props:
        include_directives.add('#include "Net/UnrealNetwork.h"')
    required_headers.discard(header_name)
    include_directives.update(f'#include "{header}"' for header in required_headers)

    collision_note = ""
    if cpp_name in ENGINE_COLLISION_NAMES:
        collision_note = (
            f"// WARNING: short name '{cpp_name}' collides with a stock UE class.\n"
            "// You may need to rename this class or exclude it from the build.\n"
        )

    prolog = HEADER_PROLOGUE.format(source=source, module=path,
                                     extra_includes=render_include_block(include_directives),
                                     forward_decls=fwd_decl_block(forwards))
    header_lines = [
        collision_note + prolog,
        f'#include "{generated_header}"',
        "",
        f"UCLASS({uclass_specifiers(obj)})" if uclass_specifiers(obj) else "UCLASS()",
        f"class {(module_api_macro(module_name) + ' ') if module_api_macro(module_name) else ''}{cpp_name} : public {super_cpp}",
        "{",
        "    GENERATED_BODY()",
        "",
        "public:",
    ]
    if member_declares:
        header_lines.extend(f"    {decl}" for decl in member_declares)
        header_lines.append("")
    header_lines.extend(prop_lines)
    header_lines.extend(func_decls)
    if needs_lifetime_replicated_props:
        header_lines.append(
            "    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;"
        )
    special_decl_lines = SPECIAL_CLASS_DECLARATIONS.get((module_name or "", cpp_name), [])
    if special_decl_lines:
        header_lines.extend(special_decl_lines)
    header_lines.append("};")

    header_path = out_dir / header_name
    header_path.write_text("\n".join(header_lines) + "\n", encoding="utf-8")

    cpp_lines = [
        "// Auto-generated stub — function bodies do not reflect original game logic.",
        f'#include "{header_name}"',
        "",
    ]
    cpp_lines.extend(func_defs)
    if needs_lifetime_replicated_props:
        if func_defs:
            cpp_lines.append("")
        cpp_lines.extend([
            f"void {cpp_name}::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const",
            "{",
            "    Super::GetLifetimeReplicatedProps(OutLifetimeProps);",
            "}",
        ])
    special_def_lines = SPECIAL_CLASS_DEFINITIONS.get((module_name or "", cpp_name), [])
    if special_def_lines:
        if func_defs or needs_lifetime_replicated_props:
            cpp_lines.append("")
        cpp_lines.extend(special_def_lines)
    cpp_path = src_dir / f"{cpp_name}.cpp"
    cpp_path.write_text("\n".join(cpp_lines) + "\n", encoding="utf-8")

    return header_path.name, cpp_path.name


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jmap", help="input .jmap JSON")
    ap.add_argument("--modules", default="RoboQuest",
                    help="Single UE module short name to emit, or comma-"
                         "separated list, or 'ALL' to emit every module that "
                         "is not in the engine/plugin blacklist.")
    ap.add_argument("--module", dest="modules", help=argparse.SUPPRESS)
    ap.add_argument("--out-public", required=True,
                    help="directory to write .h files into")
    ap.add_argument("--out-private", required=True,
                    help="directory to write .cpp files into")
    ap.add_argument("--uht-dump-root",
                    help="optional UE4SS UHTHeaderDump root used for name/header overrides")
    args = ap.parse_args()

    jmap_path = Path(args.jmap)
    with jmap_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    objects: dict = data["objects"]
    configure_uht_dump(args.uht_dump_root)

    if args.modules == "ALL":
        # Enumerate every /Script/<Module>, drop known engine modules.
        discovered: set[str] = set()
        for p in objects:
            m = short_owner_module(p)
            if m and m not in ENGINE_MODULES:
                discovered.add(m)
        modules = sorted(discovered)
    else:
        modules = [m.strip() for m in args.modules.split(",") if m.strip()]

    out_pub = Path(args.out_public); out_pub.mkdir(parents=True, exist_ok=True)
    out_priv = Path(args.out_private); out_priv.mkdir(parents=True, exist_ok=True)

    # Deduplicate by C++ short name — classes from different modules may
    # collide; last-write-wins would quietly lose data, so we track and warn.
    emitted_names: dict[str, str] = {}  # cpp_name → origin module path
    counts = {"Class": 0, "ScriptStruct": 0, "Enum": 0,
              "skipped_default": 0, "skipped_other": 0, "skipped_dup": 0}

    for module in modules:
        target_prefix = f"/Script/{module}."
        for path, obj in objects.items():
            if not path.startswith(target_prefix):
                continue
            short = obj_short_name(path)
            if short.startswith("Default__"):
                counts["skipped_default"] += 1
                continue
            t = obj.get("type")
            if t not in ("Enum", "ScriptStruct", "Class"):
                counts["skipped_other"] += 1
                continue

            cpp_name = class_cpp_name(path, obj, objects) if t != "Enum" else obj_short_name(path)
            if cpp_name in emitted_names and emitted_names[cpp_name] != path:
                # Duplicate short name across modules — keep the first one we
                # emitted so later cross-references resolve deterministically.
                counts["skipped_dup"] += 1
                continue
            emitted_names[cpp_name] = path

            if t == "Enum":
                emit_enum(path, obj, out_pub, source=str(jmap_path))
                counts["Enum"] += 1
            elif t == "ScriptStruct":
                emit_struct(path, obj, objects, out_pub, source=str(jmap_path))
                counts["ScriptStruct"] += 1
            elif t == "Class":
                emit_class(path, obj, objects, out_pub, out_priv, source=str(jmap_path))
                counts["Class"] += 1

    print(f"Modules emitted: {', '.join(modules)}")
    print("Emission summary:")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
