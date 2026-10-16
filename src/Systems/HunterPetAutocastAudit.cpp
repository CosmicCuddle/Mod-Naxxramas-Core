/*
 * Naxxramas Core - Hunter pet autocast acceptance observer (HPA-G2)
 *
 * READ-ONLY DIAGNOSTIC. This file intentionally contains NO:
 *   ToggleAutocast / learnSpell / actionbar mutation / CharacterDatabase writes.
 *
 * CanPacketReceive fires BEFORE PetHandler performs ownership, legality and
 * autocast checks. We record a requested transition only when the native
 * state was initially different; the next Player update checks whether the
 * native handler actually changed the same pet's spell to the requested state.
 *
 * This does NOT establish that Individual Progression's delayed spell
 * reconciliation has completed. It is NOT an autocast persistence fix.
 */

#include "CharmInfo.h"
#include "Config.h"
#include "Log.h"
#include "Pet.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellMgr.h"
#include "WorldPacket.h"
#include "WorldSession.h"

#include <algorithm>

namespace
{
    constexpr char const* AUDIT_KEY = "NaxxramasCore.HunterPetAutocast.PendingChoice";

    struct PendingChoice final : DataMap::Base
    {
        ObjectGuid petGuid;
        uint32 petNumber = 0;
        uint32 spellId = 0;
        bool requestedEnabled = false;
        bool pending = false;
    };

    bool AuditEnabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.HunterPetAutocast.AuditEnabled", false);
    }

    bool NativeState(Pet const* pet, uint32 spellId, bool& enabled)
    {
        if (!pet || !pet->HasSpell(spellId))
            return false;

        auto const found = pet->m_spells.find(spellId);
        if (found == pet->m_spells.end())
            return false;

        if (found->second.active != ACT_ENABLED &&
            found->second.active != ACT_DISABLED)
            return false;

        enabled = found->second.active == ACT_ENABLED;
        auto const active = std::find(
            pet->m_autospells.begin(), pet->m_autospells.end(), spellId);
        return (active != pet->m_autospells.end()) == enabled;
    }

    // This callback is invoked before the core receives the command, so
    // simply seeing a packet must NOT be counted as a confirmed choice.
    class HunterPetAutocastPacketObserver final : public ServerScript
    {
    public:
        HunterPetAutocastPacketObserver()
            : ServerScript("NaxxramasHunterPetAutocastPacketObserver",
                {SERVERHOOK_CAN_PACKET_RECEIVE}) { }

        bool CanPacketReceive(WorldSession* session,
            WorldPacket const& packet) override
        {
            if (packet.GetOpcode() != CMSG_PET_SPELL_AUTOCAST ||
                !AuditEnabled() || !session)
                return true;

            Player* owner = session->GetPlayer();
            if (!owner || owner->getClass() != CLASS_HUNTER ||
                !owner->IsInWorld() || packet.size() != 13)
                return true;

            // CMSG_PET_SPELL_AUTOCAST native layout:
            // ObjectGuid(8), SpellID(uint32), bool(uint8).
            // A copy prevents advancing the original handler's cursor.
            WorldPacket copy(packet);
            copy.rpos(0);
            ObjectGuid petGuid;
            uint32 spellId = 0;
            uint8 enabledByte = 0;
            copy >> petGuid >> spellId >> enabledByte;
            if (enabledByte > 1)
                return true;

            Pet* pet = owner->GetPet();
            if (!pet || pet->getPetType() != HUNTER_PET ||
                pet->GetGUID() != petGuid || pet->isBeingLoaded() ||
                !pet->GetCharmInfo())
                return true;

            SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
            if (!info || !info->IsAutocastable())
                return true;

            bool beforeEnabled = false;
            if (!NativeState(pet, spellId, beforeEnabled) ||
                beforeEnabled == (enabledByte != 0))
                return true; // unchanged state does not prove acceptance

            PendingChoice* pending =
                owner->CustomData.GetDefault<PendingChoice>(AUDIT_KEY);
            pending->petGuid = petGuid;
            pending->petNumber = pet->GetCharmInfo()->GetPetNumber();
            pending->spellId = spellId;
            pending->requestedEnabled = enabledByte != 0;
            pending->pending = true;

            return true; // never intercept or modify client's packet
        }
    };

    class HunterPetAutocastUpdateObserver final : public PlayerScript
    {
    public:
        HunterPetAutocastUpdateObserver()
            : PlayerScript("NaxxramasHunterPetAutocastUpdateObserver",
                {PLAYERHOOK_ON_AFTER_UPDATE}) { }

        void OnPlayerAfterUpdate(Player* owner, uint32 /*diff*/) override
        {
            if (!AuditEnabled() || !owner ||
                owner->getClass() != CLASS_HUNTER)
                return;

            PendingChoice* choice =
                owner->CustomData.Get<PendingChoice>(AUDIT_KEY);
            if (!choice || !choice->pending)
                return;

            // One-shot; do not persist stale candidates across load/relog.
            choice->pending = false;

            Pet* pet = owner->GetPet();
            if (!pet || pet->getPetType() != HUNTER_PET ||
                pet->GetGUID() != choice->petGuid ||
                pet->isBeingLoaded() || !pet->GetCharmInfo() ||
                pet->GetCharmInfo()->GetPetNumber() != choice->petNumber)
                return;

            bool confirmedEnabled = false;
            if (!NativeState(pet, choice->spellId, confirmedEnabled) ||
                confirmedEnabled != choice->requestedEnabled)
                return;

            // A confirmed *transition*, not merely a received packet.
            // Do not record/save the user's preference yet: staging must
            // establish safe persistent pet identity and IP timing first.
            LOG_INFO("module",
                "HunterPetAutocast AUDIT ONLY: owner={} petnumber={} "
                "spell={} requested={} native=confirmed; no mutation",
                owner->GetGUID().GetCounter(), choice->petNumber,
                choice->spellId, choice->requestedEnabled ? "ON" : "OFF");
        }
    };
}

void AddHunterPetAutocastAuditScripts()
{
    new HunterPetAutocastPacketObserver();
    new HunterPetAutocastUpdateObserver();
}
