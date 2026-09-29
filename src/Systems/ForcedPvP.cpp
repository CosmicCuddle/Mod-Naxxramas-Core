/*
 * Naxxramas Core
 *
 * Forced PvP Zones
 *
 * Forces normal faction PvP while players are inside selected zones.
 *
 * Current supported zones:
 * - Silithus
 * - Eastern Plaguelands
 *
 * The player's original manual PvP preference is remembered when entering
 * a forced PvP zone and restored when leaving.
 */

#include "AreaDefines.h"
#include "Chat.h"
#include "Config.h"
#include "Player.h"
#include "ScriptMgr.h"

#if __has_include("Playerbots.h")
#include "Playerbots.h"
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1
#else
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 0
#endif

#include <unordered_map>

namespace
{
    bool ForcedPvPEnabled = true;
    bool ForcedPvPSilithus = true;
    bool ForcedPvPEasternPlaguelands = true;
    bool ForcedPvPIncludeBots = true;
    bool ForcedPvPNotify = true;

    struct ForcedPvPState
    {
        bool WasManuallyPvP = false;
    };

    std::unordered_map<ObjectGuid::LowType, ForcedPvPState> ForcedPvPStates;

    bool IsPlayerBot(Player* player)
    {
#if NAXXRAMAS_CORE_HAS_PLAYERBOTS
        return GET_PLAYERBOT_AI(player) != nullptr;
#else
        return false;
#endif
    }

    bool IsConfiguredForcedPvPZone(uint32 zoneId)
    {
        if (!ForcedPvPEnabled)
            return false;

        if (zoneId == AREA_SILITHUS)
            return ForcedPvPSilithus;

        if (zoneId == AREA_EASTERN_PLAGUELANDS)
            return ForcedPvPEasternPlaguelands;

        return false;
    }

    bool ShouldForcePvP(Player* player)
    {
        if (!player)
            return false;

        // Do not force GM characters into PvP.
        if (player->IsGameMaster())
            return false;

        if (!ForcedPvPIncludeBots && IsPlayerBot(player))
            return false;

        return IsConfiguredForcedPvPZone(player->GetZoneId());
    }

    char const* GetForcedPvPZoneName(uint32 zoneId)
    {
        switch (zoneId)
        {
            case AREA_SILITHUS:
                return "Silithus";

            case AREA_EASTERN_PLAGUELANDS:
                return "Eastern Plaguelands";

            default:
                return "This zone";
        }
    }

    void EnterForcedPvP(Player* player)
    {
        if (!player || !ShouldForcePvP(player))
            return;

        ObjectGuid::LowType guid = player->GetGUID().GetCounter();

        // Only save the original PvP preference once when entering.
        auto [itr, inserted] = ForcedPvPStates.try_emplace(
            guid,
            ForcedPvPState
            {
                player->HasPlayerFlag(PLAYER_FLAGS_IN_PVP)
            });

        // Make the manual PvP flag appear enabled while inside the zone.
        if (!player->HasPlayerFlag(PLAYER_FLAGS_IN_PVP))
            player->SetPlayerFlag(PLAYER_FLAGS_IN_PVP);

        // Cancel any pending PvP-off timer and force PvP immediately.
        if (!player->IsPvP() || player->pvpInfo.EndTimer != 0)
            player->UpdatePvP(true, true);

        // Only notify when the forced state is first entered.
        if (inserted && ForcedPvPNotify && player->GetSession())
        {
            ChatHandler(player->GetSession()).PSendSysMessage(
                "{} is a PvP zone. PvP will remain enabled until you leave the zone.",
                GetForcedPvPZoneName(player->GetZoneId()));
        }
    }

    void LeaveForcedPvP(Player* player, bool loggingOut = false)
    {
        if (!player)
            return;

        ObjectGuid::LowType guid = player->GetGUID().GetCounter();

        auto itr = ForcedPvPStates.find(guid);

        if (itr == ForcedPvPStates.end())
            return;

        bool wasManuallyPvP = itr->second.WasManuallyPvP;

        ForcedPvPStates.erase(itr);

        // If PvP was already manually enabled before entering,
        // leave it enabled when leaving.
        if (wasManuallyPvP)
            return;

        // Restore the player's original manual PvP preference.
        player->RemovePlayerFlag(PLAYER_FLAGS_IN_PVP);

        if (loggingOut)
        {
            // Do not save the forced PvP state as the player's normal
            // preference when logging out inside one of these zones.
            player->pvpInfo.EndTimer = 0;
            player->SetPvP(false);
            return;
        }

        // Start AzerothCore's normal PvP-off cooldown instead of making
        // the player instantly immune when crossing the zone border.
        if (player->IsPvP())
            player->UpdatePvP(true, false);
    }

    void UpdateForcedPvPState(Player* player)
    {
        if (!player)
            return;

        if (ShouldForcePvP(player))
            EnterForcedPvP(player);
        else
            LeaveForcedPvP(player);
    }
}

class NaxxramasCoreForcedPvPConfig : public WorldScript
{
public:
    NaxxramasCoreForcedPvPConfig()
        : WorldScript(
            "NaxxramasCoreForcedPvPConfig",
            {
                WORLDHOOK_ON_BEFORE_CONFIG_LOAD
            })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        ForcedPvPEnabled =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.ForcedPvP.Enabled",
                true);

        ForcedPvPSilithus =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.ForcedPvP.Silithus",
                true);

        ForcedPvPEasternPlaguelands =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.ForcedPvP.EasternPlaguelands",
                true);

        ForcedPvPIncludeBots =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.ForcedPvP.IncludeBots",
                true);

        ForcedPvPNotify =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.ForcedPvP.Notify",
                true);
    }
};

class NaxxramasCoreForcedPvPPlayer : public PlayerScript
{
public:
    NaxxramasCoreForcedPvPPlayer()
        : PlayerScript(
            "NaxxramasCoreForcedPvPPlayer",
            {
                PLAYERHOOK_ON_LOGIN,
                PLAYERHOOK_ON_BEFORE_LOGOUT,
                PLAYERHOOK_ON_UPDATE_ZONE,
                PLAYERHOOK_ON_AFTER_UPDATE,
                PLAYERHOOK_ON_PLAYER_PVP_FLAG_CHANGE
            })
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        UpdateForcedPvPState(player);
    }

    void OnPlayerBeforeLogout(Player* player) override
    {
        LeaveForcedPvP(player, true);
    }

    void OnPlayerUpdateZone(
        Player* player,
        uint32 /*newZone*/,
        uint32 /*newArea*/) override
    {
        UpdateForcedPvPState(player);
    }

    void OnPlayerAfterUpdate(
        Player* player,
        uint32 /*diff*/) override
    {
        // This also allows config changes to take effect for players
        // who are already standing inside one of the configured zones.
        UpdateForcedPvPState(player);
    }

    void OnPlayerPVPFlagChange(
        Player* player,
        bool /*state*/) override
    {
        if (!player || !ShouldForcePvP(player))
            return;

        // If the player attempts to disable PvP while inside a forced
        // PvP zone, immediately restore the forced state.
        if (!player->HasPlayerFlag(PLAYER_FLAGS_IN_PVP))
            player->SetPlayerFlag(PLAYER_FLAGS_IN_PVP);

        player->pvpInfo.EndTimer = 0;
        player->SetPvP(true);
    }
};

void AddForcedPvPScripts()
{
    new NaxxramasCoreForcedPvPConfig();
    new NaxxramasCoreForcedPvPPlayer();
}
