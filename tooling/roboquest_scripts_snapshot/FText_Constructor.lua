-- FText_Constructor.lua — intentional no-match AOB for RoboQuest (UE 4.26.2).
--
-- Context
-- -------
-- UE 4.26's `FText::FText(FString&&)` is inlined by MSVC /O2 into every
-- caller in RoboQuest's shipping build, so there is no standalone function
-- to point at. patternsleuth's 12 built-in AOBs all miss for the same
-- reason. UE4SS v3.0.1 validates any address we return by actually CALLING
-- it — and crashes (no SEH) if the target isn't really the ctor.
--
-- Strategy
-- --------
-- Return an AOB that we KNOW won't match anywhere. UE4SS's scan completes
-- with zero hits, adds a non-fatal error to its scan_result, and the
-- outer boot loop continues (`if (!bHasFatalError) break`). FText lookups
-- from Lua will fail later with a clean "symbol not resolved" message,
-- but every other subsystem — including the UHT dumper — runs fine.
--
-- The AOB is 16 bytes of 0xFE; no such sequence appears anywhere in the
-- binary (verified via IDA `find_bytes`).

function Register()
    return "FE FE FE FE FE FE FE FE FE FE FE FE FE FE FE FE"
end

function OnMatchFound(matchAddress)
    -- Should never fire. Return 0 explicitly so if it ever does we get a
    -- clean "invalid address" error instead of a crash.
    return 0
end
