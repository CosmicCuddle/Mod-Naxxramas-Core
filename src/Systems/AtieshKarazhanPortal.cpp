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
#include "MapMgr.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "ScriptMgr.h"

#include "AtieshPortalPolicy.h"
#include "IndividualProgressionEra.h"

namespace NaxxramasAtieshPortal
{
    using namespace NaxxramasAtieshPortalPolicy;

    bool Enabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.Atiesh.VanillaOutdoorArrival.Enabled", false);
    }

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
        f.VanillaStage = NaxxramasIpEra::IsVanillaProgression(player);

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

        // Mount parity with the native path (GameObject.cpp L1524-1526).
        if (!go->GetGOInfo()->IsUsableMounted())
            player->RemoveAurasByType(SPELL_AURA_MOUNTED);

        // Fail closed: a refused request never falls back to the inside cast.
        if (player->TeleportTo(row->target_mapId, row->target_X, row->target_Y,
                row->target_Z, row->target_Orientation))
            go->AddUse();
        else
            Tell(player);

        return true;
    }
};

void AddAtieshKarazhanPortalScripts()
{
    new NaxxramasAtieshPortalScript();
}
