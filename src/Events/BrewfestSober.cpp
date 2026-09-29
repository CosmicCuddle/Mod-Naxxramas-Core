/*
 * Naxxramas Core
 *
 * Brewfest Accessibility
 *
 * Adds an accessibility option to Goldark Snipehunter and
 * Glodrak Huntsniper allowing players to immediately remove
 * drunkenness effects.
 */

#include "Chat.h"
#include "Creature.h"
#include "GossipDef.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptedGossip.h"
#include "SpellAuraDefines.h"

namespace
{
    constexpr uint32 NPC_GOLDARK_SNIPEHUNTER = 23486;
    constexpr uint32 NPC_GLODRAK_HUNTSNIPER  = 24657;

    bool IsBrewfestSoberNpc(Creature const* creature)
    {
        if (!creature)
            return false;

        return creature->GetEntry() == NPC_GOLDARK_SNIPEHUNTER ||
               creature->GetEntry() == NPC_GLODRAK_HUNTSNIPER;
    }

    void SoberPlayer(Player* player)
    {
        if (!player)
            return;

        // Remove normal alcohol drunkenness.
        player->SetDrunkValue(0);

        // Remove simulated drunkenness such as Synthebrew Goggles.
        player->RemoveAurasByType(SPELL_AURA_MOD_FAKE_INEBRIATE);

        if (player->GetSession())
        {
            ChatHandler(player->GetSession()).SendSysMessage(
                "Your drunkenness effects have been removed.");
        }
    }
}

class NaxxramasCoreBrewfestSoberGossip : public AllCreatureScript
{
public:
    NaxxramasCoreBrewfestSoberGossip()
        : AllCreatureScript("NaxxramasCoreBrewfestSoberGossip")
    {
    }

    bool CanCreatureGossipSelect(
        Player* player,
        Creature* creature,
        uint32 /*sender*/,
        uint32 action) override
    {
        if (!IsBrewfestSoberNpc(creature))
            return false;

        /*
         * Our custom gossip option uses GOSSIP_OPTION_SPIRITGUIDE
         * as an internal identifier so it can be distinguished
         * from the NPC's normal Brewfest gossip options.
         */
        if (action != GOSSIP_OPTION_SPIRITGUIDE)
            return false;

        SoberPlayer(player);
        CloseGossipMenuFor(player);

        return true;
    }
};

void AddBrewfestSoberGossipScripts()
{
    new NaxxramasCoreBrewfestSoberGossip();
}
