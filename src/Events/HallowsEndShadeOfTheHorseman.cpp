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
 * Optional solo fire path (default off):
 *     With NaxxramasCore.HallowsEnd.SoloFire.Enabled = 1 and exactly
 *     one real player nearby, bots are omitted from the existing
 *     CastFires count and a 42074 poll may stretch that aura's next
 *     interval. Multiplier 1 does not write the timer. A solo poll
 *     that finds no 42074 effect on a known trigger drops that watch.
 *     The poll does not cast a splash and does not remove the fire aura.
 *
 * Optional one-bucket path (default off):
 *     With both SoloFire.Enabled and SoloFire.OneBucket equal to 1,
 *     an accepted spell 42339 effect 0 hit on fire trigger 23686 may
 *     remove aura 42074 from that trigger only. The thrower has to be
 *     IsRealPlayer and the sole real player in the owning Shade's
 *     60 yard census. Without Playerbots.h the writer does not remove
 *     the aura. Exactly one living module Shade may own the trigger,
 *     and that Shade must have initiated spell 42132 on it this cycle.
 *     The hook does not cast 42348 and does not remove any other aura.
 *     Solo-fire pacing still uses IsHallowsEndShadePlayerBot.
 *
 * All other Shade of the Horseman behaviour is preserved
 * from the server's existing Hallow's End script when the option is off,
 * when no real player is nearby, or when two or more real players are nearby.
 */

#include "CellImpl.h"
#include "Containers.h"
#include "CreatureScript.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "AllSpellScript.h"
#include "HallowsEndSoloFire.h"
#include "ObjectAccessor.h"
#include "Player.h"
#include "ScriptedCreature.h"
#include "SharedDefines.h"
#include "SpellAuraEffects.h"
#include "Spell.h"
#include "TaskScheduler.h"

#if __has_include("Playerbots.h")
#include "Playerbots.h"
#define NAXXRAMAS_CORE_HALLOWS_SHADE_HAS_PLAYERBOTS 1
#else
#define NAXXRAMAS_CORE_HALLOWS_SHADE_HAS_PLAYERBOTS 0
#endif

#include <algorithm>
#include <list>
#include <optional>
#include <unordered_map>
#include <utility>
#include <vector>

namespace
{
    bool IsHallowsEndShadePlayerBot(Player* player)
    {
        if (!player)
            return false;

#if NAXXRAMAS_CORE_HALLOWS_SHADE_HAS_PLAYERBOTS
        return GET_PLAYERBOT_AI(player) != nullptr;
#else
        return false;
#endif
    }

    uint32 CountRealHallowsPlayers(
        std::list<Player*> const& players)
    {
        uint32 realPlayers = 0;

        for (Player* player : players)
        {
            if (player && !IsHallowsEndShadePlayerBot(player))
                ++realPlayers;
        }

        return realPlayers;
    }

    /* One-bucket only. The solo-fire helper above is unchanged.
     * With Playerbots.h the bool is the public IsRealPlayer.
     * Without that header the API is absent and isRealPlayer stays
     * false. A missing header is not treated as a human caster.
     */
    struct OneBucketCasterRead
    {
        bool apiPresent = false;
        bool isRealPlayer = false;
    };

    OneBucketCasterRead ReadOneBucketCaster(Player* player)
    {
        OneBucketCasterRead result;
#if NAXXRAMAS_CORE_HALLOWS_SHADE_HAS_PLAYERBOTS
        result.apiPresent = true;
        result.isRealPlayer = IsRealPlayer(player);
#else
        (void)player;
        result.apiPresent = false;
        result.isRealPlayer = false;
#endif
        return result;
    }
}

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
    SPELL_SPREAD_FIRE                  = 42079,
    SPELL_SUMMON_LANTERN                = 44255,
    SPELL_HORSEMAN_CONFLAGRATION        = 42380,
    SPELL_HORSEMAN_CONFLAGRATION_SOUND  = 48149,
    SPELL_HORSEMAN_CLEAVE               = 42587,

    // NPCs
    NPC_SHADE_OF_HORSEMAN               = 23543,
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

    /* Spell 42132 casts this Shade has initiated since Reset.
     * FinishEvent clears it. It is not armed from the event case.
     */
    NaxxramasCore::HallowsEndSoloFire::CycleIgnition ignitedThisCycle;

    std::unordered_map<ObjectGuid::LowType, NaxxramasCore::HallowsEndSoloFire::WatchState> soloFireWatches;

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
        ignitedThisCycle.Clear();

        soloFireWatches.clear();

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

        PollSoloFires();

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

    void CollectNearbyHallowsPlayers(
        std::list<Player*>& players) const
    {
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
    }

    /* True only after CastFires has called CastSpell(42132) for this
     * guid in the current cycle. Reset and FinishEvent clear the record.
     * The non-attackable flag, event-case entry, and playerCount are
     * not this signal.
     */
    bool IgnitedTriggerThisCycle(ObjectGuid const& guid) const
    {
        return ignitedThisCycle.Contains(
            static_cast<uint64_t>(guid.GetCounter()));
    }

    bool OwnsFireTrigger(ObjectGuid const& guid) const
    {
        for (ObjectGuid const& listed : unitList)
        {
            if (listed == guid)
                return true;
        }

        return false;
    }

    bool SoloFirePathActive(
        std::list<Player*> const& players) const
    {
        return NaxxramasCore::HallowsEndSoloFire::SoloPathActive(
            NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireEnabledSetting(),
            CountRealHallowsPlayers(players));
    }

    void DisarmSoloFireWatches()
    {
        for (auto& entry : soloFireWatches)
        {
            entry.second =
                NaxxramasCore::HallowsEndSoloFire::DisarmWatch(
                    entry.second);
        }
    }

    void PollSoloFires()
    {
        if (NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireEnabledSetting() != 1)
        {
            DisarmSoloFireWatches();
            return;
        }

        std::list<Player*> players;

        CollectNearbyHallowsPlayers(players);

        if (!SoloFirePathActive(players))
        {
            DisarmSoloFireWatches();
            return;
        }

        std::optional<int32_t> multiplier =
            NaxxramasCore::HallowsEndSoloFire::ReadHallowsEndSoloFireMultiplierSetting();

        for (ObjectGuid const& guid : unitList)
        {
            ObjectGuid::LowType id = guid.GetCounter();

            Unit* trigger = ObjectAccessor::GetUnit(
                *me,
                guid);

            bool triggerUsable =
                trigger &&
                trigger->GetEntry() == NPC_FIRE_TRIGGER;

            AuraEffect* aura = nullptr;

            if (triggerUsable)
            {
                aura = trigger->GetAuraEffect(
                    NaxxramasCore::HallowsEndSoloFire::FireAuraSpellId,
                    NaxxramasCore::HallowsEndSoloFire::FireAuraEffectIndex);
            }

            /*
             * A missing trigger or a missing 42074 effect drops the
             * watch. Keeping the old tick and amount would treat the
             * next aura on this GUID as the same fire.
             */
            if (NaxxramasCore::HallowsEndSoloFire::RetentionForObservation(
                    triggerUsable,
                    aura != nullptr) !=
                NaxxramasCore::HallowsEndSoloFire::WatchRetention::Keep)
            {
                soloFireWatches.erase(id);
                continue;
            }

            NaxxramasCore::HallowsEndSoloFire::WatchState previous;
            auto found = soloFireWatches.find(id);

            if (found != soloFireWatches.end())
                previous = found->second;

            NaxxramasCore::HallowsEndSoloFire::PollResult result =
                NaxxramasCore::HallowsEndSoloFire::PollActiveTrigger(
                    previous,
                    multiplier.has_value(),
                    multiplier.value_or(0),
                    aura->GetAmount(),
                    trigger->GetObjectScale(),
                    aura->GetTickNumber(),
                    aura->GetAmplitude());

            if (result.scale.writeScale)
            {
                trigger->SetObjectScale(
                    result.scale.scale);
            }

            if (result.timer.writeTimer)
            {
                aura->SetPeriodicTimer(
                    result.timer.timerValue);
            }

            soloFireWatches[id] = result.watch;
        }
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

        NaxxramasCore::HallowsEndSoloFire::FireCastRequest request;
        request.initial = initial;
        request.unlitTriggerCount = tmpList.size();

        std::list<Player*> players;

        if (!tmpList.empty())
            CollectNearbyHallowsPlayers(players);

        request.playerCountBeforeSoloFilter = players.size();

        if (!players.empty())
        {
            if (SoloFirePathActive(players))
            {
                players.remove_if([](Player* player)
                {
                    return IsHallowsEndShadePlayerBot(player);
                });
            }
        }

        request.playerCountAfterSoloFilter = players.size();

        if (!tmpList.empty() && !players.empty())
        {
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
                request.rateAllows =
                    !(tmpList.size() <
                        unitList.size() * playerRate);
            }
            else
            {
                playerCount += 1;
            }
        }

        /* Empty triggers, empty players, an empty solo-filtered list,
         * and a failed later-wave rate all return here. None of them
         * mark a trigger ignited.
         */
        if (!NaxxramasCore::HallowsEndSoloFire::FireCastRequestReachesIgnition(
                request))
            return;

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
            ObjectGuid guid = trigger->GetGUID();

            SpellCastResult castResult = me->CastSpell(
                trigger,
                SPELL_START_FIRE,
                true);

            if (castResult == SPELL_CAST_OK &&
                OwnsFireTrigger(guid))
            {
                ignitedThisCycle.NoteCastInitiated(
                    static_cast<uint64_t>(guid.GetCounter()));
            }
        }
    }

    void FinishEvent(bool failed)
    {
        ignitedThisCycle.Clear();

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

namespace
{
    static_assert(EFFECT_0 == 0, "42339 dummy effect index");
    static_assert(
        static_cast<uint8_t>(EFFECT_0) ==
        NaxxramasCore::HallowsEndSoloFire::BucketLandEffectIndex);

    /* The stock 42074 periodic handler casts 42079 from a burning
     * normal fire. The global check-cast hook intercepts only that
     * specific triggered spell, before it can start child fires.
     * It never modifies the fire aura, bucket effects or Shade waves.
     */
    bool ShouldStopSoloFireSpread(Creature* fire)
    {
        using namespace NaxxramasCore::HallowsEndSoloFire;

        if (!fire || fire->GetEntry() != NPC_FIRE_TRIGGER ||
            !fire->HasAura(SPELL_FIRE_AURA_BASE) ||
            ReadHallowsEndSoloFireEnabledSetting() != 1 ||
            ReadHallowsEndSoloFireDisableSpreadSetting() != 1)
            return false;

#if NAXXRAMAS_CORE_HALLOWS_SHADE_HAS_PLAYERBOTS
        SpreadGuardFacts facts;
        facts.soloEnabled = 1;
        facts.disableSpread = 1;
        facts.playerbotsApiPresent = true;
        facts.sourceIsNormalFire = true;
        facts.hasBaseFireAura = true;

        npc_naxxramas_hallows_end_soh* owner = nullptr;
        std::list<Creature*> shades;
        fire->GetCreaturesWithEntryInRange(
            shades, 100.0f, NPC_SHADE_OF_HORSEMAN);

        for (Creature* shade : shades)
        {
            if (!shade || !shade->IsAlive())
                continue;
            auto* ai = dynamic_cast<npc_naxxramas_hallows_end_soh*>(shade->AI());
            if (!ai || !ai->OwnsFireTrigger(fire->GetGUID()))
                continue;

            ++facts.livingOwnerShadeCount;
            if (ai->IgnitedTriggerThisCycle(fire->GetGUID()))
            {
                ++facts.activeOwnerShadeCount;
                owner = ai;
            }
        }

        if (facts.livingOwnerShadeCount == 1 &&
            facts.activeOwnerShadeCount == 1 && owner)
        {
            std::list<Player*> players;
            owner->CollectNearbyHallowsPlayers(players);
            facts.realPlayersNearOwner = CountRealHallowsPlayers(players);
        }

        return ShouldBlockFireSpread(facts);
#else
        /* No reliable Playerbots identification: never suppress spread. */
        return false;
#endif
    }

    struct OneBucketOwnerLists
    {
        std::vector<NaxxramasCore::HallowsEndSoloFire::ShadeOwnerView> shades;
        std::vector<NaxxramasCore::HallowsEndSoloFire::CensusPlayerView> players;
        uint64_t casterId = 0;
    };

    /* 100 yards matches the Shade Reset scan that builds unitList
     * (this file and hallows_end.cpp:680). A Shade outside that radius
     * is not treated as an owner. Living module owners are collected
     * before the active subset. An owner that has not initiated 42132
     * on this trigger stays in the list with ignitedThisTrigger false.
     */
    OneBucketOwnerLists CollectOneBucketOwnerCensus(
        Creature* fire,
        Player* caster)
    {
        using namespace NaxxramasCore::HallowsEndSoloFire;

        OneBucketOwnerLists lists;
        std::vector<npc_naxxramas_hallows_end_soh*> owners;

        std::list<Creature*> shades;

        fire->GetCreaturesWithEntryInRange(
            shades,
            100.0f,
            NPC_SHADE_OF_HORSEMAN);

        for (Creature* shade : shades)
        {
            if (!shade || !shade->IsAlive())
                continue;

            auto* ai = dynamic_cast<npc_naxxramas_hallows_end_soh*>(
                shade->AI());

            if (!ai)
                continue;

            if (!ai->OwnsFireTrigger(fire->GetGUID()))
                continue;

            ShadeOwnerView view;
            view.alive = true;
            view.moduleScript = true;
            view.ownsTrigger = true;
            view.ignitedThisTrigger = ai->IgnitedTriggerThisCycle(
                fire->GetGUID());
            lists.shades.push_back(view);
            owners.push_back(ai);
        }

        OwnerCensusTally tally = TallyShadeOwners(
            lists.shades.data(),
            lists.shades.size());

        if (tally.livingOwners != 1 ||
            tally.activeOwners != 1 ||
            owners.size() != 1 ||
            !caster)
            return lists;

        lists.casterId = static_cast<uint64_t>(
            caster->GetGUID().GetCounter());

        std::list<Player*> players;

        owners.front()->CollectNearbyHallowsPlayers(players);

        for (Player* player : players)
        {
            CensusPlayerView view;
            view.playerId = player
                ? static_cast<uint64_t>(player->GetGUID().GetCounter())
                : 0;
            view.isRealPlayer = ReadOneBucketCaster(player).isRealPlayer;
            lists.players.push_back(view);
        }

        return lists;
    }

    /* Called only from AllSpellScript::OnDummyEffect for a creature.
     * That callback runs after the stock bucket script, on a validated
     * hit (SpellEffects.cpp:694-695 and :798-800). A miss or a cancel
     * does not enter here. 42074 is read before any removal. The only
     * write is RemoveAurasDueToSpell(42074) on this creature.
     * A missing Playerbots API never reaches that write.
     */
    void ApplyHallowsEndOneBucket(
        WorldObject* caster,
        uint32 spellId,
        SpellEffIndex effIndex,
        Creature* target)
    {
        using namespace NaxxramasCore::HallowsEndSoloFire;

        if (!target)
            return;

        /* Wrong spell, effect, or creature never reads config and never
         * searches. DecideOneBucket refuses those inputs the same way.
         */
        if (spellId != BucketLandSpellId ||
            static_cast<uint8_t>(effIndex) != BucketLandEffectIndex ||
            target->GetEntry() != FireTriggerEntry)
            return;

        int32_t const oneBucket = ReadHallowsEndSoloFireOneBucketSetting();
        int32_t const soloEnabled = ReadHallowsEndSoloFireEnabledSetting();
        bool const hasAura = target->HasAura(FireAuraSpellId);
        Player* player = caster ? caster->ToPlayer() : nullptr;
        OneBucketCasterRead casterRead = ReadOneBucketCaster(player);

        std::vector<ShadeOwnerView> shades;
        std::vector<CensusPlayerView> players;
        uint64_t casterId = 0;

        bool const cheapGates =
            oneBucket == 1 &&
            soloEnabled == 1 &&
            player != nullptr &&
            casterRead.apiPresent &&
            casterRead.isRealPlayer &&
            hasAura;

        if (cheapGates)
        {
            OneBucketOwnerLists lists =
                CollectOneBucketOwnerCensus(target, player);
            shades = std::move(lists.shades);
            players = std::move(lists.players);
            casterId = lists.casterId;
        }

        OneBucketObservation observation;
        observation.hitAccepted = true;
        observation.spellId = spellId;
        observation.effectIndex = static_cast<uint8_t>(effIndex);
        observation.targetEntry = target->GetEntry();
        observation.targetHasFireAura = hasAura;
        observation.oneBucket = oneBucket;
        observation.soloEnabled = soloEnabled;
        observation.casterIsPlayer = player != nullptr;
        observation.playerbotsApiPresent = casterRead.apiPresent;
        observation.casterIsRealPlayer = casterRead.isRealPlayer;
        observation.casterId = casterId;
        observation.shades = shades.data();
        observation.shadeCount = shades.size();
        observation.players = players.data();
        observation.playerCount = players.size();

        OneBucketFacts facts = FactsFromObservation(observation);
        OneBucketDecision decision = DecideOneBucket(facts);

        if (!decision.removeFireAura)
            return;

        target->RemoveAurasDueToSpell(FireAuraSpellId);
    }
}

class spell_naxxramas_hallows_end_no_solo_spread : public AllSpellScript
{
public:
    spell_naxxramas_hallows_end_no_solo_spread()
        : AllSpellScript(
            "spell_naxxramas_hallows_end_no_solo_spread",
            { ALLSPELLHOOK_ON_SPELL_CHECK_CAST })
    {
    }

    void OnSpellCheckCast(
        Spell* spell, bool /*strict*/, SpellCastResult& result) override
    {
        if (!spell || result != SPELL_CAST_OK ||
            !spell->GetSpellInfo() ||
            spell->GetSpellInfo()->Id != SPELL_SPREAD_FIRE)
            return;

        WorldObject* caster = spell->GetCaster();
        Creature* fire = caster ? caster->ToCreature() : nullptr;
        if (ShouldStopSoloFireSpread(fire))
            result = SPELL_FAILED_DONT_REPORT;
    }
};

class spell_naxxramas_hallows_end_one_bucket : public AllSpellScript
{
public:
    spell_naxxramas_hallows_end_one_bucket()
        : AllSpellScript(
            "spell_naxxramas_hallows_end_one_bucket",
            { ALLSPELLHOOK_ON_DUMMY_EFFECT_CREATURE })
    {
    }

    void OnDummyEffect(
        WorldObject* caster,
        uint32 spellId,
        SpellEffIndex effIndex,
        Creature* creatureTarget) override
    {
        ApplyHallowsEndOneBucket(
            caster,
            spellId,
            effIndex,
            creatureTarget);
    }
};

void AddHallowsEndShadeOfTheHorsemanScripts()
{
    RegisterCreatureAI(
        npc_naxxramas_hallows_end_soh);

    new spell_naxxramas_hallows_end_one_bucket();
    new spell_naxxramas_hallows_end_no_solo_spread();
}