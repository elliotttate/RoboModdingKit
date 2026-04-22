# RoboQuest Static Mirror Learnings

Updated: 2026-04-22

## Goal

Use `jmap` reflection data to generate a UE 4.27 C++ mirror project that can survive `UnrealHeaderTool` and, eventually, compile cleanly enough to be useful for reverse engineering and editor inspection.

This document records what the generator has learned so far. It is a process log, not a polished spec.

## Ground Rules

- Use reference trees and dumps as metadata or behavior oracles only.
- Do not copy implementation code from external reference trees, `Suzie`, or the UE4SS dump.
- Keep generator fixes generic where possible; accept targeted overrides where the dump does not preserve enough information.

## Current Best References

### `jmap`

Primary source of reflected objects, properties, function signatures, enum forms, and module ownership.

Useful fields:
- `type`
- `super_struct`
- `class_cast_flags`
- `enum`
- `cpp_form`
- function/property flags

### UE4SS `UHTHeaderDump`

Primary source for reconstructed C++ spellings and header basenames.

Why it matters:
- `jmap` object names are not always the real C++ symbol names.
- Some headers intentionally use a basename that does not match the final C++ symbol.
- Cross-module include comments in the dump are a useful signal for module/header relationships.

Concrete examples:
- `AStartTile.h` declares `AAStartTile`
- `ATutoStartTile.h` declares `AATutoStartTile`
- `StartTile.h` declares `FStartTile`
- `RQQuickPlayQosBeaconClient.h` derives from `AQosBeaconClient`

## Generator Changes So Far

### Reflection include fixes

- Local reflected member types now add sibling includes instead of relying on forward declarations.
- This fixed cases like `FAccelByteModelItemConditionGroup` requiring `FAccelByteModelItemPredicate`.

### Enum emission fixes

- Generated enums now use the final C++ enum name rather than the raw object short name.
- `ByteProperty(enum=...)` now emits `TEnumAsByte<...>` when the referenced enum is not an `EnumClass`.
- This fixed the `ECollisionChannel` style failure seen in `FMODOcclusionDetails`.

### Class/config/interface fixes

- Added class specifier emission for config-related class flags.
- Added dedicated `UINTERFACE` + `I...` emission instead of treating interfaces like normal abstract classes.
- Delegate-valued signatures are temporarily degraded to `UObject*` to keep the mirror UHT-safe.

### UHT dump integration

New generator capability:
- Optional `--uht-dump-root` can be passed into the generator.
- The dump is scanned for:
  - reflected type kind
  - reconstructed C++ symbol
  - header basename

This is now used for:
- type-name overrides beyond the handwritten `CPP_NAME_OVERRIDES`
- emitted header filenames
- generated `.generated.h` names
- superclass include basenames for non-engine modules

This should remove a class of false collisions caused by `jmap` short names such as `AStartTile` vs actual `AAStartTile`.

### Interface and event-function fixes

- `BlueprintNativeEvent` and `BlueprintImplementableEvent` members on normal classes must not be emitted as `virtual`.
- Replicated `FString` / `FText` parameters need `const&` in generated signatures.
- Interfaces are not one shape:
  - contract-style interfaces need `CannotImplementInterfaceInBlueprint` and virtual pure methods
  - blueprint-implementable interfaces need `UINTERFACE(Blueprintable)` and non-virtual event members

The UE4SS dump made this split obvious:
- `ISkillManager` is a contract-style interface
- `AdvancedFriendsInterface` is blueprint-implementable

## Project Shape Learnings

- The real project shape is closer to a small game module plus plugins.
- Many things the raw dump exposes as script modules are plugin-owned.
- Reflection-based dependency inference underestimates `Build.cs` dependencies.

Current generator state:
- Engine plugin modules are filtered from the generated project modules.
- Engine plugin ownership is inferred from the local UE 4.27 install.
- Plugins referenced by skipped modules or discovered dependencies are enabled in the generated `.uproject`.

## Known Generator Weak Spots

### Engine/plugin module discovery

The current `ALL` module mode still leaks some engine/runtime modules into the generated project because:
- the hand-maintained engine module blacklist is incomplete
- the plugin scanner has to tolerate Unreal descriptor quirks like trailing commas
- module ownership from engine source and engine plugins still needs tighter reconciliation

Workaround:
- use the known-good project module list while iterating on UHT failures

### Name reconstruction

`jmap` alone is not enough for safe symbol reconstruction.

Examples:
- `/Script/RoboQuest.AStartTile` should be `AAStartTile`
- `/Script/RoboQuest.ATutoStartTile` should be `AATutoStartTile`
- `/Script/RoboQuest.StartTile` should stay `FStartTile`

The UE4SS dump is now the preferred override source for this class of problem.

### Delegate/function signature synthesis

Some generated delegate signatures collide with owner property names.

Current mitigation:
- generated parameter names are renamed with a stable `_Arg` suffix when they would shadow existing class property names

## Current Status

Latest known sequence of blockers:
1. Missing sibling reflected includes
2. Raw `ECollisionChannel` member type
3. Missing `Qos` parent type visibility
4. Delegate parameter shadowing in `AACharacter`
5. Struct/class collision around `StartTile` / `AStartTile`
6. Event UFUNCTION virtual-ness and interface shape mismatches

The current work item is to move from “UHT clean” to “compile-stage clean enough”.

Current verified state:
- `clean20` reaches a successful UHT pass.
- Remaining failures are now in the C++ compile stage.

Compile-stage learnings since then:
- `clean25` confirmed the next real failures are mostly compile-surface mismatches, not UHT failures
- namespaced enums from the dump must stay namespaced in generated code:
  - `EFMODEventProperty`
  - `EFMODSpeakerMode`
  - `EAttachLocation`
- the static generator now emits `namespace EWhatever { enum Type { ... } }` for `cpp_form == Namespaced`
- `ByteProperty(enum=...)` now emits `TEnumAsByte<EWhatever::Type>` for namespaced enums
- the stock UE 4.27 install is not a complete compile oracle for RoboQuest's reflected type surface
  - `BlueprintSessionResult.h` is absent in stock 4.27 source
  - `MovieSceneParameterSectionTemplate.h` and `MovieSceneByteChannel.h` live under different paths than the game's flattened dump view
  - some generated includes match the game's 4.26-era flat header layout better than vanilla 4.27
- to compensate, `clean26` adds a project-local junction:
  - `Source/_engine_module_reference -> E:\RoboQuestReverse\project\RoboQuest\Source\_engine_module_reference`
- generated `Build.cs` files now add `PublicIncludePaths` entries for dependency modules that exist in `_engine_module_reference`

Current unresolved build issue:
- plugin-backed engine modules are still problematic at the UBT/makefile stage in the 4.27 installed build
- observed examples:
  - `ApexDestruction`
  - `Paper2D`
- this is now clearly separate from the earlier header/include reconstruction work
- the remaining question is whether these plugin-backed dependencies should be:
  - enabled differently in the generated `.uproject`
  - treated as reference-only dependencies for the mirror
  - or mapped to a closer RoboQuest-era project/plugin shape

## Next Checks

- Decide how to handle plugin-backed engine modules in the generated mirror target
- Keep using `_engine_module_reference` as the compile-oracle fallback for flat 4.26-style headers
- Separate true missing module ownership from stock-4.27 plugin-loading quirks
- Record the next blocker here before patching again

## UE4SS UHT Dump Learnings

The `UE4SS` `UHTHeaderDump` is now useful for more than class/header name overrides.

What it now drives:
- exact reflected C++ class names
- header basenames
- `UFUNCTION` specifier/declaration overrides when `jmap` under-reports function flags or parameter passing
- support includes from the dump header itself
- fallback support includes from `//CROSS-MODULE INCLUDE V2` comments in the dump header

Concrete fixes it enabled:
- `AdvancedFriendsGameInstance` now emits:
  - `BlueprintCallable, BlueprintImplementableEvent`
  - `const FString& AppId`
- generated class `.cpp` files no longer emit stub bodies for `BlueprintImplementableEvent` methods, which avoids fighting the `*.gen.cpp` wrapper that UHT already generates

Important consequence:
- once real `UFUNCTION` declarations are imported from the dump, the generator can surface support-header gaps that `jmap` never exposed before
- example:
  - `AccelByteUe4Sdk/ABAchievement.h` started pulling in real delegate parameter types like `FDHandler`
  - those types were not reflected as normal `jmap` objects, so the mirror had no `DHandlerDelegate.h`

Current mitigation in progress:
- copy orphan delegate declaration headers from `UHTHeaderDump/<Module>/Public/*Delegate*.h` into the generated module when they are not otherwise emitted from `jmap`
- this treats the dump as a public-surface supplement, not just a naming oracle
- treat dump `CROSS-MODULE INCLUDE V2` comments as real header dependencies during emission
  - example:
    - `FindSessionsCallbackProxyAdvanced.h` needs `BlueprintFindSessionsResultDelegateDelegate.h`
    - `BlueprintFindFriendSessionDelegateDelegate.h` needs `BlueprintSessionResult.h`
  - the dump often records those relationships only as comments, so parsing raw `#include` lines is not enough
- copied raw dump delegate headers need the same normalization pass
  - otherwise the generator fixes only generated class/struct headers while copied `*Delegate*.h` files still carry comment-only dependencies

Follow-on finding:
- some flat dump headers are not missing types; they are aliases into a larger engine/plugin header that already owns the reflected surface
  - concrete example:
    - `OnlineSubsystemUtils/BlueprintSessionResult.h`
    - `OnlineSubsystemUtils/BlueprintFindSessionsResultDelegateDelegate.h`
  - in stock UE 4.27 both actually come from `OnlineSubsystemUtils/Classes/FindSessionsCallbackProxy.h`
  - the real engine header already owns:
    - `FBlueprintSessionResult`
    - `FBlueprintFindSessionsResultDelegate`
    - the generated wrapper and exported `Z_Construct_UDelegateFunction_OnlineSubsystemUtils_BlueprintFindSessionsResultDelegate__DelegateSignature`
  - mirror lesson:
    - do not emulate these as local opaque structs/delegates when the owning engine plugin header exists
    - route the flat fallback headers to the real owning header instead
- copied dump headers must have existing `#include` lines rewritten through the same canonicalization pass
  - only adding missing normalized includes is not enough
  - otherwise a copied header like `BlueprintFindFriendSessionDelegateDelegate.h` can keep its literal `#include "BlueprintSessionResult.h"` and still resolve to `_engine_module_reference` instead of the intended shim or owner header
- copied dump headers must preserve their own `*.generated.h` include exactly
  - the normalization pass should never rewrite or drop a `.generated.h` line
  - dropping it breaks `UDELEGATE(...)` headers even when UHT generated the corresponding wrapper file correctly
- `OnlineSubsystemUtils` is a special include-path case for this mirror
  - the flat `_engine_module_reference/OnlineSubsystemUtils/Public` path hijacks canonical includes like `FindSessionsCallbackProxy.h`
  - once the generated headers are normalized to the real owner header, that flat reference path should be omitted so the compiler resolves to the actual engine plugin source instead
- the same flat-header hijack pattern also shows up in other engine modules
  - examples seen after the `OnlineSubsystemUtils` fix:
    - `MovieSceneEvalTemplate.h` should route to `Evaluation/MovieSceneEvalTemplate.h`
    - `DataTableRowHandle.h` should route to `Engine/DataTable.h`
    - `EAspectRatioAxisConstraint.h` should route to `Engine/EngineTypes.h`
    - `ESlateColorStylingMode.h` should route to `Styling/SlateColor.h`
  - the mirror should prefer canonical engine headers via compile shims and include aliases instead of letting the flat `_engine_module_reference` version win
- interface methods with dump-provided declarations need a different emission rule than normal pure virtual synthesis
  - if the dump already provides a full declaration using `PURE_VIRTUAL(...)`, emit that declaration directly
  - appending a separate `= 0` after a dump-provided `PURE_VIRTUAL(...)` form produces invalid interface headers
  - when reconstructing the declaration from a parsed dump signature, preserve the original prefix such as `virtual `
- some classes contain nested `DECLARE_DYNAMIC_DELEGATE...` member declarations that are not represented cleanly in `jmap`
- in those cases `jmap` exposes `*__DelegateSignature` children, but emitting them as `UFUNCTION` methods is wrong

Concrete example:
- `AccelByteBlueprintsAchievement` should contain:
  - `DECLARE_DYNAMIC_DELEGATE_OneParam(FGetAchievementSuccess, ...)`
  - `DECLARE_DYNAMIC_DELEGATE_OneParam(FQueryUserAchievementsSuccess, ...)`
- the dump proves these are class member declarations, not callable methods

Current mitigation in progress:
- import nested `DECLARE_DYNAMIC_*` lines from the dump-backed class header
- suppress matching `__DelegateSignature` function emission when the dump already provides the member delegate declaration

Additional constraint confirmed by probe:
- class-local delegate declarations must appear before any `UPROPERTY` fields that use their `F...` types
- appending `DECLARE_DYNAMIC_*` lines after the property block is too late for UHT in classes like `AAProjectile`
- a manual probe moving the delegate macros above `AAProjectile`'s fields advanced UHT to the next same-pattern failure in `AArenaTile`

Practical rule:
- for dump-backed class member delegates, emit `DECLARE_DYNAMIC_*` lines immediately after `public:` and before the generated property block

## Compile-Stage Learnings After UHT Recovery

`clean35` is the first mirror variant in this round that gets back through `UHT` and into real C++ compilation after the delegate/import fixes.

First compile-stage blockers observed there:
- generated row-handle wrapper structs like `FLootRowHandle` are being used as `TMap` keys
- raw `_engine_module_reference` headers like `InputCore/Key.h` still expect their own `*.generated.h`, which does not exist in the mirror

Mitigations added:
- generated `USTRUCT` headers now append a trivial
  - `FORCEINLINE uint32 GetTypeHash(const FGeneratedStruct& Value) { return 0; }`
  - this is a compile-only placeholder so `TMap`/`TSet` instantiations can proceed
- compile-shim coverage now includes `InputCore/Key.h`
  - the shim provides a minimal `FKey` plus `GetTypeHash`
  - this keeps the mirror on a UHT-safe / compile-safe header instead of the raw reference copy that still includes `Key.generated.h`
- compile shims are now also the preferred escape hatch for engine-owned flat basenames that would otherwise pull in `_engine_module_reference/*/*.generated.h`
  - examples:
    - `BlueprintFunctionLibrary.h -> Kismet/BlueprintFunctionLibrary.h`
    - `BlueprintAsyncActionBase.h -> Kismet/BlueprintAsyncActionBase.h`
    - `Object.h -> UObject/Object.h`
    - `DateTime.h -> Misc/DateTime.h`
    - `Guid.h -> Misc/Guid.h`
    - `DirectoryPath.h` / `ECollisionChannel.h` / `TableRowBase.h` -> existing engine umbrella headers
    - `MovieSceneTrackTemplateProducer.h -> Compilation/IMovieSceneTrackTemplateProducer.h`
    - `EmptyOnlineDelegateDelegate.h -> Net/OnlineBlueprintCallProxyBase.h`
- compile shims must be unconditional
  - the earlier `#if HACK_HEADER_GENERATOR` wrapper was wrong because that macro is present in the Unreal header tool path and can still leak the flattened reference headers back into the active build surface
  - for this mirror, the safe shim or canonical include needs to be what both UHT and the C++ compiler see
- the generator now normalizes dump-derived engine include basenames before emitting them
  - if a dump asks for `Actor.h`, `DirectoryPath.h`, `ECollisionChannel.h`, or `TableRowBase.h`, the generator now maps that back to the canonical umbrella header and then suppresses it if the prologue already covers it
  - this prevents mixed canonical + flattened-engine includes like:
    - `GameFramework/Actor.h` plus `Actor.h`
    - `Kismet/BlueprintFunctionLibrary.h` plus `BlueprintFunctionLibrary.h`
- the normalization now also suppresses flat headers whose basename corresponds to a `CoreMinimal` builtin
  - examples:
    - `Vector.h`
    - `Rotator.h`
    - `Transform.h`
    - `Color.h`
- the same normalizer now treats flat basenames for prologue-covered engine headers as duplicates
  - examples:
    - `SceneComponent.h`
    - `ActorComponent.h`
    - `PrimitiveComponent.h`
    - `Pawn.h`
    - `Character.h`
- some dump-only engine enum/interface basenames need canonical remaps rather than suppression
  - examples:
    - `Interface.h -> UObject/Interface.h`
    - `ENavLinkDirection.h -> AI/Navigation/NavLinkDefinition.h`
    - `EMovieSceneCompletionMode.h -> Evaluation/MovieSceneCompletionMode.h`
    - `EAttachLocation.h -> Engine/EngineTypes.h`
- delegate support shims that exist only to satisfy C++ need to avoid `UDELEGATE(...)`
  - `UDELEGATE` expects the generated wrapper path that exists in the real engine module
  - for placeholder mirror-only delegate headers, a plain `DECLARE_DYNAMIC_MULTICAST_DELEGATE_*` is safer

Additional findings from later compile probes:
- the original fake shims for `FKey` and `FFontOutlineSettings` were too aggressive
  - stock UE 4.27 already provides reflected definitions for both types
  - a local placeholder `struct FKey` / `struct FFontOutlineSettings` causes redefinition errors and then leaves the generated code with incomplete types
- the correct mitigation is not "better fake structs"
  - it is to redirect the flat basenames back to their real owning headers
  - current redirects now prefer:
    - `Key.h -> InputCoreTypes.h`
    - `FontOutlineSettings.h -> Fonts/SlateFontInfo.h`
    - `UniqueNetIdRepl.h -> GameFramework/OnlineReplStructs.h`
    - `ESlateVisibility.h -> Components/SlateWrapperTypes.h`
    - `EVirtualKeyboardType.h -> Components/SlateWrapperTypes.h`
    - `CustomWidgetNavigationDelegateDelegate.h -> Blueprint/WidgetNavigation.h`
    - `EEndPlayReason.h` / `LightingChannels.h` / `EComponentMobility.h` / `ENetDormancy.h -> Engine/EngineTypes.h`
    - `AssetManager.h -> Engine/AssetManager.h`
    - `SaveGame.h -> GameFramework/SaveGame.h`
    - `PrimaryAssetType.h -> UObject/PrimaryAssetId.h`
    - `BTNode.h -> BehaviorTree/BTNode.h`
    - `BTTaskNode.h -> BehaviorTree/BTTaskNode.h`
    - `IntervalCountdown.h -> AITypes.h`
- `generated_project` is useful as another metadata oracle
  - reference path:
    - `E:\SteamLibrary\steamapps\common\RoboQuest\generated_project`
  - it is clearly synthetic rather than authoritative source
    - `RoboQuest.uproject` describes it as a generated mirror project
  - its overall structure is still useful
    - it keeps most third-party/runtime surfaces under `Plugins/`
    - it only leaves a small set of direct project modules under `Source/`
  - it confirms several of the real include choices above without needing to trust the flattened `_engine_module_reference` copies
  - examples:
    - `AGameInstance.h` includes `InputCoreTypes.h`
    - `DamageFeedbackRow.h` includes `Fonts/SlateFontInfo.h`
    - `APlayerController.h` / `PlayerData.h` include `GameFramework/OnlineReplStructs.h`
    - `Character_Player.h` / `RQEditableText.h` include `Components/SlateWrapperTypes.h`
    - `ACompassLocator.h` / `SkeletalMeshActorWithMobility.h` include `Engine/EngineTypes.h`
    - `AAssetManager.h` includes `Engine/AssetManager.h`
    - `ASaveGame.h` includes `GameFramework/SaveGame.h`
    - `ABTTask.h` includes `BehaviorTree/Tasks/BTTask_BlueprintBase.h`
    - `SkeletalMeshActorWithMobility.h` includes `Animation/SkeletalMeshActor.h`
    - `AGameViewportClient.h` includes `Engine/GameViewportClient.h`
    - `CinematicBubbles.h` includes `Styling/SlateColor.h`
    - `CullingScaleRetainerBox.h` includes `Components/ContentWidget.h`
  - it is not trustworthy for every function signature
    - `APlayerController.h` still declares `OnBlueprintPreClientTravel` with `TEnumAsByte<ETravelType>`
    - when synthetic references disagree on function declarations, defer to the declaration shape that survives the build
- enum emission needs one more guard for reflected byte enums
  - some dumps carry synthetic sentinels like `EGDKUserPrivilege_MAX = 256`
  - `UENUM(BlueprintType) enum class ... : uint8` cannot represent that value
  - current mitigation: skip `_MAX` entries when the dumped value exceeds `0xFF`
- not every remaining compile failure should be solved by keeping `_engine_module_reference` on the include path
  - once the mirror knows the real engine owner for a header, the flat reference root becomes a liability because local sibling includes inside that tree bypass the compile shims
  - current strategy:
    - keep compile shims for engine-owned flat basenames
    - stop adding `_engine_module_reference` include roots for modules we can now canonicalize directly:
      - `AIModule`
      - `CoreUObject`
      - `Engine`
      - `InputCore`
      - `SlateCore`
      - `UMG`
      - `OnlineSubsystemUtils`
- function signatures need different enum handling than reflected properties
  - property fields often want `TEnumAsByte<...>` for legacy non-`enum class` UE enums
  - `UFUNCTION` signatures do not always want that wrapper
  - concrete example:
    - `AAPlayerController::OnBlueprintPreClientTravel` must take `ETravelType`, not `TEnumAsByte<ETravelType>`
  - current mitigation:
    - for enum-backed `ByteProperty` function params/returns, emit the raw enum type in `_fn_signature`
    - normalize dump-sourced `UFUNCTION` declarations the same way before reusing them as authoritative overrides

Additional findings from the low-parallel `clean53` compile probe:
- reducing UBT to `-MaxParallelActions=4` is enough to turn the build log back into a useful signal source
  - `clean51` was dominated by paging-file / compiler heap failures
  - `clean53` reaches deep enough into `RoboQuest` compilation to expose real missing-header and dependency errors
- another cluster of flat engine includes needed canonical remaps
  - `BoxComponent.h -> Components/BoxComponent.h`
  - `CharacterMovementComponent.h -> GameFramework/CharacterMovementComponent.h`
  - `ParticleSystemComponent.h -> Particles/ParticleSystemComponent.h`
  - `LocalPlayer.h -> Engine/LocalPlayer.h`
  - `EditableText.h -> Components/EditableText.h`
- `generated_project` confirmed all five of those include owners
  - `SpecialTriggerBoxComponent.h`
  - `ClientAuthorativeCMC.h`
  - `FOVParticleSystemComponent.h`
  - `RoboquestLocalPlayer.h`
  - `RQEditableText.h`
- another late-stage engine enum header alias was needed
  - `ECollisionEnabled.h -> Engine/EngineTypes.h`
  - the flat include is another signal that the dump basename should collapse back to the owner umbrella header
- the same umbrella-header rule also applies to `ENetworkSmoothingMode`
  - `ENetworkSmoothingMode` lives in `Engine/EngineTypes.h`
  - `generated_project/Source/RoboQuest/Public/RQBlueprintLibrary.h` avoids the flat `ENetworkSmoothingMode.h` include entirely
  - current mitigation:
    - add `ENetworkSmoothingMode -> Engine/EngineTypes.h` to engine type ownership
    - canonicalize `ENetworkSmoothingMode.h -> Engine/EngineTypes.h`
    - add the matching compile shim so copied dump headers cannot reintroduce the flat basename
- `UMediaSource` failures in `CinematicRow.gen.cpp` and `VideoWidget.gen.cpp` are not just include-alias problems
  - the generated headers only forward-declare `UMediaSource`
  - the real issue is that `MediaAssets` was not being treated as an engine-owned dependency module
  - current mitigation:
    - add `MediaAssets` to the engine-module set
    - let dependency inference pull `MediaAssets` into `RoboQuest.Build.cs`
    - exclude `MediaAssets` from `_engine_module_reference` include roots the same way as the other canonicalized engine modules
- `OnlineSubsystemUtils` is not sufficient on its own for some plugin modules
  - `AdvancedSessions` linked against `FOnlineSessionSettings` symbols but only had `OnlineSubsystemUtils`
  - the surviving dependency set points to `OnlineSubsystem` as the missing owner
  - current mitigation:
    - when dependency inference adds `OnlineSubsystemUtils`, also add `OnlineSubsystem`
- `UReverbEffect` in UE 4.27 is `MinimalAPI`, which matters for generated subclasses
  - the base class declares `PostEditChangeProperty`, but cross-module subclasses cannot rely on the engine exporting that editor hook cleanly
  - the real FMOD plugin works around this in `UFMODSnapshotReverb` by overriding `PostEditChangeProperty` behind `#if WITH_EDITORONLY_DATA`
  - current mitigation:
    - inject targeted extra declarations/definitions for `UFMODSnapshotReverb`
    - preserve:
      - constructor with `FObjectInitializer`
      - `IsAsset() const override`
      - editor-only `PostEditChangeProperty(...) override`
- once the build reaches link, `UFUNCTION` thunk ownership matters as much as the header surface
  - plain native generated methods can keep direct stub bodies on `Class::Function(...)`
  - `BlueprintNativeEvent` methods must instead stub `Class::Function_Implementation(...)`
  - RPC methods (`Server` / `Client` / `NetMulticast`) must also stub `Class::Function_Implementation(...)`
  - RPC methods with `WithValidation` must additionally stub `Class::Function_Validate(...)`
  - otherwise the failure mode is exactly what `clean56` showed:
    - duplicate symbol errors for the public thunk name because UHT already generated it
    - unresolved externals for `_Implementation` / `_Validate`
- the `clean57` link pass exposed the next layer behind the thunk fix
  - cross-module reflected classes need their module export macro on the generated declaration
    - concrete failures: `AJumpingAIController`, `AASpline_Moving`
    - current mitigation: emit `<MODULE>_API` on generated `UCLASS` / `UINTERFACE` / `USTRUCT` declarations
    - refinement from `clean58`: the export macro belongs on the `I...` interface type, not on the `U... : UInterface` wrapper
  - replicated properties are enough to require `GetLifetimeReplicatedProps(...)`
    - this shows up in classes like `UASkill`, `AAInteractive`, `AAHoleSpawner`, `AAGameState`, `AAPlayerState`, `ACharacter_Player`
    - current mitigation: if any property carries `CPF_Net`, emit a minimal override that only calls `Super::GetLifetimeReplicatedProps(...)`
  - `RoboQuest` also still needs the `GameplayTasks` module even after the earlier engine-module cleanup
    - concrete symptom: unresolved `IGameplayTaskOwnerInterface::OnGameplayTaskActivated`
    - the validated dependency set includes `GameplayTasks`
    - current mitigation: if dependency inference pulls `AIModule`, also add `GameplayTasks`
  - UE 4.26 also requires an actual module bootstrap translation unit per emitted module
    - concrete symptom on the first 4.26 pass:
      - unresolved `IMPLEMENT_MODULE_<ModuleName>` symbols for `AdvancedSessions`, `RyseUpTool`, `TriggerEffectManager`, `FMODStudio`, `AccelByteUe4Sdk`, and `RoboQuest`
    - root cause:
      - the generator emitted `Build.cs`, headers, and class stubs, but no per-module `Private/<Module>.cpp` that calls the module macro
      - the 4.27 build tolerated this gap, but the 4.26 linker did not
    - current mitigation:
      - emit `Private/<Module>.cpp` for every generated module
      - use `IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, <RootModule>, "<RootModule>");` for the root game module
      - use `IMPLEMENT_MODULE(FDefaultModuleImpl, <ModuleName>);` for the rest
  - a clean editor build is still not enough if the target only names the root module
    - concrete symptom on the first editor launch:
      - Unreal reported `Incompatible or missing module` for `DonAINavigation`, `OnlineSubsystemGOG`, `OnlineSubsystemRedpointEOS`, `RedpointEOSAuthDiscord`, `RedpointEOSAuthSteam`, `RMAFoliageTools`, and `SteamUtilities`
      - launching the editor then triggered an on-demand UBT pass that said `Target is up to date`, because those standalone project modules were never part of the target graph
    - current mitigation:
      - emit `ExtraModuleNames.AddRange(...)` in both `Target.cs` files with every generated project module, not just the root game module
  - UE 4.26 still needs a few canonical include and dependency corrections in the standalone modules
    - `GameInstanceSubsystem.h` must collapse to `Subsystems/GameInstanceSubsystem.h`
    - `BlackboardKeySelector.h` must collapse to `BehaviorTree/BehaviorTreeTypes.h`
    - `RedpointEOSAuthDiscord` and `RedpointEOSAuthSteam` need a dependency on `OnlineSubsystemRedpointEOS`
    - `OnlineSubsystemGOG` needs `NetCore` in addition to its packet-handler usage so `FDDoSDetection` resolves at link time

## `sdk_dump_tools` Learnings

Reference path:
- `E:\SteamLibrary\steamapps\common\RoboQuest\sdk_dump_tools`

What it is:
- a local offline pipeline that converts UE4SS dump artifacts into a `sdkgenny`/`regenny`-style SDK layout
- main outputs:
  - `out/RoboQuest.generated.genny`
  - `out/generated_sdk/...`

What it is good for:
- confirming flat external type/header names that RoboQuest actually uses
- confirming some parent/field relationships in a layout-oriented way
- quickly checking whether an external type exists in the game's dump surface at all

Concrete useful examples:
- `FBlueprintSessionResult.hpp`
- `FFontOutlineSettings.hpp`
- `ANavLinkProxy.hpp`
- `UUserWidget.hpp`
- `RyseUpTool/AJumpingNavLinkProxy.hpp` includes `..\ANavLinkProxy.hpp`
- `RoboQuest/FDamageFeedbackRow.hpp` uses `FFontOutlineSettings`
- `RoboQuest/FRQBPGameInvite.hpp` uses `FBlueprintSessionResult`

What it is not good for:
- UHT-safe source emission
- exact engine/plugin module ownership for external types
- precise field typing in cyclic or parser-hostile cases

Important caveats from its own work log:
- declaration cycles are intentionally degraded to raw `byte[...]` spans
- nested-template fields can also be degraded to raw bytes
- output is a layout SDK, not a clean compilable Unreal source mirror

Bottom line:
- `sdk_dump_tools` is worth using as a supplemental flat-type oracle
- it is not a replacement for `UE4SS UHTHeaderDump` or `jmap`
- the best use is to help resolve "does this external type/header exist and what flat name does RoboQuest expect?" while keeping module ownership logic elsewhere

## Build Milestone

- `E:\RoboQuestReverse\project\RoboQuest_jmap_427_clean59` is the first clean end-to-end 4.27 build from the current generator
- build proof:
  - `E:\RoboQuestReverse\project\RoboQuest_jmap_427_clean59\build_clean59_probe.log`
  - terminal summary at the end of the log:
    - `[279/279] RoboQuestEditor.target`
    - `Total execution time: 126.30 seconds`
- `E:\RoboQuestReverse\project\RoboQuest_jmap_426_try1` also builds cleanly under `E:\Epic Games\UE_4.26`
- build proof:
  - `E:\RoboQuestReverse\project\RoboQuest_jmap_426_try1\build_426_try1_rerun.log`
  - terminal summary at the end of the log:
    - `[19/19] RoboQuestEditor.target`
    - `Total execution time: 17.77 seconds`
- after the follow-up target/dependency fixes, `E:\RoboQuestReverse\project\RoboQuest_jmap_426_try1` also reaches a live editor launch under `E:\Epic Games\UE_4.26`
- follow-up build proof:
  - `E:\RoboQuestReverse\project\RoboQuest_jmap_426_try1\build_426_try1_allmodules.log`
  - `E:\RoboQuestReverse\project\RoboQuest_jmap_426_try1\build_426_try1_editorretry2.log`
