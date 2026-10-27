/*
 * Naxxramas Core - Atiesh "Portal to Karazhan" Vanilla arrival (F13).
 *
 * Default OFF. During a character's Vanilla stage, using the Atiesh portal
 * (GO 181146, type 22, spell 28147) teleports the user to the outside of
 * Karazhan's main gate (live areatrigger_teleport 4436) instead of casting
 * 28147 into map 532. Every other GO, era, GM and disabled case keeps the
 * stock path. A bot's direct 28147 cast (Playerbots "teleport" command)
 * never reaches this hook. See docs/ATIESH-KARAZHAN-PORTAL.md.
 */
#include "Chat.h"
#include "Config.h"
#include "GameObject.h"
#include "Group.h"
#include "Log.h"
#include "MapMgr.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "ScriptMgr.h"

#include "AtieshPortalPolicy.h"
#include "IndividualProgressionEra.h"

namespace NaxxramasAtieshPortal
{
    using namespace NaxxramasAtieshPortalPolicy;

    // Only called from the config hook below, on the world thread.
    bool ReadEnabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled", false);
    }

    // Written only by the startup config load, which runs before MapMgr
    // starts any map worker, and never again. The gossip hook runs on a map
    // thread, so it reads only this snapshot and never calls ConfigMgr
    // (same fix as #133 / #144). Until it is written, the feature is OFF.
    bool StartupEnabled = false;

    bool Enabled() { return StartupEnabled; }

    // NAXXRAMAS_IP_ERA_HAS_IP_HEADER comes from IndividualProgressionEra.h.
    // Without IP's exported header the era helper's fallback would read
    // ConfigMgr on this map thread, so the portal stays stock instead.
    constexpr bool IP_HEADER_AVAILABLE = NAXXRAMAS_IP_ERA_HAS_IP_HEADER != 0;

    Facts Gather(Player* player, GameObject* go, AreaTriggerTeleport const*& row)
    {
        Facts f;
        f.Entry = go->GetEntry();

        GameObjectTemplate const* info = go->GetGOInfo();
        if (!info)
            return f;

        f.GoType = info->type;
        f.TemplateSpell = info->type == GAMEOBJECT_TYPE_SPELLCASTER
            ? info->spellcaster.spellId : 0;

        // Stop here for every other object: only the portal pays for the
        // config, era and table lookups below.
        if (!IsAtieshPortal(f))
            return f;

        f.Enabled = Enabled();
        f.GameMaster = player->IsGameMaster();
        // Only ask IP when the feature is on and its header is available;
        // otherwise VanillaStage stays false and Decide keeps the stock path.
        f.VanillaStage = f.Enabled && IP_HEADER_AVAILABLE &&
            NaxxramasIpEra::IsVanillaProgression(player);

        f.PartyOnly = info->spellcaster.partyOnly != 0;
        ObjectGuid const owner = go->GetOwnerGUID();
        f.HasOwner = !owner.IsEmpty();
        f.ClickerIsOwner = f.HasOwner && player->GetGUID() == owner;
        Group* group = player->GetGroup();
        f.ClickerGroupHasOwner = f.HasOwner && group && group->IsMember(owner);

        f.BeingTeleported = player->IsBeingTeleported();

        row = sObjectMgr->GetAreaTriggerTeleport(AREATRIGGER_KARAZHAN_MAIN_EXIT);
        f.ExitRowExists = row != nullptr;
        f.ExitRowMap = row ? row->target_mapId : 0;
        f.ExitRowCoordValid = row && MapMgr::IsValidMapCoord(row->target_mapId,
            row->target_X, row->target_Y, row->target_Z, row->target_Orientation);
        return f;
    }

    void Tell(Player* player)
    {
        if (WorldSession* session = player->GetSession())
            ChatHandler(session).SendSysMessage(
                "The portal flickers but cannot open outside Karazhan.");
    }
}

// Takes the settings snapshot on the world thread: at startup before any map
// worker exists, and for ".reload config" while no map worker runs. A reload
// keeps the startup value (restart-only) and warns if it changed.
class NaxxramasAtieshPortalConfig : public WorldScript
{
public:
    NaxxramasAtieshPortalConfig()
        : WorldScript("NaxxramasAtieshPortalConfig", { WORLDHOOK_ON_AFTER_CONFIG_LOAD }) { }

    void OnAfterConfigLoad(bool reload) override
    {
        using namespace NaxxramasAtieshPortal;
        bool const loaded = ReadEnabled();
        if (!reload)
        {
            StartupEnabled = loaded;
            if (loaded && !IP_HEADER_AVAILABLE)
                LOG_WARN("module",
                    "AtieshPortal: VanillaOutdoorArrival.Enabled = 1, but Individual Progression's "
                    "header is not available to this module; the portal stays stock.");
            return;
        }

        if (loaded != StartupEnabled)
            LOG_WARN("module",
                "AtieshPortal: settings changed by .reload config are ignored until "
                "Worldserver restarts; still VanillaOutdoorArrival.Enabled={}.", StartupEnabled);
    }
};

class NaxxramasAtieshPortalScript : public AllGameObjectScript
{
public:
    NaxxramasAtieshPortalScript()
        : AllGameObjectScript("NaxxramasAtieshPortal") { }

    // Return false = stock path unchanged. Return true = handled here.
    bool CanGameObjectGossipHello(Player* player, GameObject* go) override
    {
        using namespace NaxxramasAtieshPortal;

        if (!player || !go || go->GetEntry() != GO_ATIESH_PORTAL_TO_KARAZHAN)
            return false;

        AreaTriggerTeleport const* row = nullptr;
        switch (Decide(Gather(player, go, row)))
        {
            case Action::Stock:
                return false;
            case Action::Ignore:
                return true;
            case Action::FailClosed:
                Tell(player);
                return true;
            case Action::Teleport:
                break;
        }

        // The portal may be owned by its clicker. TeleportTo can remove that
        // player's old-world objects (or interrupt a summoning aura), so an
        // owned GO cannot safely be dereferenced after the teleport succeeds.
        // For other-owner and unowned GOs the clicker's removal does not own
        // their lifecycle; preserve their native successful-use accounting.
        bool const clickerOwnsPortal = go->GetOwnerGUID() == player->GetGUID();

        // Mount parity with the native path (GameObject.cpp L1524-1526).
        if (!go->GetGOInfo()->IsUsableMounted())
            player->RemoveAurasByType(SPELL_AURA_MOUNTED);

        // Fail closed: a refused request never falls back to the inside cast.
        if (player->TeleportTo(row->target_mapId, row->target_X, row->target_Y,
                row->target_Z, row->target_Orientation))
        {
            // Owner portals can be deleted by the successful move itself;
            // their use count no longer has a live owner-side purpose.
            if (!clickerOwnsPortal)
                go->AddUse();
        }
        else
            Tell(player);

        return true;
    }
};

void AddAtieshKarazhanPortalScripts()
{
    new NaxxramasAtieshPortalConfig();
    new NaxxramasAtieshPortalScript();
}
