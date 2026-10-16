/*
 * Naxxramas Core - Hunter pet autocast acceptance observer (HPA-G2)
 *
 * READ-ONLY DIAGNOSTIC. This file intentionally contains NO:
 *   ToggleAutocast / learnSpell / actionbar mutation / CharacterDatabase writes.
 *
 * Both observed CMSG packet types are only candidate player commands.
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
#include "Duration.h"
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
    constexpr char const* PHASE_KEY = "NaxxramasCore.HunterPetAutocast.LifecycleProbe";
    constexpr char const* LEARN_KEY = "NaxxramasCore.HunterPetAutocast.LearnPacketProbe";

    // A packet is observable even for a headless bot session on the
    // pinned WorldSession::SendPacket path, but that does NOT prove the
    // Playerbot runtime sent it in an actual scenario.
    struct LearnPacketProbe final : DataMap::Base
    {
        uint32 pendingSpell = 0;
    };

    bool AuditEnabled();

    // Runtime-only per-Pet sample; attached to a Pet object so it cannot
    // outlive that instance or accidentally address a new pet with the
    // same persistent PetNumber.
    struct LifecycleProbe final : DataMap::Base
    {
        uint32 elapsedMs = 0;
        uint32 initialBarSpell = 0;
        ActiveStates initialBarState = ACT_PASSIVE;
        bool initialLoading = false;
        bool loadFinishedObserved = false;
        bool reported = false;
        bool eventClockProbeScheduled = false;
    };

    // Read the first Lightning Breath rank 5/6 actionbar entry for the
    // narrow Wind Serpent pilot. This is observation only, not a rank
    // entitlement check or a final hardcoded restoration algorithm.
    void ObserveLightningBreathBar(Pet* pet, uint32& spell,
        ActiveStates& state)
    {
        spell = 0;
        state = ACT_PASSIVE;
        CharmInfo* bar = pet ? pet->GetCharmInfo() : nullptr;
        if (!bar)
            return;

        for (uint8 slot = 0; slot < MAX_UNIT_ACTION_BAR_INDEX; ++slot)
        {
            UnitActionBarEntry const* entry = bar->GetActionBarEntry(slot);
            if (!entry || !entry->IsActionBarForSpell())
                continue;

            uint32 const candidate = entry->GetAction();
            if (candidate != 25011 && candidate != 25012)
                continue;

            spell = candidate;
            state = entry->GetType();
            break;
        }
    }

    class HunterPetAutocastLifecycleObserver final : public PetScript
    {
    public:
        HunterPetAutocastLifecycleObserver()
            : PetScript("NaxxramasHunterPetAutocastLifecycleObserver",
                {PETHOOK_ON_PET_ADD_TO_WORLD}) { }

        void OnPetAddToWorld(Pet* pet) override
        {
            if (!AuditEnabled() || !pet || pet->getPetType() != HUNTER_PET)
                return;

            Player* owner = pet->GetOwner();
            if (!owner || owner->getClass() != CLASS_HUNTER)
                return;

            LifecycleProbe* sample = pet->CustomData.GetDefault<LifecycleProbe>(
                PHASE_KEY);
            sample->elapsedMs = 0;
            sample->loadFinishedObserved = false;
            sample->reported = false;
            sample->initialLoading = pet->isBeingLoaded();
            ObserveLightningBreathBar(pet, sample->initialBarSpell,
                sample->initialBarState);

            LOG_INFO("module",
                "HunterPetAutocast LIFECYCLE audit: on-add owner={} petnumber={} "
                "loading={} barLB={} barState={} knownR5={} knownR6={}",
                owner->GetGUID().GetCounter(),
                pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
                sample->initialLoading, sample->initialBarSpell,
                uint32(sample->initialBarState),
                pet->HasSpell(25011), pet->HasSpell(25012));

            // The pinned IP delay and this audit marker share the PET's
            // event clock, not the player's update clock. It is ONE
            // diagnostic sample per Pet object, never a readiness token.
            // The lambda lives in the pet-owned event queue and dies with it.
            if (!sample->eventClockProbeScheduled)
            {
                sample->eventClockProbeScheduled = true;
                pet->m_Events.AddEventAtOffset([pet]()
                {
                    if (!AuditEnabled() || !pet->IsInWorld() ||
                        pet->getPetType() != HUNTER_PET)
                        return;

                    Player* currentOwner = pet->GetOwner();
                    LifecycleProbe* probe =
                        pet->CustomData.Get<LifecycleProbe>(PHASE_KEY);
                    if (!currentOwner ||
                        currentOwner->getClass() != CLASS_HUNTER || !probe)
                        return;

                    uint32 nowBarSpell = 0;
                    ActiveStates nowBarState = ACT_PASSIVE;
                    ObserveLightningBreathBar(pet, nowBarSpell, nowBarState);
                    LOG_INFO("module",
                        "HunterPetAutocast PET-EVENT-CLOCK audit: "
                        "owner={} petnumber={} loading={} "
                        "onAddBarLB={} onAddBarState={} "
                        "clockBarLB={} clockBarState={} knownR5={} knownR6={}; "
                        "one-shot pet queue sample; NOT proof IP completed",
                        currentOwner->GetGUID().GetCounter(),
                        pet->GetCharmInfo() ?
                            pet->GetCharmInfo()->GetPetNumber() : 0,
                        pet->isBeingLoaded(),
                        probe->initialBarSpell, uint32(probe->initialBarState),
                        nowBarSpell, uint32(nowBarState),
                        pet->HasSpell(25011), pet->HasSpell(25012));
                }, Milliseconds(2500));
            }
        }
    };

    // This function is called only while AuditEnabled=1 and the owner has
    // a pending, finite-lifetime probe; it NEVER signals IP completion.
    void ObserveLifecycle(Player* owner, uint32 diff)
    {
        Pet* pet = owner->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET)
            return;

        LifecycleProbe* sample = pet->CustomData.Get<LifecycleProbe>(PHASE_KEY);
        if (!sample || sample->reported)
            return;

        sample->elapsedMs += std::min(diff, uint32(10000));

        if (!sample->loadFinishedObserved && !pet->isBeingLoaded())
        {
            sample->loadFinishedObserved = true;
            LOG_INFO("module",
                "HunterPetAutocast LIFECYCLE audit: native-load-flag-cleared "
                "owner={} petnumber={} atMs={} knownR5={} knownR6={}; "
                "NOT proof IP reconciliation has run",
                owner->GetGUID().GetCounter(),
                pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
                sample->elapsedMs, pet->HasSpell(25011), pet->HasSpell(25012));
        }

        // Take one finite post-load snapshot, rather than scan forever.
        // Time elapsed is evidence for staging, NOT a readiness guarantee.
        if (sample->elapsedMs < 3000 ||
            (pet->isBeingLoaded() && sample->elapsedMs < 10000))
            return;

        uint32 laterSpell = 0;
        ActiveStates laterState = ACT_PASSIVE;
        ObserveLightningBreathBar(pet, laterSpell, laterState);
        sample->reported = true;
        LOG_INFO("module",
            "HunterPetAutocast LIFECYCLE audit: snapshot owner={} "
            "petnumber={} atMs={} loading={} onAddBarLB={} "
            "onAddBarState={} nowBarLB={} nowBarState={} "
            "knownR5={} knownR6={} r5Autocast={} r6Autocast={}; "
            "NO IP completion asserted; no change applied",
            owner->GetGUID().GetCounter(),
            pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
            sample->elapsedMs, pet->isBeingLoaded(),
            sample->initialBarSpell, uint32(sample->initialBarState),
            laterSpell, uint32(laterState),
            pet->HasSpell(25011), pet->HasSpell(25012),
            std::find(pet->m_autospells.begin(), pet->m_autospells.end(),
                25011) != pet->m_autospells.end(),
            std::find(pet->m_autospells.begin(), pet->m_autospells.end(),
                25012) != pet->m_autospells.end());
    }

    struct PendingChoice final : DataMap::Base
    {
        ObjectGuid petGuid;
        uint32 petNumber = 0;
        uint32 spellId = 0;
        bool requestedEnabled = false;
        bool pending = false;
        uint8 barSlot = MAX_UNIT_ACTION_BAR_INDEX; // only for SET_ACTION
        char const* origin = "CMSG_PET_SPELL_AUTOCAST";
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

    // Pet::learnSpell emits SMSG_PET_LEARNED_SPELL when not loading,
    // including during IP's successful re-learn of a legal Hunter rank.
    // This observes evidence of a re-learn; it cannot identify IP as
    // the sender or assert that the whole IP reconciliation has ended.
    class HunterPetAutocastLearnPacketObserver final : public ServerScript
    {
    public:
        HunterPetAutocastLearnPacketObserver()
            : ServerScript("NaxxramasHunterPetAutocastLearnPacketObserver",
                {SERVERHOOK_ON_PACKET_SENT}) { }

        void OnPacketSent(WorldSession* session,
            WorldPacket const& packet) override
        {
            if (packet.GetOpcode() != SMSG_PET_LEARNED_SPELL ||
                !AuditEnabled() || !session || packet.size() != 4)
                return;

            Player* owner = session->GetPlayer();
            if (!owner || owner->getClass() != CLASS_HUNTER)
                return;

            WorldPacket copy(packet);
            copy.rpos(0);
            uint32 spellId = 0;
            copy >> spellId;

            // Pilot ranks only; a future generic implementation will
            // use validated rank chains and individual IP eligibility.
            if (spellId != 25011 && spellId != 25012)
                return;

            Pet* pet = owner->GetPet();
            if (!pet || pet->getPetType() != HUNTER_PET ||
                pet->isBeingLoaded() || !pet->HasSpell(spellId))
                return;

            LearnPacketProbe* sample =
                pet->CustomData.GetDefault<LearnPacketProbe>(LEARN_KEY);
            sample->pendingSpell = spellId;

            LOG_INFO("module",
                "HunterPetAutocast LEARN-PACKET audit: owner={} "
                "petnumber={} learnedSpell={} observed; "
                "origin may be IP or another legal learn path",
                owner->GetGUID().GetCounter(),
                pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
                spellId);
        }
    };

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
            pending->barSlot = MAX_UNIT_ACTION_BAR_INDEX;
            pending->origin = "CMSG_PET_SPELL_AUTOCAST";
            pending->pending = true;

            return true; // never intercept or modify client's packet
        }
    };


    // The pinned native handler interprets 16 bytes as a single slot update
    // and 24 bytes as a two-slot command/move. Ignore two-slot/move packets.
    // Only a same-slot, same-spell enabled/disabled transition is a candidate;
    // moving or adding a spell is NOT evidence of explicit autocast intent.
    class HunterPetAutocastActionBarObserver final : public ServerScript
    {
    public:
        HunterPetAutocastActionBarObserver()
            : ServerScript("NaxxramasHunterPetAutocastActionBarObserver",
                {SERVERHOOK_CAN_PACKET_RECEIVE}) { }

        bool CanPacketReceive(WorldSession* session,
            WorldPacket const& packet) override
        {
            if (packet.GetOpcode() != CMSG_PET_SET_ACTION ||
                !AuditEnabled() || !session || packet.size() != 16)
                return true;

            Player* owner = session->GetPlayer();
            if (!owner || owner->getClass() != CLASS_HUNTER ||
                !owner->IsInWorld())
                return true;

            WorldPacket copy(packet);
            copy.rpos(0);
            ObjectGuid petGuid;
            uint32 position = 0;
            uint32 packedData = 0;
            copy >> petGuid >> position >> packedData;

            // Refuse command/reaction slots and two-slot rearrangements.
            if (position < ACTION_BAR_INDEX_PET_SPELL_START ||
                position >= ACTION_BAR_INDEX_PET_SPELL_END)
                return true;

            uint32 const spellId = UNIT_ACTION_BUTTON_ACTION(packedData);
            uint8 const requestedType = UNIT_ACTION_BUTTON_TYPE(packedData);
            if (requestedType != ACT_ENABLED && requestedType != ACT_DISABLED)
                return true;
            bool const requestedEnabled = requestedType == ACT_ENABLED;

            Pet* pet = owner->GetPet();
            if (!pet || pet->getPetType() != HUNTER_PET ||
                pet->GetGUID() != petGuid || pet->isBeingLoaded() ||
                !pet->GetCharmInfo())
                return true;

            UnitActionBarEntry const* beforeBar =
                pet->GetCharmInfo()->GetActionBarEntry(uint8(position));
            if (!beforeBar || !beforeBar->IsActionBarForSpell() ||
                beforeBar->GetAction() != spellId)
                return true;

            SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
            if (!info || !info->IsAutocastable())
                return true;

            bool beforeEnabled = false;
            if (!NativeState(pet, spellId, beforeEnabled) ||
                beforeEnabled == requestedEnabled ||
                beforeBar->GetType() !=
                    (beforeEnabled ? ACT_ENABLED : ACT_DISABLED))
                return true;

            PendingChoice* pending =
                owner->CustomData.GetDefault<PendingChoice>(AUDIT_KEY);
            pending->petGuid = petGuid;
            pending->petNumber = pet->GetCharmInfo()->GetPetNumber();
            pending->spellId = spellId;
            pending->requestedEnabled = requestedEnabled;
            pending->barSlot = uint8(position);
            pending->origin = "CMSG_PET_SET_ACTION";
            pending->pending = true;

            return true; // read-only; native handler owns all validation
        }
    };

    class HunterPetAutocastUpdateObserver final : public PlayerScript
    {
    public:
        HunterPetAutocastUpdateObserver()
            : PlayerScript("NaxxramasHunterPetAutocastUpdateObserver",
                {PLAYERHOOK_ON_AFTER_UPDATE}) { }

        void OnPlayerAfterUpdate(Player* owner, uint32 diff) override
        {
            if (!AuditEnabled() || !owner ||
                owner->getClass() != CLASS_HUNTER)
                return;

            ObserveLifecycle(owner, diff);

            // Inspect the same pet's still-known rank during a subsequent
            // update, without executing any action. A packet alone does
            // not prove completion of IP's delayed reconciliation.
            if (Pet* pet = owner->GetPet())
            {
                LearnPacketProbe* learned =
                    pet->CustomData.Get<LearnPacketProbe>(LEARN_KEY);
                if (learned && learned->pendingSpell != 0)
                {
                    uint32 const spellId = learned->pendingSpell;
                    learned->pendingSpell = 0;
                    LOG_INFO("module",
                        "HunterPetAutocast LEARN-PACKET audit: "
                        "next-update owner={} spell={} stillKnown={} "
                        "loading={}; no autocast restoration",
                        owner->GetGUID().GetCounter(), spellId,
                        pet->HasSpell(spellId), pet->isBeingLoaded());
                }
            }

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

            if (choice->barSlot < MAX_UNIT_ACTION_BAR_INDEX)
            {
                UnitActionBarEntry const* bar =
                    pet->GetCharmInfo()->GetActionBarEntry(choice->barSlot);
                if (!bar || !bar->IsActionBarForSpell() ||
                    bar->GetAction() != choice->spellId ||
                    bar->GetType() !=
                        (choice->requestedEnabled ? ACT_ENABLED : ACT_DISABLED))
                    return;
            }

            // A confirmed *transition*, not merely a received packet.
            // Do not record/save the user's preference yet: staging must
            // establish safe persistent pet identity and IP timing first.
            LOG_INFO("module",
                "HunterPetAutocast AUDIT ONLY: owner={} petnumber={} "
                "spell={} requested={} source={} native=matching-state-only; actor not attributable; no mutation",
                owner->GetGUID().GetCounter(), choice->petNumber,
                choice->spellId, choice->requestedEnabled ? "ON" : "OFF",
                choice->origin);
        }
    };
}

void AddHunterPetAutocastAuditScripts()
{
    new HunterPetAutocastPacketObserver();
    new HunterPetAutocastActionBarObserver();
    new HunterPetAutocastLearnPacketObserver();
    new HunterPetAutocastLifecycleObserver();
    new HunterPetAutocastUpdateObserver();
}
