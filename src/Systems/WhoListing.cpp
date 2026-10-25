/*
 * Naxxramas Core - F14 `/who` listing by Individual Progression stage
 * (default OFF). See docs/research/F14-WHO-LISTING-S1.md and
 * docs/F14-WHO-LISTING-S2.md.
 *
 * While NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces = 0 the module
 * returns true for every packet and the unmodified core handler answers.
 * When it is 1 and the observer is Vanilla-stage, CMSG_WHO is answered here
 * with a line-for-line mirror of the stock handler that leaves Blood Elf
 * and Draenei rows out of the list and out of both counts.
 *
 * No core, Individual Progression or Playerbots change. No SQL or DBC.
 */
#include "AccountMgr.h"
#include "Config.h"
#include "DBCStores.h"
#include "IndividualProgressionEra.h"
#include "Log.h"
#include "Opcodes.h"
#include "Player.h"
#include "RBAC.h"
#include "ScriptMgr.h"
#include "Util.h"
#include "WhoListCacheMgr.h"
#include "WhoListingPolicy.h"
#include "World.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <string>

namespace
{
    using namespace NaxxramasWhoListing;

    struct WhoListingConfig
    {
        bool hideTbcRaces = false;
        bool gmBypass = true;
    };

    // Only called from the config hook below, on the world thread.
    WhoListingConfig ReadWhoListingConfig()
    {
        WhoListingConfig loaded;
        loaded.hideTbcRaces = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.ExpansionRaceVisibility.HideTbcRaces", false);
        loaded.gmBypass = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.ExpansionRaceVisibility.GMBypass", true);
        return loaded;
    }

    // Written only by the startup config load, before any map worker exists
    // (World::SetInitialWorldSettings), and never again. CMSG_WHO runs on a
    // map thread, which only reads this. Until it is written, the feature is OFF.
    WhoListingConfig StartupWhoListingConfig;

    // Restart-only, like the Golemagg guard (#133): ".reload config" keeps the
    // startup values and warns if they changed.
    class NaxxramasCoreWhoListingConfig final : public WorldScript
    {
    public:
        NaxxramasCoreWhoListingConfig()
            : WorldScript("NaxxramasCoreWhoListingConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD })
        {
        }

        void OnAfterConfigLoad(bool reload) override
        {
            WhoListingConfig const loaded = ReadWhoListingConfig();
            if (!reload)
            {
                StartupWhoListingConfig = loaded;
                return;
            }

            if (loaded.hideTbcRaces != StartupWhoListingConfig.hideTbcRaces ||
                loaded.gmBypass != StartupWhoListingConfig.gmBypass)
                LOG_WARN("module",
                    "WhoListing: settings changed by .reload config are ignored until "
                    "Worldserver restarts; still HideTbcRaces={} GMBypass={}.",
                    StartupWhoListingConfig.hideTbcRaces, StartupWhoListingConfig.gmBypass);
        }
    };

    // Core text helpers, exactly the ones the stock handler calls.
    struct CoreText
    {
        static bool ToWide(std::string const& utf8, std::wstring& wide) { return Utf8toWStr(utf8, wide); }
        static void Lower(std::wstring& wide) { wstrToLower(wide); }
        static bool FitTo(std::string const& utf8, std::wstring const& search) { return Utf8FitTo(utf8, search); }
    };

    // The observer-side values the stock loop reads, taken once per request.
    struct CoreWhoContext
    {
        TeamId team;
        bool canSeeOtherTeam;
        bool canSeeAllSecLevels;
        AccountTypes gmLevelInWhoList;
        ObjectGuid observerGuid;
        bool observerIsPlayerAccount;
        AccountTypes observerSecurity;
        uint32 maxReturn;
        LocaleConstant locale;

        std::string AreaName(uint32 zoneId) const
        {
            if (AreaTableEntry const* areaEntry = sAreaTableStore.LookupEntry(zoneId))
                return areaEntry->area_name[locale];
            return {};
        }
    };

    class NaxxramasCoreWhoListing final : public ServerScript
    {
    public:
        NaxxramasCoreWhoListing()
            : ServerScript("NaxxramasCoreWhoListing", { SERVERHOOK_CAN_PACKET_RECEIVE })
        {
        }

        // For STATUS_LOGGEDIN packets the core calls this inside the session's
        // try block and only when the player is in world (WorldSession.cpp
        // L441-L464). CMSG_WHO is PROCESS_THREADSAFE (Opcodes.cpp L229), so
        // this runs on the observer's map thread, as the stock handler does.
        bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override
        {
            if (packet.GetOpcode() != CMSG_WHO)
                return true;

            WhoListingConfig const& config = StartupWhoListingConfig;
            if (!config.hideTbcRaces || !session)
                return true;                                   // R1: stock

            Player* player = session->GetPlayer();
            if (!player || !player->IsInWorld())
                return true;

            ObserverContext observer;
            observer.hideTbcRaces = config.hideTbcRaces;
            observer.gmBypass = config.gmBypass;
            observer.observerIsVanilla = NaxxramasIpEra::IsVanillaProgression(player);
            observer.observerAboveSecPlayer = session->GetSecurity() > SEC_PLAYER;
            if (!InterceptWho(observer))
                return true;                                   // R2, R3: stock

            // Read from a copy so the packet the core holds is untouched. A
            // short packet throws here, inside the core's try, as it would
            // in the stock handler: no reply either way.
            WorldPacket copy(packet);
            WhoRequest request;
            if (!ReadWhoRequest<CoreText>(copy, request, MAX_LEVEL, STRONG_MAX_LEVEL))
                return false;                                  // stock early return: no reply

            CoreWhoContext ctx{
                player->GetTeamId(),
                session->HasPermission(rbac::RBAC_PERM_TWO_SIDE_WHO_LIST),
                session->HasPermission(rbac::RBAC_PERM_WHO_SEE_ALL_SEC_LEVELS),
                AccountTypes(sWorld->getIntConfig(CONFIG_GM_LEVEL_IN_WHO_LIST)),
                player->GetGUID(),
                AccountMgr::IsPlayerAccount(session->GetSecurity()),
                session->GetSecurity(),
                sWorld->getIntConfig(CONFIG_MAX_WHO_LIST_RETURN),
                session->GetSessionDbcLocale()
            };

            WorldPacket data(SMSG_WHO, 50);
            WriteWhoReply<CoreText>(request, sWhoListCacheMgr->GetWhoList(), ctx, true, data);
            session->SendPacket(&data);
            return false;                                      // answered here; skip the stock handler
        }
    };
}

void AddWhoListingScripts()
{
    new NaxxramasCoreWhoListingConfig();
    new NaxxramasCoreWhoListing();
}
