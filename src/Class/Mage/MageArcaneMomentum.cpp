/*
 * Naxxramas Core
 * Mage - Arcane Momentum (optional directional Blink)
 *
 * Mages can learn/unlearn the technique from an existing Mage trainer.
 * The choice is stored per character and normal Blink remains the default.
 *
 * Spell 1953 retains its original client data, cooldown, and effects.
 * We only redirect its calculated leap destination after checking collisions.
 */

#include "Chat.h"
#include "Creature.h"
#include "DatabaseEnv.h"
#include "GossipDef.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptedGossip.h"
#include "SharedDefines.h"
#include "Spell.h"
#include "SpellInfo.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Trainer.h"

#include <cmath>
#include <unordered_set>

namespace
{
    constexpr uint32 SPELL_MAGE_BLINK = 1953;

    constexpr uint32 GOSSIP_ACTION_ARCANE_MOMENTUM_INFO = 92010;
    constexpr uint32 GOSSIP_ACTION_ARCANE_MOMENTUM_LEARN = 92011;
    constexpr uint32 GOSSIP_ACTION_ARCANE_MOMENTUM_UNLEARN = 92012;

    // Accessed on AzerothCore's world/script thread.
    // An empty/missing row means the character uses normal Blink.
    std::unordered_set<uint32> ArcaneMomentumMages;

    bool IsMageTrainer(Player const* player, Creature const* creature)
    {
        if (!player || !creature || player->getClass() != CLASS_MAGE)
            return false;

        Trainer::Trainer const* trainer = sObjectMgr->GetTrainer(creature->GetEntry());

        return trainer &&
               trainer->GetTrainerType() == Trainer::Type::Class &&
               trainer->GetTrainerRequirement() == CLASS_MAGE &&
               trainer->IsTrainerValidForPlayer(player);
    }

    bool HasArcaneMomentum(Player const* player)
    {
        return player &&
               ArcaneMomentumMages.find(player->GetGUID().GetCounter()) != ArcaneMomentumMages.end();
    }

    void SetArcaneMomentum(Player* player, bool enabled)
    {
        if (!player || player->getClass() != CLASS_MAGE)
            return;

        uint32 guid = player->GetGUID().GetCounter();

        if (enabled)
        {
            CharacterDatabase.DirectExecute(
                "INSERT INTO mod_naxxramas_arcane_momentum (guid) VALUES ({}) "
                "ON DUPLICATE KEY UPDATE guid = VALUES(guid)", guid);

            ArcaneMomentumMages.insert(guid);
        }
        else
        {
            CharacterDatabase.DirectExecute(
                "DELETE FROM mod_naxxramas_arcane_momentum WHERE guid = {}", guid);

            ArcaneMomentumMages.erase(guid);
        }
    }
}

class NaxxramasMageArcaneMomentumPlayer : public PlayerScript
{
public:
    NaxxramasMageArcaneMomentumPlayer()
        : PlayerScript("NaxxramasMageArcaneMomentumPlayer",
          { PLAYERHOOK_ON_LOGIN, PLAYERHOOK_ON_LOGOUT })
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        if (!player || player->getClass() != CLASS_MAGE)
            return;

        uint32 guid = player->GetGUID().GetCounter();
        ArcaneMomentumMages.erase(guid);

        if (CharacterDatabase.Query(
            "SELECT guid FROM mod_naxxramas_arcane_momentum WHERE guid = {}", guid))
        {
            ArcaneMomentumMages.insert(guid);
        }
    }

    void OnPlayerLogout(Player* player) override
    {
        if (player)
            ArcaneMomentumMages.erase(player->GetGUID().GetCounter());
    }
};

class NaxxramasMageArcaneMomentumTrainer : public AllCreatureScript
{
public:
    NaxxramasMageArcaneMomentumTrainer()
        : AllCreatureScript("NaxxramasMageArcaneMomentumTrainer")
    {
    }

    bool CanCreatureGossipHello(Player* player, Creature* creature) override
    {
        if (!IsMageTrainer(player, creature))
            return false;

        // Rebuild the normal NPC menu first, so the trainer's normal
        // services, quests and other DB-defined options are preserved.
        player->PrepareGossipMenu(creature, creature->GetGossipMenuId(), true);

        AddGossipItemFor(
            player,
            GOSSIP_ICON_CHAT,
            "I want to talk about the Arcane Momentum technique.",
            GOSSIP_SENDER_MAIN,
            GOSSIP_ACTION_ARCANE_MOMENTUM_INFO);

        player->SendPreparedGossip(creature);
        return true;
    }

    bool CanCreatureGossipSelect(Player* player, Creature* creature,
                                 uint32 sender, uint32 action) override
    {
        if (sender != GOSSIP_SENDER_MAIN || !IsMageTrainer(player, creature))
            return false;

        switch (action)
        {
            case GOSSIP_ACTION_ARCANE_MOMENTUM_INFO:
            {
                ClearGossipMenuFor(player);

                if (HasArcaneMomentum(player))
                {
                    AddGossipItemFor(
                        player,
                        GOSSIP_ICON_CHAT,
                        "I would like to unlearn Arcane Momentum and Blink in the direction I am facing.",
                        GOSSIP_SENDER_MAIN,
                        GOSSIP_ACTION_ARCANE_MOMENTUM_UNLEARN,
                        "Remove Arcane Momentum and restore normal Blink?",
                        0, false);
                }
                else
                {
                    AddGossipItemFor(
                        player,
                        GOSSIP_ICON_CHAT,
                        "I would like to learn Arcane Momentum and Blink in the direction I am moving.",
                        GOSSIP_SENDER_MAIN,
                        GOSSIP_ACTION_ARCANE_MOMENTUM_LEARN,
                        "Learn Arcane Momentum and change Blink direction?",
                        0, false);
                }

                SendGossipMenuFor(player, player->GetGossipTextId(creature), creature);
                return true;
            }

            case GOSSIP_ACTION_ARCANE_MOMENTUM_LEARN:
                SetArcaneMomentum(player, true);
                CloseGossipMenuFor(player);
                if (player->GetSession())
                    ChatHandler(player->GetSession()).SendSysMessage(
                        "Arcane Momentum learned. Blink now follows your movement direction.");
                return true;

            case GOSSIP_ACTION_ARCANE_MOMENTUM_UNLEARN:
                SetArcaneMomentum(player, false);
                CloseGossipMenuFor(player);
                if (player->GetSession())
                    ChatHandler(player->GetSession()).SendSysMessage(
                        "Arcane Momentum unlearned. Blink now follows the direction you are facing.");
                return true;

            default:
                return false;
        }
    }
};

class spell_naxxramas_arcane_momentum : public SpellScript
{
    PrepareSpellScript(spell_naxxramas_arcane_momentum);

    void RedirectBlink(SpellDestination& destination)
    {
        Player* player = GetCaster() ? GetCaster()->ToPlayer() : nullptr;

        if (!player || player->getClass() != CLASS_MAGE || !HasArcaneMomentum(player))
            return;

        // Do not attempt to redirect a Blink on transports, where the
        // local/world coordinate conversion requires special handling.
        if (player->GetTransport())
            return;

        uint32 flags = player->GetUnitMovementFlags();

        float forward = 0.0f;
        float sideways = 0.0f;

        if (flags & MOVEMENTFLAG_FORWARD)
            forward += 1.0f;
        if (flags & MOVEMENTFLAG_BACKWARD)
            forward -= 1.0f;
        if (flags & MOVEMENTFLAG_STRAFE_LEFT)
            sideways -= 1.0f;
        if (flags & MOVEMENTFLAG_STRAFE_RIGHT)
            sideways += 1.0f;

        // When the Mage is not moving, retain ordinary facing-based Blink.
        if (forward == 0.0f && sideways == 0.0f)
            return;

        // Relative to the Mage's facing: forward=0, right=+pi/2,
        // backward=pi and left=-pi/2. Diagonal inputs are normalized.
        float relativeAngle = std::atan2(sideways, forward);
        float distance = GetSpellInfo()->Effects[EFFECT_0].CalcRadius(player);
        if (distance <= 0.0f)
            return;

        Position safeDestination = player->GetPosition();

        // Use AzerothCore map collision checks; never teleport a fixed
        // 20 yards blindly through obstacles.
        player->MovePositionToFirstCollision(
            safeDestination, distance, relativeAngle);

        // Fail closed on unusable or excessive height transitions.
        if (!std::isfinite(safeDestination.GetPositionX()) ||
            !std::isfinite(safeDestination.GetPositionY()) ||
            !std::isfinite(safeDestination.GetPositionZ()) ||
            std::fabs(safeDestination.GetPositionZ() - player->GetPositionZ()) > 5.0f)
        {
            safeDestination = player->GetPosition();
        }

        destination.Relocate(safeDestination);
    }

    void Register() override
    {
        OnDestinationTargetSelect += SpellDestinationTargetSelectFn(
            spell_naxxramas_arcane_momentum::RedirectBlink,
            EFFECT_0, TARGET_DEST_CASTER_FRONT_LEAP);
    }
};

void AddMageArcaneMomentumScripts()
{
    new NaxxramasMageArcaneMomentumPlayer();
    new NaxxramasMageArcaneMomentumTrainer();
    RegisterSpellScript(spell_naxxramas_arcane_momentum);
}
