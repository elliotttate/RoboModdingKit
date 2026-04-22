-- UHTDumper mod — triggers UE4SS's generate_uht_compatible_headers once
-- UObjects are loaded, then exits the game so the pipeline can collect
-- output files without a human clicking around.
--
-- The UHT dumper walks every loaded UObject, so we wait until the engine
-- has finished boot. `NotifyOnNewObject("/Script/Engine.GameInstance", ...)`
-- fires after the engine has constructed the primary game instance, which
-- is a reliable "reflection is live" signal on UE4.26.
local sawTrigger = false

local function runDump()
    if sawTrigger then return end
    sawTrigger = true
    print("[UHTDumper] triggering UHT generator...")
    -- UE4SS registers GenerateUHTCompatibleHeaders as a global Lua symbol.
    local ok, err = pcall(GenerateUHTCompatibleHeaders)
    if not ok then
        print("[UHTDumper] UHT dump failed: " .. tostring(err))
    else
        print("[UHTDumper] UHT dump complete.")
    end
    -- DumpAllObjects is also exposed and writes alongside the UHT tree.
    pcall(DumpAllObjects)
    -- Wait a beat for disk flush, then quit.
    print("[UHTDumper] Scheduling game shutdown in ~5s")
    ExecuteWithDelay(5000, function()
        print("[UHTDumper] Calling exit()")
        os.exit()
    end)
end

-- NotifyOnNewObject fires for the first instance of any matching class.
NotifyOnNewObject("/Script/Engine.GameInstance", function(newObject)
    print("[UHTDumper] GameInstance observed — scheduling dump")
    ExecuteWithDelay(3000, runDump)
end)

-- Fallback: if NotifyOnNewObject hasn't fired in 60s (e.g. different
-- loading order), run the dump anyway.
ExecuteWithDelay(60000, runDump)
