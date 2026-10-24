/*
 * Naxxramas Core - Scarlet Monastery Cathedral/Armory exits (F12).
 *
 * Default OFF. Handles only the exit area triggers 604 (Cathedral) and
 * 606 (Armory) from CanPacketReceive, before the native area-trigger
 * handler. Every case the native handler treats specially is handed back
 * to it unchanged. Once an exit is eligible, the native handler never runs
 * for it (fail closed). See docs/SCARLET-MONASTERY-EXITS.md.
 */
#include "Battleground.h"
#include "Chat.h"
#include "Config.h"
#include "Group.h"
#include "Map.h"
#include "MapMgr.h"
#include "ObjectMgr.h"
#include "Opcodes.h"
#include "OutdoorPvP.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/ServerScript.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <iterator>

#include "ScarletExitPolicy.h"

namespace NaxxramasScarletExits
{
    using namespace NaxxramasScarletExitPolicy;

    bool Enabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.ScarletExits.Enabled", false);
    }

    bool UseDoorTargets()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.ScarletExits.UseVanillaDoorTargets", true);
    }

    bool RouteDungeonFinderExits()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.ScarletExits.RouteDungeonFinderExits", true);
    }

    TriggerShape ShapeOf(uint32 triggerId)
    {
        TriggerShape shape;
        if (AreaTrigger const* at = sObjectMgr->GetAreaTrigger(triggerId))
        {
            shape.Present = true;
            shape.Map = at->map;
            shape.X = at->x;
            shape.Y = at->y;
            shape.Z = at->z;
            shape.Radius = at->radius;
            shape.Length = at->length;
            shape.Width = at->width;
            shape.Height = at->height;
            shape.Orientation = at->orientation;
        }
        return shape;
    }

    bool DoorTargetIsSafe(DoorTarget const& door)
    {
        Point const& p = door.Where;
        if (!MapMgr::IsValidMapCoord(EXIT_MAP, p.X, p.Y, p.Z, p.O))
            return false;

        TriggerShape const own = ShapeOf(door.EntranceTrigger);
        TriggerShape others[std::size(SM_ENTRANCES)];
        std::size_t count = 0;
        for (uint32 entrance : SM_ENTRANCES)
            if (entrance != door.EntranceTrigger)
                others[count++] = ShapeOf(entrance);

        return TargetIsSafe(p, own, others, count);
    }

    // Collects the live facts in the same order the native handler checks
    // them (MiscHandler.cpp HandleAreaTriggerOpcode).
    Facts Gather(Player* player, uint32 triggerId, DoorTarget const& door,
        AreaTriggerTeleport const*& row)
    {
        Facts f;
        f.Enabled = true;
        f.HandledTrigger = true;
        f.InFlight = player->IsInFlight();
        f.DebugAreaTriggers = player->isDebugAreaTriggers;

        AreaTrigger const* at = sObjectMgr->GetAreaTrigger(triggerId);
        f.TriggerKnown = at != nullptr;

        uint32 const teamFaction = player->GetTeamId(true) == TEAM_ALLIANCE
            ? FACTION_MASK_ALLIANCE : FACTION_MASK_HORDE;
        f.Tavern = sObjectMgr->IsTavernAreaTrigger(triggerId, teamFaction);
        f.InRadius = at && player->IsInAreaTriggerRadius(at, 0.f);
        f.BoundScript = sObjectMgr->GetAreaTriggerScriptId(triggerId) != 0;
        f.QuestTrigger = sObjectMgr->GetQuestForAreaTrigger(triggerId) != 0;

        if (Battleground* bg = player->GetBattleground())
            f.BattlegroundActive = bg->GetStatus() == STATUS_IN_PROGRESS;
        f.OutdoorPvP = player->GetOutdoorPvP() != nullptr;

        row = sObjectMgr->GetAreaTriggerTeleport(triggerId);
        f.RowExists = row != nullptr;
        f.RowMap = row ? row->target_mapId : 0;
        f.AlreadyOnExitMap = row && player->GetMapId() == row->target_mapId;
        f.EntryDenied = row && !f.AlreadyOnExitMap &&
            sMapMgr->PlayerCannotEnter(row->target_mapId, player, false) != Map::CAN_ENTER;

        Group* group = player->GetGroup();
        f.DungeonFinderExit = group && group->isLFGGroup() &&
            player->GetMap()->IsDungeon();
        f.RouteDungeonFinderExits = RouteDungeonFinderExits();
        f.UseDoorTargets = UseDoorTargets();
        f.DoorTargetSafe = f.UseDoorTargets && DoorTargetIsSafe(door);
        return f;
    }

    void Tell(Player* player, char const* text)
    {
        if (WorldSession* session = player->GetSession())
            ChatHandler(session).SendSysMessage(text);
    }

    // Returns true when this module handled the exit, so the native
    // handler must not run. Returns false to leave everything to the core.
    bool Handle(Player* player, uint32 triggerId)
    {
        DoorTarget const* door = FindDoorTarget(triggerId);
        if (!door)
            return false;

        AreaTriggerTeleport const* row = nullptr;
        Route const route = Decide(Gather(player, triggerId, *door, row));
        if (route == Route::Stock || !row)
            return false;

        Point const target = route == Route::DoorTarget
            ? door->Where
            : Point{ row->target_X, row->target_Y, row->target_Z, row->target_Orientation };

        // Fail closed: an eligible exit never falls back to the native
        // handler, which could send a Dungeon Finder member to the queue
        // spot or homebind. A refused request leaves the player in place.
        if (!player->TeleportTo(EXIT_MAP, target.X, target.Y, target.Z, target.O,
                TELE_TO_NOT_LEAVE_TRANSPORT))
            Tell(player, "The exit is not available right now.");

        return true;
    }
}

class NaxxramasScarletExitsScript : public ServerScript
{
public:
    NaxxramasScarletExitsScript()
        : ServerScript("NaxxramasScarletExits", { SERVERHOOK_CAN_PACKET_RECEIVE }) { }

    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override
    {
        // Runs for every incoming opcode: leave quickly for anything else.
        if (packet.GetOpcode() != CMSG_AREATRIGGER || packet.size() < 4 ||
            !NaxxramasScarletExits::Enabled() || !session)
            return true;

        Player* player = session->GetPlayer();
        if (!player || !player->IsInWorld())
            return true;

        // Read from a copy so the native handler's cursor is untouched.
        WorldPacket copy(packet);
        copy.rpos(0);
        uint32 triggerId = 0;
        copy >> triggerId;

        return !NaxxramasScarletExits::Handle(player, triggerId);
    }
};

void AddScarletMonasteryExitScripts()
{
    new NaxxramasScarletExitsScript();
}
