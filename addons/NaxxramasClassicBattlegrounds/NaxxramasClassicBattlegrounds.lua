-- Naxxramas Classic Battlegrounds - WotLK 3.3.5a (Lua 5.1)
-- Optional cosmetic companion to Naxxramas Core's SERVER-SIDE queue guard.
-- It does not secure queues or replace the PvP window.
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
local hint

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

local function UpdateControls()
    if not PVPBattlegroundFrame
       or not PVPBattlegroundFrameJoinButton
       or not PVPBattlegroundFrameGroupJoinButton then
        return
    end

    local hideRemote = Enabled() and (not progressKnown or not hasWotlk)
        and not OpenedFromBattlemaster()

    if hideRemote then
        PVPBattlegroundFrameJoinButton:Hide()
        PVPBattlegroundFrameGroupJoinButton:Hide()
    else
        PVPBattlegroundFrameJoinButton:Show()
        PVPBattlegroundFrameGroupJoinButton:Show()
    end

    if hint then
        if hideRemote then
            if progressKnown then
                hint:SetText("Visit a Battlemaster to join a Battleground.\nRemote queues unlock in Wrath of the Lich King.")
            else
                hint:SetText("Checking Individual Progression...\nVisit a Battlemaster to queue.")
            end
            hint:Show()
        else
            hint:Hide()
        end
    end
end

local function InstallHooks()
    if hooked or not PVPBattlegroundFrame
       or not PVPBattlegroundFrameJoinButton
       or not PVPBattlegroundFrameGroupJoinButton
       or not PVPFrame_SetJustBG
       or not PVPBattleground_UpdateBattlegrounds then
        return
    end

    hooked = true
    hint = PVPBattlegroundFrame:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
    hint:SetWidth(360)
    hint:SetJustifyH("CENTER")
    hint:SetPoint("BOTTOM", PVPBattlegroundFrame, "BOTTOM", 0, 37)
    hint:Hide()

    -- These hooks run AFTER Blizzard updates its own buttons.
    -- No global UI functions or Battleground join APIs are overwritten.
    hooksecurefunc("PVPFrame_SetJustBG", UpdateControls)
    hooksecurefunc("PVPBattleground_UpdateBattlegrounds", UpdateControls)
    if PVPBattlegroundFrame_UpdateVisible then
        hooksecurefunc("PVPBattlegroundFrame_UpdateVisible", UpdateControls)
    end
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
