-- Naxxramas Classic Battlegrounds - WotLK 3.3.5a (Lua 5.1)
-- Optional cosmetic companion to Naxxramas Core's SERVER-SIDE queue guard.
-- It does not secure queues or replace the PvP window.\n-- Hides the remote Battlegrounds TAB (PVPParentFrameTab2), not join controls.
-- Modern Individual Progression grants hidden quest 66013 at WotLK entry.
-- 66014-66018 represent later WotLK progression milestones.

local ADDON = "NaxxramasClassicBattlegrounds"
local WOTLK_ENTRY_QUEST = 66013
local LAST_PROGRESS_QUEST = 66018
local QUERY_INTERVAL = 75  -- 3.3.5 throttles QueryQuestsCompleted (~60s)
local elapsed = 0
local lastQuery = -QUERY_INTERVAL
local progressKnown = false
local hasWotlk = false
local hooked = false

local function Log(message)
    if DEFAULT_CHAT_FRAME then
        DEFAULT_CHAT_FRAME:AddMessage("|cffffd200Naxxramas Classic BG:|r " .. message)
    end
end

local function Enabled()
    return NaxxramasClassicBGQueueSettings
       and NaxxramasClassicBGQueueSettings.enabled ~= false
end

local function OpenedFromBattlemaster()
    -- Blizzard uses this mode for NPC_PVPQUEUE_ANYWHERE; do not hide the
    -- queue controls at an NPC, even during Vanilla or TBC.
    return PVPFrame_IsJustBG and PVPFrame_IsJustBG()
end

-- The requested Classic appearance is to hide the Battlegrounds TAB next
-- to PvP, not the Join Battle buttons or the entire Battleground window.
-- The Battlemaster's own NPC window uses justBG mode and remains untouched.
local function UpdateControls()
    if not PVPParentFrame or not PVPParentFrameTab1
       or not PVPParentFrameTab2 then
        return
    end

    if OpenedFromBattlemaster() then
        return -- Blizzard intentionally hides both tabs in the NPC window.
    end

    local hideRemoteTab = Enabled() and (not progressKnown or not hasWotlk)

    if hideRemoteTab then
        -- A previous visit to the Battleground tab can leave that panel
        -- selected. Switch back to PvP before removing its tab.
        if PVPParentFrame:IsShown() and PVPBattlegroundFrame
           and PVPBattlegroundFrame:IsShown() then
            PVPParentFrameTab1:Click()
        end

        PVPParentFrameTab2:Hide()
    else
        -- When Wrath progression unlocks (or the addon is turned off),
        -- restore the tab only if Blizzard reports an available BG.
        local available = false
        if GetNumBattlegroundTypes and GetBattlegroundInfo then
            for i = 1, GetNumBattlegroundTypes() do
                local _, canEnter = GetBattlegroundInfo(i)
                if canEnter then
                    available = true
                    break
                end
            end
        end

        if available then
            PVPParentFrameTab2:Show()
        else
            PVPParentFrameTab2:Hide()
        end
    end
end

local function InstallHooks()
    if hooked or not PVPParentFrame or not PVPParentFrameTab1
       or not PVPParentFrameTab2 or not PVPBattlegroundFrame
       or not PVPFrame_SetJustBG
       or not PVPBattleground_UpdateBattlegrounds then
        return
    end

    hooked = true

    -- Blizzard can reshow Tab2 as the BG list/progression changes.
    -- These safe hooks run after its normal UI updates.
    hooksecurefunc("PVPFrame_SetJustBG", UpdateControls)
    hooksecurefunc("PVPBattleground_UpdateBattlegrounds", UpdateControls)
    if PVPBattlegroundFrame_UpdateVisible then
        hooksecurefunc("PVPBattlegroundFrame_UpdateVisible", UpdateControls)
    end
    PVPParentFrame:HookScript("OnShow", UpdateControls)
    PVPBattlegroundFrame:HookScript("OnShow", UpdateControls)
    UpdateControls()
end

local function QueryProgression()
    if type(QueryQuestsCompleted) ~= "function"
       or type(GetQuestsCompleted) ~= "function" then
        Log("The client does not support the completed-quest query API.")
        return
    end
    local now = GetTime()
    if now - lastQuery < 65 then
        return
    end
    lastQuery = now
    QueryQuestsCompleted()
end

local function ReceiveProgression()
    local quests = GetQuestsCompleted and GetQuestsCompleted()
    if type(quests) ~= "table" then
        return
    end

    local wasKnown, wasWotlk = progressKnown, hasWotlk
    progressKnown = true
    hasWotlk = false

    for questId = WOTLK_ENTRY_QUEST, LAST_PROGRESS_QUEST do
        if quests[questId] then
            hasWotlk = true
            break
        end
    end

    UpdateControls()
    if hasWotlk and (not wasKnown or not wasWotlk) then
        Log("Wrath progression detected: remote Battleground buttons unlocked.")
    end
end

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("PLAYER_ENTERING_WORLD")
events:RegisterEvent("QUEST_QUERY_COMPLETE")

events:SetScript("OnEvent", function(self, event, arg1)
    if event == "ADDON_LOADED" and arg1 == ADDON then
        if not NaxxramasClassicBGQueueSettings then
            NaxxramasClassicBGQueueSettings = { enabled = true }
        end
    elseif event == "PLAYER_LOGIN" then
        InstallHooks()
        UpdateControls()
        QueryProgression()
    elseif event == "PLAYER_ENTERING_WORLD" then
        InstallHooks()
        UpdateControls()
        QueryProgression()
    elseif event == "QUEST_QUERY_COMPLETE" then
        ReceiveProgression()
    end
end)

events:SetScript("OnUpdate", function(self, delta)
    elapsed = elapsed + delta
    if elapsed < 2 then return end
    elapsed = 0

    if not hooked then InstallHooks() end
    if Enabled() and GetTime() - lastQuery >= QUERY_INTERVAL then
        QueryProgression()
    end
end)

SLASH_NAXXCLASSICBG1 = "/ncbg"
SlashCmdList["NAXXCLASSICBG"] = function(message)
    message = string.lower((message or ""):match("^%s*(.-)%s*$"))
    if not NaxxramasClassicBGQueueSettings then
        NaxxramasClassicBGQueueSettings = { enabled = true }
    end

    if message == "on" then
        NaxxramasClassicBGQueueSettings.enabled = true
        UpdateControls()
        QueryProgression()
        Log("Client-only button hiding enabled.")
    elseif message == "off" then
        NaxxramasClassicBGQueueSettings.enabled = false
        UpdateControls()
        Log("Client-only button hiding disabled. Server restrictions remain active.")
    elseif message == "refresh" then
        QueryProgression()
        Log("Progression query requested (the 3.3.5 client throttles requests).")
    elseif message == "status" then
        local stage = not progressKnown and "awaiting server quest data"
            or (hasWotlk and "WotLK or later" or "Vanilla / TBC")
        Log("Display: " .. (Enabled() and "enabled" or "disabled") ..
            "; progression: " .. stage ..
            "; server is authoritative.")
    else
        Log("Commands: /ncbg on, /ncbg off, /ncbg refresh, /ncbg status")
    end
end
