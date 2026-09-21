/*
 * Naxxramas Core
 * Events - Hallow's End - Shade of the Horseman
 *
 * Custom replacement for AzerothCore:
 * npc_hallows_end_soh
 *
 * Custom changes:
 *
 * Event fire cycle:
 *     AzerothCore: 15 seconds
 *     Naxxramas Core: 30 seconds
 *
 * Event completion/failure check:
 *     AzerothCore: counter > 21
 *     Naxxramas Core: counter > 14
 *
 * All other Shade of the Horseman behaviour is preserved
 * from the server's existing Hallow's End script.
 */

#include "CellImpl.h"
#include "Containers.h"
#include "CreatureScript.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "ScriptedCreature.h"
#include "TaskScheduler.h"

#include <algorithm>
#include <list>
#include <vector>

enum NaxxramasHallowsEndShade
{
    // Quests
    QUEST_LET_THE_FIRES_COME_A          = 12135,
    QUEST_LET_THE_FIRES_COME_H          = 12139,
    QUEST_STOP_THE_FIRES_A              = 11131,
    QUEST_STOP_THE_FIRES_H              = 11219,

    // Spells
    SPELL_HORSEMAN_MOUNT                = 48025,
    SPELL_FIRE_AURA_BASE                = 42074,
    SPELL_START_FIRE                    = 42132,
    SPELL_SUMMON_LANTERN                = 44255,
    SPELL_HORSEMAN_CONFLAGRATION        = 42380,
    SPELL_HORSEMAN_CONFLAGRATION_SOUND  = 48149,
    SPELL_HORSEMAN_CLEAVE               = 42587,

    // NPCs
    NPC_FIRE_TRIGGER                    = 23686,

    // Talks
    TALK_SHADE_CONFLAGRATION            = 0,
    TALK_SHADE_PREPARE                  = 1,
    TALK_SHADE_START_EVENT              = 2,
    TALK_SHADE_MORE_FIRES               = 3,
    TALK_SHADE_FAILED                   = 4,
    TALK_SHADE_DEFEATED                 = 5,
    TALK_SHADE_DEATH                    = 6,
};

struct npc_naxxramas_hallows_end_soh : public ScriptedAI
{
    npc_naxxramas_hallows_end_soh(Creature* creature)
        : ScriptedAI(creature)
    {
        pos = 0;
        counter = 0;
        unitList.clear();

        me->CastSpell(
            me,
            SPELL_HORSEMAN_MOUNT,
            true);

        me->SetSpeed(
            MOVE_WALK,
            3.0f,
            true);
    }

    EventMap events;

    uint32 playerCount;
    uint32 counter;

    GuidList unitList;

    int32 pos;

    TaskScheduler scheduler;

    void JustEngagedWith(Unit*) override
    {
        scheduler.Schedule(6s, [this](TaskContext context)
        {
            if (Unit* target =
                    SelectTarget(
                        SelectTargetMethod::Random,
                        0,
                        30.0f,
                        true))
            {
                me->CastSpell(
                    target,
                    SPELL_HORSEMAN_CONFLAGRATION,
                    false);

                target->CastSpell(
                    target,
                    SPELL_HORSEMAN_CONFLAGRATION_SOUND,
                    true);

                Talk(
                    TALK_SHADE_CONFLAGRATION);
            }

            context.Repeat(12s);
        })
        .Schedule(7s, [this](TaskContext context)
        {
            DoCastVictim(
                SPELL_HORSEMAN_CLEAVE,
                true);

            context.Repeat(8s);
        });
    }

    void MoveInLineOfSight(Unit* /*who*/) override
    {
    }

    void DoAction(int32 param) override
    {
        pos = param;
    }

    void GetPosToLand(
        float& x,
        float& y,
        float& z)
    {
        switch (pos)
        {
            case 235431:
                x = -9445.1f;
                y = 63.27f;
                z = 58.16f;
                break;

            case 235432:
                x = -5616.30f;
                y = -481.89f;
                z = 398.99f;
                break;

            case 235433:
                x = -4198.1f;
                y = -12509.13f;
                z = 46.6f;
                break;

            case 235434:
                x = 360.9f;
                y = -4735.5f;
                z = 11.773f;
                break;

            case 235435:
                x = 2229.4f;
                y = 263.1f;
                z = 36.13f;
                break;

            case 235436:
                x = 9532.9f;
                y = -6833.8f;
                z = 18.5f;
                break;

            default:
                x = 0.0f;
                y = 0.0f;
                z = 0.0f;
                break;
        }
    }

    void Reset() override
    {
        playerCount = 0;

        unitList.clear();

        std::list<Creature*> temp;

        me->GetCreaturesWithEntryInRange(
            temp,
            100.0f,
            NPC_FIRE_TRIGGER);

        for (std::list<Creature*>::const_iterator itr =
                temp.begin();
             itr != temp.end();
             ++itr)
        {
            unitList.push_back(
                (*itr)->GetGUID());
        }

        events.ScheduleEvent(1, 3s);
        events.ScheduleEvent(2, 25s);
        events.ScheduleEvent(2, 43s);
        events.ScheduleEvent(3, 63s);

        me->SetReactState(
            REACT_PASSIVE);

        me->SetUnitFlag(
            UNIT_FLAG_NON_ATTACKABLE);

        me->SetCanFly(true);
        me->SetDisableGravity(true);
    }

    void EnterEvadeMode(
        EvadeReason /*why*/) override
    {
        me->DespawnOrUnsummon(1ms);
    }

    uint32 GetData(
        uint32 /*type*/) const override
    {
        return playerCount;
    }

    void UpdateAI(uint32 diff) override
    {
        events.Update(diff);

        if (me->HasUnitState(
                UNIT_STATE_CASTING))
        {
            return;
        }

        switch (events.ExecuteEvent())
        {
            case 1:
            {
                Talk(
                    TALK_SHADE_PREPARE);

                break;
            }

            case 2:
            {
                CastFires(true);

                break;
            }

            case 3:
            {
                bool checkBurningTriggers = false;

                for (ObjectGuid const& guid : unitList)
                {
                    if (Unit* creature =
                            ObjectAccessor::GetUnit(
                                *me,
                                guid))
                    {
                        if (creature->HasPeriodicDummyAura())
                        {
                            checkBurningTriggers = true;
                            break;
                        }
                    }
                }

                /*
                 * If all fires have already been extinguished,
                 * finish the event successfully.
                 */
                if (!checkBurningTriggers)
                {
                    FinishEvent(false);
                    return;
                }

                counter++;

                /*
                 * NAXXRAMAS CORE CUSTOM CHANGE
                 *
                 * AzerothCore:
                 *
                 *     if (counter > 21)
                 *
                 * Naxxramas Core:
                 *
                 *     if (counter > 14)
                 */
                if (counter > 14)
                {
                    bool failed = false;

                    for (ObjectGuid const& guid : unitList)
                    {
                        if (Unit* creature =
                                ObjectAccessor::GetUnit(
                                    *me,
                                    guid))
                        {
                            if (creature->HasPeriodicDummyAura())
                            {
                                failed = true;
                                break;
                            }
                        }
                    }

                    FinishEvent(failed);
                    return;
                }

                if (counter == 5)
                {
                    Talk(
                        TALK_SHADE_START_EVENT);
                }
                else if (counter == 15)
                {
                    Talk(
                        TALK_SHADE_MORE_FIRES);
                }

                CastFires(false);

                /*
                 * NAXXRAMAS CORE CUSTOM CHANGE
                 *
                 * AzerothCore:
                 *
                 *     events.Repeat(15s);
                 *
                 * Naxxramas Core:
                 *
                 *     events.Repeat(30s);
                 */
                events.Repeat(30s);

                break;
            }

            case 4:
            {
                me->ReplaceAllUnitFlags(
                    UNIT_FLAG_NONE);

                me->SetReactState(
                    REACT_AGGRESSIVE);

                if (Unit* target =
                        me->SelectNearestPlayer(
                            30.0f))
                {
                    AttackStart(target);
                }

                break;
            }

            default:
                break;
        }

        if (!UpdateVictim())
            return;

        scheduler.Update(diff, [this]
        {
            DoMeleeAttackIfReady();
        });
    }

    void CastFires(bool initial)
    {
        std::vector<Unit*> tmpList;

        for (ObjectGuid const& guid : unitList)
        {
            if (Unit* creature =
                    ObjectAccessor::GetUnit(
                        *me,
                        guid))
            {
                if (!creature->HasPeriodicDummyAura())
                {
                    tmpList.push_back(
                        creature);
                }
            }
        }

        if (tmpList.empty())
            return;

        std::list<Player*> players;

        Acore::AnyPlayerInObjectRangeCheck checker(
            me,
            60.0f);

        Acore::PlayerListSearcher<
            Acore::AnyPlayerInObjectRangeCheck>
            searcher(
                me,
                players,
                checker);

        Cell::VisitObjects(
            me,
            searcher,
            60.0f);

        if (players.empty())
            return;

        playerCount =
            static_cast<uint32>(
                players.size()) - 1;

        if (!initial)
        {
            float playerRate =
                std::max(
                    0.0f,
                    0.5f -
                        playerCount * 0.25f);

            /*
             * If there are more burning triggers
             * than players, do not cast the next fire.
             */
            if (tmpList.size() <
                unitList.size() * playerRate)
            {
                return;
            }
        }
        else
        {
            playerCount += 1;
        }

        uint32 sizeCount =
            (playerCount / 3) + 1;

        if (initial &&
            playerCount > 0)
        {
            sizeCount +=
                playerCount % 2;
        }

        Acore::Containers::RandomResize(
            tmpList,
            sizeCount);

        for (Unit* trigger : tmpList)
        {
            me->CastSpell(
                trigger,
                SPELL_START_FIRE,
                true);
        }
    }

    void FinishEvent(bool failed)
    {
        if (failed)
        {
            Talk(
                TALK_SHADE_FAILED);

            for (ObjectGuid const& guid : unitList)
            {
                if (Unit* creature =
                        ObjectAccessor::GetUnit(
                            *me,
                            guid))
                {
                    creature->RemoveAllAuras();
                }
            }

            me->DespawnOrUnsummon(1ms);
        }
        else
        {
            Talk(
                TALK_SHADE_DEFEATED);

            float x;
            float y;
            float z;

            GetPosToLand(
                x,
                y,
                z);

            me->GetMotionMaster()->Clear();
            me->GetMotionMaster()->MoveIdle();

            me->GetMotionMaster()->MovePoint(
                8,
                x,
                y,
                z);
        }
    }

    void MovementInform(
        uint32 type,
        uint32 point) override
    {
        if (type == POINT_MOTION_TYPE &&
            point == 8)
        {
            me->RemoveAllAuras();

            me->SetCanFly(false);
            me->SetDisableGravity(false);

            events.ScheduleEvent(
                4,
                2s);
        }
    }

    void JustDied(
        Unit* /*killer*/) override
    {
        Talk(
            TALK_SHADE_DEATH);

        float x;
        float y;
        float z;

        GetPosToLand(
            x,
            y,
            z);

        me->CastSpell(
            x,
            y,
            z,
            SPELL_SUMMON_LANTERN,
            true);

        CompleteQuest();
    }

    void CompleteQuest()
    {
        float radius = 100.0f;

        std::list<Player*> players;

        Acore::AnyPlayerInObjectRangeCheck checker(
            me,
            radius);

        Acore::PlayerListSearcher<
            Acore::AnyPlayerInObjectRangeCheck>
            searcher(
                me,
                players,
                checker);

        Cell::VisitObjects(
            me,
            searcher,
            radius);

        for (Player* player : players)
        {
            player->AreaExploredOrEventHappens(
                QUEST_STOP_THE_FIRES_H);

            player->AreaExploredOrEventHappens(
                QUEST_STOP_THE_FIRES_A);

            player->AreaExploredOrEventHappens(
                QUEST_LET_THE_FIRES_COME_H);

            player->AreaExploredOrEventHappens(
                QUEST_LET_THE_FIRES_COME_A);
        }
    }
};

void AddHallowsEndShadeOfTheHorsemanScripts()
{
    RegisterCreatureAI(
        npc_naxxramas_hallows_end_soh);
}