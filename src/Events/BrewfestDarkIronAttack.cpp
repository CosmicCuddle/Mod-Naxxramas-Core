/*
 * Naxxramas Core
 * Events - Brewfest - Dark Iron Attack
 *
 * Custom replacement for AzerothCore:
 * npc_dark_iron_attack_generator
 *
 * Custom change:
 *
 * Dark Iron mole machine spawn interval
 *
 * AzerothCore original:
 *     events.Repeat(3s);
 *
 * Naxxramas Core:
 *     events.Repeat(12s);
 *
 * All other Dark Iron attack generator behaviour is
 * preserved from the server's existing Brewfest script.
 */

#include "AreaDefines.h"
#include "CreatureScript.h"
#include "ObjectAccessor.h"
#include "Random.h"
#include "ScriptedCreature.h"
#include "SharedDefines.h"
#include "SpellInfo.h"
#include "Timer.h"

#include <cmath>
#include <cstdio>
#include <list>

enum NaxxramasBrewfestDarkIronAttack
{
    // GOs
    GO_MOLE_MACHINE                     = 195305,

    // NPCs
    NPC_BARLEYBREW_KEG                  = 23700,
    NPC_THUNDERBREW_KEG                 = 23702,
    NPC_GORDOK_KEG                      = 23706,
    NPC_VOODOO_KEG                      = 24373,
    NPC_DROHN_KEG                       = 24372,
    NPC_MOLE_MACHINE_TRIGGER            = 23894,
    NPC_DARK_IRON_GUZZLER               = 23709,
    NPC_NORMAL_DROHN                    = 24492,
    NPC_NORMAL_VOODOO                   = 24493,
    NPC_NORMAL_BARLEYBREW               = 23683,
    NPC_NORMAL_THUNDERBREW              = 23684,
    NPC_NORMAL_GORDOK                   = 23685,
    NPC_EVENT_GENERATOR                 = 23703,
    NPC_SUPER_BREW_TRIGGER              = 23808,
    NPC_DARK_IRON_HERALD                = 24536,
    NPC_BREWFEST_REVELER                = 24484,

    // Events
    EVENT_CHECK_HOUR                    = 1,
    EVENT_SPAWN_MOLE_MACHINE            = 2,
    EVENT_PRE_FINISH_ATTACK             = 3,
    EVENT_FINISH_ATTACK                 = 4,
    EVENT_BARTENDER_SAY                 = 5,

    // Spells
    SPELL_THROW_MUG_TO_PLAYER           = 42300,
    SPELL_ADD_MUG                       = 42518,
    SPELL_SPAWN_MOLE_MACHINE            = 43563,
    SPELL_KEG_MARKER                    = 42761,
    SPELL_PLAYER_MUG                    = 42436,
    SPELL_REPORT_DEATH                  = 42655,
    SPELL_CREATE_SUPER_BREW             = 42715,
    SPELL_DRUNKEN_MASTER                = 42696,
    SPELL_SUMMON_PLANS_A                = 48145,
    SPELL_SUMMON_PLANS_H                = 49318,
    SPELL_WEAK_ALCOHOL                  = 42523,

    // Dark Irons
    SPELL_ATTACK_KEG                    = 42393,
    SPELL_KNOCKBACK_AURA                = 42676,
    SPELL_MUG_BOUNCE_BACK               = 42522,
};

struct npc_naxxramas_dark_iron_attack_generator : public ScriptedAI
{
    npc_naxxramas_dark_iron_attack_generator(Creature* creature)
        : ScriptedAI(creature), summons(me) { }

    EventMap events;
    SummonList summons;
    uint32 kegCounter, guzzlerCounter;
    uint8 thrown;
    GuidVector revelerGUIDs;

    void Reset() override
    {
        for (ObjectGuid const& guid : revelerGUIDs)
        {
            if (Creature* reveler = ObjectAccessor::GetCreature(*me, guid))
            {
                reveler->SetRespawnDelay(5 * MINUTE);
                reveler->Respawn();

                // SmartAI::JustRespawned restores the original faction.
                // Delay slightly before reloading creature template auras.
                reveler->m_Events.AddEventAtOffset([reveler]()
                {
                    reveler->RemoveAllAuras();
                    reveler->LoadCreaturesAddon(true);
                }, 100ms);
            }
        }

        revelerGUIDs.clear();

        summons.DespawnAll();
        events.Reset();
        events.ScheduleEvent(EVENT_CHECK_HOUR, 2s);

        kegCounter = 0;
        guzzlerCounter = 0;
        thrown = 0;
    }

    // DARK IRON ATTACK EVENT
    void MoveInLineOfSight(Unit* /*who*/) override { }

    void JustEngagedWith(Unit*) override { }

    void SpellHit(Unit* caster, SpellInfo const* spellInfo) override
    {
        if (spellInfo->Id == SPELL_REPORT_DEATH)
        {
            if (caster->GetEntry() == NPC_DARK_IRON_GUZZLER)
            {
                guzzlerCounter++;
            }
            else
            {
                kegCounter++;

                if (kegCounter == 3)
                    FinishEventDueToLoss();
            }
        }
    }

    void UpdateAI(uint32 diff) override
    {
        events.Update(diff);

        switch (events.ExecuteEvent())
        {
            case EVENT_CHECK_HOUR:
            {
                // Determine hour.
                if (AllowStart())
                {
                    PrepareEvent();
                    events.Repeat(300s);
                    return;
                }

                events.Repeat(2s);
                break;
            }

            case EVENT_SPAWN_MOLE_MACHINE:
            {
                if (me->GetMapId() == MAP_KALIMDOR)
                {
                    float rand = 8 + rand_norm() * 12;
                    float angle = rand_norm() * 2 * M_PI;

                    float x = 1201.8f + rand * cos(angle);
                    float y = -4299.6f + rand * std::sin(angle);

                    if (Creature* cr = me->SummonCreature(
                            NPC_MOLE_MACHINE_TRIGGER,
                            x,
                            y,
                            21.3f,
                            0.0f))
                    {
                        cr->CastSpell(
                            cr,
                            SPELL_SPAWN_MOLE_MACHINE,
                            true);
                    }
                }
                else if (me->GetMapId() == MAP_EASTERN_KINGDOMS)
                {
                    float rand = rand_norm() * 20;
                    float angle = rand_norm() * 2 * M_PI;

                    float x = -5157.1f + rand * cos(angle);
                    float y = -598.98f + rand * std::sin(angle);

                    if (Creature* cr = me->SummonCreature(
                            NPC_MOLE_MACHINE_TRIGGER,
                            x,
                            y,
                            398.11f,
                            0.0f))
                    {
                        cr->CastSpell(
                            cr,
                            SPELL_SPAWN_MOLE_MACHINE,
                            true);
                    }
                }

                /*
                 * NAXXRAMAS CORE CUSTOM CHANGE
                 *
                 * AzerothCore:
                 *     events.Repeat(3s);
                 *
                 * Custom:
                 *     events.Repeat(12s);
                 */
                events.Repeat(12s);

                break;
            }

            case EVENT_PRE_FINISH_ATTACK:
            {
                events.CancelEvent(EVENT_SPAWN_MOLE_MACHINE);
                events.ScheduleEvent(EVENT_FINISH_ATTACK, 20s);

                break;
            }

            case EVENT_FINISH_ATTACK:
            {
                FinishAttackDueToWin();
                events.RescheduleEvent(EVENT_CHECK_HOUR, 1min);

                break;
            }

            case EVENT_BARTENDER_SAY:
            {
                /*
                 * NOTE:
                 * This 12-second timer is ORIGINAL Brewfest behaviour.
                 * It is unrelated to our custom mole-machine timer.
                 */
                events.Repeat(12s);

                Creature* sayer = GetRandomBartender();

                if (!sayer)
                    return;

                thrown++;

                if (thrown == 3)
                {
                    thrown = 0;

                    sayer->Say(
                        "SOMEONE TRY THIS SUPER BREW!",
                        LANG_UNIVERSAL);

                    // sayer->CastSpell(
                    //     sayer,
                    //     SPELL_CREATE_SUPER_BREW,
                    //     true);

                    sayer->SummonCreature(
                        NPC_SUPER_BREW_TRIGGER,
                        sayer->GetPositionX() +
                            15 * cos(sayer->GetOrientation()),
                        sayer->GetPositionY() +
                            15 * std::sin(sayer->GetOrientation()),
                        sayer->GetPositionZ(),
                        0.0f,
                        TEMPSUMMON_TIMED_OR_CORPSE_DESPAWN,
                        30000);
                }
                else
                {
                    if (urand(0, 1))
                    {
                        sayer->Say(
                            "Chug and chuck! Chug and chuck!",
                            LANG_UNIVERSAL);
                    }
                    else
                    {
                        sayer->Say(
                            "Down the free brew and pelt the Guzzlers with your mug!",
                            LANG_UNIVERSAL);
                    }
                }

                break;
            }

            default:
                break;
        }
    }

    void FinishEventDueToLoss()
    {
        if (Creature* herald = me->FindNearestCreature(
                NPC_DARK_IRON_HERALD,
                100.0f))
        {
            char amount[500];

            snprintf(
                amount,
                sizeof(amount),
                "We did it boys! Now back to the Grim Guzzler and we'll drink to the %u that were injured!",
                guzzlerCounter);

            herald->Yell(
                amount,
                LANG_UNIVERSAL);
        }

        Reset();

        events.RescheduleEvent(
            EVENT_CHECK_HOUR,
            1min);
    }

    void FinishAttackDueToWin()
    {
        if (Creature* herald = me->FindNearestCreature(
                NPC_DARK_IRON_HERALD,
                100.0f))
        {
            char amount[500];

            snprintf(
                amount,
                sizeof(amount),
                "RETREAT!! We've already lost %u and we can't afford to lose any more!!",
                guzzlerCounter);

            herald->Yell(
                amount,
                LANG_UNIVERSAL);
        }

        me->CastSpell(
            me,
            me->GetMapId() == MAP_KALIMDOR
                ? SPELL_SUMMON_PLANS_H
                : SPELL_SUMMON_PLANS_A,
            true);

        Reset();
    }

    void PrepareEvent()
    {
        std::list<Creature*> revelers;

        GetCreatureListWithEntryInGrid(
            revelers,
            me,
            NPC_BREWFEST_REVELER,
            100.0f);

        for (Creature* reveler : revelers)
        {
            revelerGUIDs.push_back(
                reveler->GetGUID());

            reveler->SetRespawnDelay(
                MONTH);

            reveler->AI()->SetData(
                0,
                me->GetMapId());
        }

        Creature* cr;

        if (me->GetMapId() == MAP_KALIMDOR)
        {
            if ((cr = me->SummonCreature(
                    NPC_DROHN_KEG,
                    1183.69f,
                    -4315.15f,
                    21.1875f,
                    0.750492f)))
            {
                cr->SetReactState(REACT_PASSIVE);

                summons.Summon(cr);

                revelerGUIDs.push_back(
                    cr->GetGUID());
            }

            if ((cr = me->SummonCreature(
                    NPC_VOODOO_KEG,
                    1182.42f,
                    -4272.45f,
                    21.1182f,
                    -1.02974f)))
            {
                cr->SetReactState(REACT_PASSIVE);

                summons.Summon(cr);

                revelerGUIDs.push_back(
                    cr->GetGUID());
            }

            if ((cr = me->SummonCreature(
                    NPC_GORDOK_KEG,
                    1223.78f,
                    -4296.48f,
                    21.1707f,
                    -2.86234f)))
            {
                cr->SetReactState(REACT_PASSIVE);

                summons.Summon(cr);

                revelerGUIDs.push_back(
                    cr->GetGUID());
            }
        }
        else if (me->GetMapId() == MAP_EASTERN_KINGDOMS)
        {
            if ((cr = me->SummonCreature(
                    NPC_BARLEYBREW_KEG,
                    -5187.23f,
                    -599.779f,
                    397.176f,
                    0.017453f)))
            {
                cr->SetReactState(REACT_PASSIVE);

                summons.Summon(cr);

                revelerGUIDs.push_back(
                    cr->GetGUID());
            }

            if ((cr = me->SummonCreature(
                    NPC_THUNDERBREW_KEG,
                    -5160.05f,
                    -632.632f,
                    397.178f,
                    1.39626f)))
            {
                cr->SetReactState(REACT_PASSIVE);

                summons.Summon(cr);

                revelerGUIDs.push_back(
                    cr->GetGUID());
            }

            if ((cr = me->SummonCreature(
                    NPC_GORDOK_KEG,
                    -5145.75f,
                    -575.667f,
                    397.176f,
                    -2.28638f)))
            {
                cr->SetReactState(REACT_PASSIVE);

                summons.Summon(cr);

                revelerGUIDs.push_back(
                    cr->GetGUID());
            }
        }

        if ((cr = me->SummonCreature(
                NPC_DARK_IRON_HERALD,
                me->GetPositionX(),
                me->GetPositionY(),
                me->GetPositionZ(),
                0.0f,
                TEMPSUMMON_TIMED_DESPAWN,
                300000)))
        {
            summons.Summon(cr);
        }

        kegCounter = 0;
        guzzlerCounter = 0;
        thrown = 0;

        events.ScheduleEvent(
            EVENT_SPAWN_MOLE_MACHINE,
            1500ms);

        events.ScheduleEvent(
            EVENT_PRE_FINISH_ATTACK,
            280s);

        events.ScheduleEvent(
            EVENT_BARTENDER_SAY,
            5s);
    }

    bool AllowStart()
    {
        auto minutes = Acore::Time::GetMinutes();

        if (!minutes || minutes == 30)
            return true;

        return false;
    }

    Creature* GetRandomBartender()
    {
        uint32 entry = 0;

        switch (urand(0, 2))
        {
            case 0:
                entry =
                    me->GetMapId() == MAP_KALIMDOR
                        ? NPC_NORMAL_DROHN
                        : NPC_NORMAL_THUNDERBREW;
                break;

            case 1:
                entry =
                    me->GetMapId() == MAP_KALIMDOR
                        ? NPC_NORMAL_VOODOO
                        : NPC_NORMAL_BARLEYBREW;
                break;

            case 2:
                entry = NPC_NORMAL_GORDOK;
                break;

            default:
                break;
        }

        return me->FindNearestCreature(
            entry,
            100.0f);
    }
};

void AddBrewfestDarkIronAttackScripts()
{
    RegisterCreatureAI(
        npc_naxxramas_dark_iron_attack_generator);
}