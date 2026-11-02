/*
 * P4 H1/H2 shared read-only single-copy quest turn predicate.
 * The real pickup wrapper retains packet source/range checks and error.
 */
#ifndef NAXXRAMAS_QUEST_LOOT_TURN_GUARD_H
#define NAXXRAMAS_QUEST_LOOT_TURN_GUARD_H
#include <cstdint>
class Player;
class Creature;
namespace NaxxramasQuestLootProtection
{
    bool WouldDenyQuestSlotForViewer(Player* player, Creature* creature, std::uint8_t requestedSlot);
}
#endif
