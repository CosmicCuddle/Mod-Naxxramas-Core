/*
 * Naxxramas Core
 * Class - Warlock - Wrack
 *
 * 18275 - Shadow Mastery Rank 5
 * 90058 - Wrack
 *
 * Warlocks automatically learn Wrack while their active specialization
 * contains Shadow Mastery Rank 5. Wrack is removed again when that
 * requirement is no longer met.
 */

#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"

namespace
{
    constexpr uint32 SPELL_WARLOCK_SHADOW_MASTERY_RANK_5 = 18275;
    constexpr uint32 SPELL_WARLOCK_WRACK = 90058;

    void SyncWrack(Player* player)
    {
        if (!player || player->getClass() != CLASS_WARLOCK)
            return;

        bool shouldKnowWrack =
            player->HasSpell(SPELL_WARLOCK_SHADOW_MASTERY_RANK_5);

        bool knowsWrack =
            player->HasSpell(SPELL_WARLOCK_WRACK);

        if (shouldKnowWrack && !knowsWrack)
        {
            player->learnSpell(
                SPELL_WARLOCK_WRACK,
                false);
            return;
        }

        if (!shouldKnowWrack && knowsWrack)
        {
            player->removeSpell(
                SPELL_WARLOCK_WRACK,
                player->GetActiveSpecMask(),
                false);
        }
    }
}

class NaxxramasCoreWarlockWrack : public PlayerScript
{
public:
    NaxxramasCoreWarlockWrack()
        : PlayerScript(
            "NaxxramasCoreWarlockWrack",
            {
                PLAYERHOOK_ON_LOGIN,
                PLAYERHOOK_ON_TALENTS_RESET,
                PLAYERHOOK_ON_AFTER_SPEC_SLOT_CHANGED,
                PLAYERHOOK_ON_FORGOT_SPELL,
                PLAYERHOOK_ON_PLAYER_LEARN_TALENTS
            })
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        SyncWrack(player);
    }

    void OnPlayerTalentsReset(
        Player* player,
        bool /*noCost*/) override
    {
        if (!player ||
            player->getClass() != CLASS_WARLOCK ||
            !player->HasSpell(SPELL_WARLOCK_WRACK))
        {
            return;
        }

        // This hook fires immediately before the talent reset.
        // Remove Wrack now because Shadow Mastery Rank 5 is about
        // to be removed from the active specialization.
        player->removeSpell(
            SPELL_WARLOCK_WRACK,
            player->GetActiveSpecMask(),
            false);
    }

    void OnPlayerAfterSpecSlotChanged(
        Player* player,
        uint8 /*newSlot*/) override
    {
        SyncWrack(player);
    }

    void OnPlayerForgotSpell(
        Player* player,
        uint32 spellId) override
    {
        if (spellId == SPELL_WARLOCK_SHADOW_MASTERY_RANK_5 ||
            spellId == SPELL_WARLOCK_WRACK)
        {
            SyncWrack(player);
        }
    }

    void OnPlayerLearnTalents(
        Player* player,
        uint32 /*talentId*/,
        uint32 /*talentRank*/,
        uint32 /*spellId*/) override
    {
        SyncWrack(player);
    }
};

void AddWarlockWrackScripts()
{
    new NaxxramasCoreWarlockWrack();
}
