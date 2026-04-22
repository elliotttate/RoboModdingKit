# TestPlayableClassMod

This is a UE4SS runtime mod for probing and then extending RoboQuest's player-class selection flow.

The first revision focuses on:

- locating the class-list functions from Lua
- logging active class names
- probing row lookup behavior for shipped class rows

Once the row and return-value shapes are confirmed in `UE4SS.log`, this same mod can be upgraded into a runtime test-class injector.
