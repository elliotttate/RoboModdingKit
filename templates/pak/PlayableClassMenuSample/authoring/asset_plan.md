# Asset Plan

This sample is anchored to the generated RoboQuest source already present in the modding kit.

Relevant generated files:

- `projects/RoboQuest_jmap_426_local/Source/RoboQuest/Public/PlayerClassRow.h`
- `projects/RoboQuest_jmap_426_local/Source/RoboQuest/Public/AGameMode.h`
- `projects/RoboQuest_jmap_426_local/Source/RoboQuest/Public/AInteractiveBasecampMenu.h`
- `projects/RoboQuest_jmap_426_local/Source/RoboQuest/Public/RQBlueprintLibrary.h`

## Baseline shipped class names

- `Guardian`
- `Recon`
- `Engineer`
- `Commando`
- `Sentinel`

Use one of those rows as the reference row when you build the first custom class.

## Core authoring targets

- Add or replace rows in `/Game/Data/DT_PlayerClasses`.
- Put new class-owned assets under `/Game/Mods/PlayableClassMenuSample/PlayerClasses/<RowName>/`.
- Reuse or duplicate stock selector and button widgets under `/Game/Blueprint/HUD/Base/Selector/` and `/Game/Blueprint/HUD/Base/Button/`.
- Override `/Game/Blueprint/HUD/Menus/HUD_MenuTitle` if you want a title-screen entry.
- Point an `AAInteractiveBasecampMenu` instance at a custom widget through `MenuClass` if you want a basecamp class terminal.

## `FPlayerClassRow` fields that usually matter

- `Class`
- `ClassWidget`
- `SubCrosshairWidget`
- `IconWidget`
- `Name`
- `passiveName`
- `PassiveDescription`
- `StatDescription`
- `UnlockDescription`
- `ClassIcon`
- `ClassUpgradeIcon`
- `ClassUnlock`
- `ClassPreviewSelector`
- `ClassPreviewSelectorLocked`
- `ClassIconSelector`
- `ClassIconSelectorLocked`
- `ClassIconSelectorSelected`
- `bIsActive`
- `ClassSkill`
- `BashSkill`
- `ClassWeapon`
- `ItemBundles`
- `UpgradePool`
- `PerkCompendiumCategory`
- `bUnlockedInLG`

## Staging map

- `/Game/Data/DT_PlayerClasses` maps to `stage/RoboQuest/Content/Data/DT_PlayerClasses.*`
- `/Game/Mods/PlayableClassMenuSample/...` maps to `stage/RoboQuest/Content/Mods/PlayableClassMenuSample/...`
- `/Game/Blueprint/HUD/Menus/HUD_MenuTitle` maps to `stage/RoboQuest/Content/Blueprint/HUD/Menus/HUD_MenuTitle.*`
- Any other stock widget override keeps its original `/Game/...` package path under `stage/RoboQuest/Content/...`

## Validation hints

- `URQBlueprintLibrary::SyncLoadAllActivePlayerClassRowNames` is the expected runtime list source for active rows.
- `AAGameMode` and `ACharacter_Player` both expose `DT_PlayerClasses`, so broken row data tends to surface quickly when the class roster is refreshed.
- `Character_Player::DelegateOnUnlockClass` and `UnlockTextWidget::OnUnlockedClass` are the unlock-notification path if you add a new unlock flow.
