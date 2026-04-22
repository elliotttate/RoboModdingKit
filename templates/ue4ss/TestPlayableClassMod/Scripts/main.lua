local mod_name = "TestPlayableClassMod"

local target_row_name = "Magus"
local test_class_name = "Test Class"
local base_class_name = "Guardian"

local load_player_class_row_fn = "/Script/RoboQuest.RQBlueprintLibrary:SyncLoadPlayerClassRow"
local bp_game_instance_prefix = "/Game/Blueprint/GameSystem/GameInstance/BP_AGameInstance.BP_AGameInstance_C:"
local is_unlocked_fn = bp_game_instance_prefix .. "IsPlayerClassUnlocked"
local unlocked_amount_fn = bp_game_instance_prefix .. "GetPlayerClassUnlockedAmount"

for _, prefix in ipairs({
    ".\\Mods\\shared\\?.lua;",
    ".\\Mods\\shared\\?\\?.lua;",
}) do
    if not string.find(package.path, prefix, 1, true) then
        package.path = prefix .. package.path
    end
end

local UEHelpers = require("UEHelpers")

local state = {
    hook_ids = {},
    hook_failures = {},
    pending_alias = {},
    game_instance = nil,
    smoke_test_done = false,
    bp_hooks_registered = false,
    bp_retry_started = false,
}

local function log(message)
    print(string.format("[%s] %s", mod_name, message))
end

local function safe_call(fn, fallback)
    local ok, result = pcall(fn)
    if ok then
        return result
    end
    return fallback
end

local function value_type(value)
    local lua_type = type(value)
    if lua_type == "userdata" and value and value.type then
        local reported_type = safe_call(function()
            return value:type()
        end)
        if reported_type then
            return reported_type
        end
    end
    return lua_type
end

local function value_to_string(value)
    if value == nil then
        return "nil"
    end

    local kind = value_type(value)
    if (kind == "RemoteUnrealParam" or kind == "LocalUnrealParam") and value.get then
        local unwrapped = safe_call(function()
            return value:get()
        end)
        if unwrapped ~= nil then
            return value_to_string(unwrapped)
        end
    end

    if kind == "FName" or kind == "FString" or kind == "FText" then
        local converted = safe_call(function()
            return value:ToString()
        end)
        if converted then
            return converted
        end
    end

    if value.GetFullName then
        local full_name = safe_call(function()
            return value:GetFullName()
        end)
        if full_name then
            return full_name
        end
    end

    return tostring(value)
end

local function find_or_add_fname(name)
    return UEHelpers.FindOrAddFName(name)
end

local function is_test_class_name(value)
    return value_to_string(value) == target_row_name
end

local function patch_test_class_row(row_struct)
    if not row_struct or not row_struct.IsValid or not row_struct:IsValid() then
        return false
    end

    row_struct.Name = FText(test_class_name)
    row_struct.passiveName = FText("Runtime Prototype")
    row_struct.PassiveDescription = FText("Uses Guardian gameplay data while proving out a hidden playable-class slot.")
    row_struct.StatDescription = FText("This sample hijacks the hidden Magus row and exposes it as a test class.")
    row_struct.UnlockDescription = FText("Unlocked by the TestPlayableClassMod sample.")
    row_struct.bIsActive = true
    row_struct.bUnlockedInLG = true
    return true
end

local function log_name_array(label, name_array)
    local kind = value_type(name_array)
    if not name_array then
        log(string.format("%s is nil", label))
        return
    end

    if (kind == "RemoteUnrealParam" or kind == "LocalUnrealParam") and name_array.get then
        name_array = safe_call(function()
            return name_array:get()
        end)
        kind = value_type(name_array)
    end

    local names = {}
    if kind == "TArray" then
        local count = safe_call(function()
            return name_array:GetArrayNum()
        end, 0)

        for index = 1, count, 1 do
            names[#names + 1] = value_to_string(name_array[index])
        end
    elseif kind == "table" then
        for _, value in ipairs(name_array) do
            names[#names + 1] = value_to_string(value)
        end
    else
        log(string.format("%s is not a supported collection (got %s)", label, kind))
        return
    end

    log(string.format("%s [%d]: %s", label, #names, table.concat(names, ", ")))
end

local function register_hook_once(function_name, callback, post_callback)
    if state.hook_ids[function_name] then
        return true
    end

    local ok, pre_id, post_id = pcall(function()
        return RegisterHook(function_name, callback, post_callback)
    end)
    if not ok then
        state.hook_failures[function_name] = (state.hook_failures[function_name] or 0) + 1
        if state.hook_failures[function_name] == 1 then
            log(string.format("Failed to hook %s: %s", function_name, tostring(pre_id)))
        end
        return false
    end

    state.hook_ids[function_name] = {
        pre = pre_id,
        post = post_id,
    }
    state.hook_failures[function_name] = nil
    log(string.format("Hooked %s", function_name))
    return true
end

local function register_native_hooks()
    register_hook_once(
        load_player_class_row_fn,
        function(_, _, row_name_param)
            local row_name = row_name_param and row_name_param.get and row_name_param:get() or nil
            if is_test_class_name(row_name) then
                row_name_param:set(find_or_add_fname(base_class_name))
                log(string.format("Aliased %s lookup to %s", target_row_name, base_class_name))
            end
        end,
        function(_, original_success, _, _, out_row_param)
            local row_struct = out_row_param and out_row_param.get and out_row_param:get() or nil
            if patch_test_class_row(row_struct) then
                log(string.format("Patched %s row into '%s'", target_row_name, test_class_name))
                return true
            end
            return original_success
        end
    )

end

local function register_blueprint_hooks()
    local unlock_hook_registered = register_hook_once(
        is_unlocked_fn,
        function(_, original_return_value, class_name_param)
            local requested_name = class_name_param and class_name_param.get and class_name_param:get() or nil
            if is_test_class_name(requested_name) then
                log(string.format("Forced %s unlock state to true", target_row_name))
                return true
            end
            return original_return_value
        end
    )

    local amount_hook_registered = register_hook_once(
        unlocked_amount_fn,
        function(_, original_return_value)
            if type(original_return_value) == "number" then
                return original_return_value + 1
            end

            if (value_type(original_return_value) == "RemoteUnrealParam" or value_type(original_return_value) == "LocalUnrealParam") and original_return_value.get then
                local unwrapped = safe_call(function()
                    return original_return_value:get()
                end)
                if type(unwrapped) == "number" then
                    return unwrapped + 1
                end
            end
            return original_return_value
        end
    )

    state.bp_hooks_registered = unlock_hook_registered and amount_hook_registered
end

local function start_blueprint_hook_retry_loop()
    if state.bp_hooks_registered or state.bp_retry_started then
        return
    end

    state.bp_retry_started = true
    LoopAsync(2000, function()
        if state.bp_hooks_registered then
            return true
        end

        register_blueprint_hooks()
        if state.bp_hooks_registered then
            log("Blueprint hooks became available after retry")
            return true
        end

        return false
    end)
end

local function get_rq_library()
    return safe_call(function()
        return StaticFindObject("/Script/RoboQuest.Default__RQBlueprintLibrary")
    end)
end

local function resolve_game_instance()
    if state.game_instance and state.game_instance:IsValid() then
        return state.game_instance
    end

    for _, class_name in ipairs({
        "BP_AGameInstance_C",
        "GameInstance",
    }) do
        local found = safe_call(function()
            return FindFirstOf(class_name)
        end)
        if found and found:IsValid() then
            state.game_instance = found
            log(string.format("Recovered existing GameInstance %s", value_to_string(found)))
            return found
        end
    end

    return nil
end

local function run_smoke_test()
    if state.smoke_test_done then
        return
    end

    local game_instance = resolve_game_instance()
    if not game_instance or not game_instance:IsValid() then
        log("Smoke test waiting for a valid GameInstance")
        return
    end

    local rq_library = get_rq_library()
    if not rq_library or not rq_library:IsValid() then
        log("Skipping smoke test because RQBlueprintLibrary is not available")
        return
    end

    log("Running injected class smoke test")

    local active_names = safe_call(function()
        return rq_library:SyncLoadAllActivePlayerClassRowNames(game_instance)
    end)
    if active_names then
        log_name_array("Active class names", active_names)
    else
        log("Failed to read active class names during smoke test")
    end

    if state.bp_hooks_registered then
        local is_unlocked = safe_call(function()
            return game_instance:IsPlayerClassUnlocked(find_or_add_fname(target_row_name))
        end)
        local unlocked_amount = safe_call(function()
            return game_instance:GetPlayerClassUnlockedAmount()
        end)
        log(string.format("Blueprint unlock smoke test: unlocked=%s, unlocked_count=%s", tostring(is_unlocked), tostring(unlocked_amount)))
    else
        log("Blueprint unlock smoke test skipped because BP hooks were not registered")
    end

    state.smoke_test_done = active_names ~= nil
end

RegisterConsoleCommandGlobalHandler("rq_test_class_status", function()
    log(string.format("BP hooks registered=%s", tostring(state.bp_hooks_registered)))
    if state.game_instance and state.game_instance:IsValid() then
        log(string.format("Tracked GameInstance=%s", value_to_string(state.game_instance)))
    else
        log("Tracked GameInstance=nil")
    end
    run_smoke_test()
    return true
end)

NotifyOnNewObject("/Script/Engine.GameInstance", function(new_object)
    state.game_instance = new_object
    log(string.format("Tracked GameInstance %s", value_to_string(new_object)))
end)

register_native_hooks()
register_blueprint_hooks()
start_blueprint_hook_retry_loop()

log(string.format("Loaded. Exposing hidden row '%s' as '%s' backed by '%s'.", target_row_name, test_class_name, base_class_name))
