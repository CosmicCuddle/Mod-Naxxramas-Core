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
#include <map>
#include <string>
#include <vector>

namespace
{
    constexpr char const* AUDIT_KEY = "NaxxramasCore.HunterPetAutocast.PendingChoice";
    constexpr char const* PHASE_KEY = "NaxxramasCore.HunterPetAutocast.LifecycleProbe";
    constexpr char const* LEARN_KEY = "NaxxramasCore.HunterPetAutocast.LearnPacketProbe";
    constexpr char const* REVIVE_KEY = "NaxxramasCore.HunterPetAutocast.ReviveProbe";
    constexpr char const* STABILITY_KEY = "NaxxramasCore.HunterPetAutocast.SpellStabilityProbe";
    constexpr char const* POST_EVENT_KEY = "NaxxramasCore.HunterPetAutocast.PostEventTickProbe";

    // A packet is observable even for a headless bot session on the
    // pinned WorldSession::SendPacket path, but that does NOT prove the
    // Playerbot runtime sent it in an actual scenario.
    constexpr size_t MAX_LEARNED_AUDIT_QUEUE = 32;
    constexpr size_t MAX_TOGGLE_AUDIT_QUEUE = 32;
    constexpr size_t MAX_STABILITY_SPELLS = 64;
    constexpr uint8 MAX_STABILITY_SAMPLES = 10;

    struct LearnPacketProbe final : DataMap::Base
    {
        std::vector<uint32> pendingSpells;
    };

    bool AuditEnabled();

    // Matches the pinned IP GetPlayerProgressionFromQuests scan, but does
    // NOT read IP config, account classification, dummies or event state.
    // "unavailable" must never become an assumed stage zero.
    std::string DescribeOwnerRawRewardedStage(Player* owner)
    {
        if (!owner || !owner->IsInWorld())
            return "unavailable";

        uint8 highest = 0;
        for (uint32 tier = 1; tier <= 18; ++tier)
            if (owner->GetQuestStatus(66000 + tier) == QUEST_STATUS_REWARDED)
                highest = uint8(tier);
        return std::to_string(highest);
    }

    // Runtime-only per-Pet sample; attached to a Pet object so it cannot
    // outlive that instance or accidentally address a new pet with the
    // same persistent PetNumber.
    struct LifecycleProbe final : DataMap::Base
    {
        uint32 elapsedMs = 0;
        uint32 initialBarSpell = 0;
        ActiveStates initialBarState = ACT_PASSIVE;
        std::string initialGenericAutocast;
        bool initialLoading = false;
        std::string rawRewardedStageAtAdd = "unavailable";
        bool loadFinishedObserved = false;
        bool reported = false;
        bool eventClockProbeScheduled = false;
    };

    // Only a bounded number of death -> revive transitions are reported per
    // actual pet object. No Playerbot or IP-ready inference is made.
    struct ReviveProbe final : DataMap::Base
    {
        bool initialized = false;
        bool lastAlive = false;
        bool sawDeath = false;
        uint8 observations = 0;
        uint32 revivalSequence = 0;
        std::string beforeRevive;
    };

    // Bounded post-WorldObject-event-loop observations for ONE Pet object.
    // This is a queue scheduling diagnostic, NEVER an IP completion token.
    struct PostEventTickProbe final : DataMap::Base
    {
        uint8 samples = 0;
    };

    // Per actual Pet object, finite diagnostic samples of each native
    // autocast-capable ability family. No preference or readiness state.
    struct StabilityProbe final : DataMap::Base
    {
        uint32 intervalMs = 0;
        uint8 samples = 0;
        uint8 unchangedSamples = 0;
        bool finished = false;
        bool initialized = false;
        std::map<uint32, std::string> lastFamilyStates;
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


    // Compact, bounded observation of ALL native autocast-capable Hunter
    // pet spells, not a list of spells the module may legally restore.
    std::string DescribeHunterPetAutocast(Pet* pet)
    {
        if (!pet)
            return "no-pet";
        auto familyOf = [](uint32 id)
        {
            uint32 const first = sSpellMgr->GetFirstSpellInChain(id);
            return first ? first : id;
        };
        std::string out = "bar[";
        if (CharmInfo* charm = pet->GetCharmInfo())
        {
            for (uint8 slot = ACTION_BAR_INDEX_PET_SPELL_START;
                 slot < ACTION_BAR_INDEX_PET_SPELL_END; ++slot)
            {
                UnitActionBarEntry const* entry = charm->GetActionBarEntry(slot);
                if (!entry || !entry->IsActionBarForSpell() || !entry->GetAction())
                    continue;
                uint32 const id = entry->GetAction();
                SpellInfo const* info = sSpellMgr->GetSpellInfo(id);
                if (!info || !info->IsAutocastable())
                    continue;
                out += std::to_string(slot) + ":" + std::to_string(id) + "/" +
                    std::to_string(familyOf(id)) + "/" +
                    std::to_string(uint32(entry->GetType())) + ",";
            }
        }
        out += "] known[";
        std::vector<uint32> known;
        for (auto const& spell : pet->m_spells)
        {
            uint32 const id = spell.first;
            SpellInfo const* info = sSpellMgr->GetSpellInfo(id);
            if (pet->HasSpell(id) && info && info->IsAutocastable())
                known.push_back(id);
        }
        std::sort(known.begin(), known.end());
        size_t const maxEntries = std::min(known.size(), size_t(64));
        for (size_t i = 0; i < maxEntries; ++i)
        {
            uint32 const id = known[i];
            auto const spell = pet->m_spells.find(id);
            bool const listed = std::find(pet->m_autospells.begin(),
                pet->m_autospells.end(), id) != pet->m_autospells.end();
            out += std::to_string(id) + "/" + std::to_string(familyOf(id)) +
                "/" + std::to_string(uint32(spell->second.active)) + "/" +
                (listed ? "1" : "0") + ",";
        }
        if (known.size() > maxEntries)
            out += "truncated,";
        out += "]";
        return out;
    }

    // Full state per spell family, including known spell rank, native active
    // flag, m_autospells and actionbar slot/type. This is not IP entitlement.
    // Return false when truncated; a partial sample must not look stable.
    bool CaptureAbilityFamilyStates(Pet* pet,
        std::map<uint32, std::string>& states)
    {
        states.clear();
        if (!pet || !pet->GetCharmInfo())
            return false;

        // PetSpellMap is std::unordered_map in pinned AzerothCore.
        // Canonical spell-ID ordering prevents spurious family diffs after
        // hash table iteration/reallocation while the actual state agrees.
        std::vector<uint32> knownSpells;
        for (auto const& entry : pet->m_spells)
        {
            uint32 const id = entry.first;
            SpellInfo const* info = sSpellMgr->GetSpellInfo(id);
            if (!pet->HasSpell(id) || !info || !info->IsAutocastable())
                continue;
            if (knownSpells.size() >= MAX_STABILITY_SPELLS)
                return false;
            knownSpells.push_back(id);
        }
        std::sort(knownSpells.begin(), knownSpells.end());

        for (uint32 const id : knownSpells)
        {
            auto const spell = pet->m_spells.find(id);
            uint32 const firstRank = sSpellMgr->GetFirstSpellInChain(id);
            uint32 const family = firstRank ? firstRank : id;
            bool const listed = std::find(pet->m_autospells.begin(),
                pet->m_autospells.end(), id) != pet->m_autospells.end();
            uint32 slot = MAX_UNIT_ACTION_BAR_INDEX;
            uint32 type = ACT_PASSIVE;
            for (uint8 index = ACTION_BAR_INDEX_PET_SPELL_START;
                index < ACTION_BAR_INDEX_PET_SPELL_END; ++index)
            {
                UnitActionBarEntry const* bar =
                    pet->GetCharmInfo()->GetActionBarEntry(index);
                if (bar && bar->IsActionBarForSpell() &&
                    bar->GetAction() == id)
                {
                    slot = index;
                    type = uint32(bar->GetType());
                    break;
                }
            }
            states[family] += std::to_string(id) + "/" +
                std::to_string(uint32(spell->second.active)) + "/" +
                (listed ? "1" : "0") + "/" + std::to_string(slot) + "/" +
                std::to_string(type) + ",";
        }
        return true;
    }

    void ObserveAbilityStability(Player* owner, uint32 diff)
    {
        Pet* pet = owner->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET)
            return;

        StabilityProbe* sample =
            pet->CustomData.GetDefault<StabilityProbe>(STABILITY_KEY);
        if (sample->finished)
            return;

        // Finite maximum of ten snapshots per actual Pet, one per
        // 750ms of Player updates. This is NOT the IP event clock.
        sample->intervalMs += std::min(diff, uint32(10000));
        if (sample->intervalMs < 750)
            return;
        sample->intervalMs = 0;

        std::map<uint32, std::string> current;
        if (!CaptureAbilityFamilyStates(pet, current))
        {
            sample->finished = true;
            LOG_INFO("module",
                "HunterPetAutocast STABILITY audit: owner={} "
                "sample unavailable/truncated; NO IP readiness inferred",
                owner->GetGUID().GetCounter());
            return;
        }

        ++sample->samples;
        if (sample->initialized)
        {
            bool const unchanged = sample->lastFamilyStates == current;
            sample->unchangedSamples =
                unchanged ? uint8(sample->unchangedSamples + 1) : 0;

            // Only log changed families to distinguish Bite from Growl.
            std::map<uint32, std::string> changes = sample->lastFamilyStates;
            for (auto const& [family, state] : current)
                changes.emplace(family, state);
            for (auto const& [family, previous] : changes)
            {
                auto before = sample->lastFamilyStates.find(family);
                auto after = current.find(family);
                std::string const prior = before == sample->lastFamilyStates.end()
                    ? "absent" : before->second;
                std::string const now = after == current.end()
                    ? "absent" : after->second;
                if (prior != now)
                {
                    LOG_INFO("module",
                        "HunterPetAutocast STABILITY audit: owner={} "
                        "family={} before={} after={} loading={}; "
                        "observed change ONLY; not IP completion",
                        owner->GetGUID().GetCounter(), family, prior, now,
                        pet->isBeingLoaded());
                }
            }
        }
        else
            sample->initialized = true;

        sample->lastFamilyStates.swap(current);
        if (sample->samples >= MAX_STABILITY_SAMPLES)
        {
            sample->finished = true;
            LOG_INFO("module",
                "HunterPetAutocast STABILITY audit: owner={} samples={} "
                "lastUnchangedRun={} families={} loading={}; "
                "unchanged state is NOT proof IP completed; NO restore",
                owner->GetGUID().GetCounter(), uint32(sample->samples),
                uint32(sample->unchangedSamples),
                sample->lastFamilyStates.size(), pet->isBeingLoaded());
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
            sample->rawRewardedStageAtAdd = DescribeOwnerRawRewardedStage(owner);
            LOG_INFO("module",
                "HunterPetAutocast QUEST-STAGE audit: owner={} "
                "onAddRawRewardedTier={}; no IP config, dummy, bot "
                "or completion inference; no changes applied",
                owner->GetGUID().GetCounter(),
                sample->rawRewardedStageAtAdd);
            ObserveLightningBreathBar(pet, sample->initialBarSpell,
                sample->initialBarState);
            sample->initialGenericAutocast = DescribeHunterPetAutocast(pet);

            LOG_INFO("module",
                "HunterPetAutocast LIFECYCLE audit: on-add owner={} petnumber={} "
                "loading={} barLB={} barState={} knownR5={} knownR6={}",
                owner->GetGUID().GetCounter(),
                pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
                sample->initialLoading, sample->initialBarSpell,
                uint32(sample->initialBarState),
                pet->HasSpell(25011), pet->HasSpell(25012));

            LOG_INFO("module",
                "HunterPetAutocast GENERIC audit: on-add owner={} petnumber={} "
                "autocast={} (read only; not IP eligibility)",
                owner->GetGUID().GetCounter(),
                pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
                sample->initialGenericAutocast);

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
                    LOG_INFO("module",
                        "HunterPetAutocast GENERIC audit: pet-clock owner={} "
                        "autocast={} (not IP completion)",
                        currentOwner->GetGUID().GetCounter(),
                        DescribeHunterPetAutocast(pet));
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
            "HunterPetAutocast QUEST-STAGE audit: later owner={} "
            "onAddRawRewardedTier={} laterRawRewardedTier={}; "
            "not authoritative IP rank eligibility or completion",
            owner->GetGUID().GetCounter(),
            sample->rawRewardedStageAtAdd,
            DescribeOwnerRawRewardedStage(owner));
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
        LOG_INFO("module",
            "HunterPetAutocast GENERIC audit: later owner={} "
            "before={} after={} (not IP completion)",
            owner->GetGUID().GetCounter(),
            sample->initialGenericAutocast,
            DescribeHunterPetAutocast(pet));
    }

    // Source-backed normal death callback. The Player observer remains
    // fallback for unusual deaths that may bypass UnitScript::OnUnitDeath.
    void RecordObservedPetDeath(Pet* pet)
    {
        ReviveProbe* state = pet->CustomData.GetDefault<ReviveProbe>(REVIVE_KEY);
        if (state->initialized && !state->lastAlive && state->sawDeath)
            return; // same death observed twice, do not bump generation

        state->initialized = true;
        state->lastAlive = false;
        state->sawDeath = true;
        ++state->revivalSequence; // invalidates previous pet-clock sample
        if (state->observations < 4)
            state->beforeRevive = DescribeHunterPetAutocast(pet);
    }

    // Pinned WorldObject::Update runs m_Events.Update BEFORE this script
    // callback. Pet::Update normally returns while m_loading, so the
    // callback is absent for those ordinary loading-time Pet::Update calls.
    // Neither queue emptiness nor reaching here identifies an IP event.
    class HunterPetAutocastPostEventObserver final : public WorldObjectScript
    {
    public:
        HunterPetAutocastPostEventObserver()
            : WorldObjectScript("NaxxramasHunterPetAutocastPostEventObserver",
                {WORLDOBJECTHOOK_ON_WORLD_OBJECT_UPDATE}) { }

        void OnWorldObjectUpdate(WorldObject* object, uint32 /*diff*/) override
        {
            if (!AuditEnabled() || !object)
                return;

            Unit* unit = object->ToUnit();
            Pet* pet = unit ? unit->ToPet() : nullptr;
            if (!pet || pet->getPetType() != HUNTER_PET)
                return;

            Player* owner = pet->GetOwner();
            if (!owner || owner->getClass() != CLASS_HUNTER ||
                owner->GetPet() != pet)
                return;

            PostEventTickProbe* probe =
                pet->CustomData.GetDefault<PostEventTickProbe>(POST_EVENT_KEY);
            if (probe->samples >= 4)
                return;

            ++probe->samples;
            LOG_INFO("module",
                "HunterPetAutocast POST-PET-EVENT-TICK audit: owner={} "
                "petnumber={} sample={} nativeQueueHasEvents={} loading={}; "
                "AFTER this Pet event tick only; queue status is NOT IP "
                "completion; no toggle, SQL or actionbar changes",
                owner->GetGUID().GetCounter(),
                pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
                uint32(probe->samples), pet->m_Events.HasEvents(),
                pet->isBeingLoaded());
        }
    };

    class HunterPetAutocastDeathObserver final : public UnitScript
    {
    public:
        HunterPetAutocastDeathObserver()
            : UnitScript("NaxxramasHunterPetAutocastDeathObserver", true,
                {UNITHOOK_ON_UNIT_DEATH}) { }

        void OnUnitDeath(Unit* victim, Unit* /*killer*/) override
        {
            if (!AuditEnabled() || !victim)
                return;
            Pet* pet = victim->ToPet();
            if (!pet || pet->getPetType() != HUNTER_PET)
                return;
            Player* owner = pet->GetOwner();
            if (!owner || owner->getClass() != CLASS_HUNTER ||
                owner->GetPet() != pet)
                return;
            RecordObservedPetDeath(pet);
        }
    };

    // Read-only. Some Hunter pets revive without OnPetAddToWorld. This
    // samples only an existing, actively owned Pet from PlayerAfterUpdate;
    // a death/revive fully between updates may be missed. NOT a restore hook.
    void ObserveRevival(Player* owner)
    {
        Pet* pet = owner->GetPet();
        if (!pet || pet->getPetType() != HUNTER_PET ||
            pet->isBeingLoaded())
            return;

        ReviveProbe* probe = pet->CustomData.GetDefault<ReviveProbe>(REVIVE_KEY);
        bool const alive = pet->IsAlive();
        if (!probe->initialized)
        {
            probe->initialized = true;
            probe->lastAlive = alive;
            // The first audit tick can find a pet already dead. Preserve
            // that observation so its next visible revival is not missed.
            if (!alive)
                RecordObservedPetDeath(pet);
            return;
        }

        if (probe->lastAlive == alive)
            return;

        probe->lastAlive = alive;
        if (!alive)
        {
            RecordObservedPetDeath(pet);
            return;
        }

        if (!probe->sawDeath)
            return;
        probe->sawDeath = false;

        // No repeated log or event scheduling after four observed revivals.
        if (probe->observations >= 4)
            return;
        ++probe->observations;
        uint32 const sequence = probe->revivalSequence;
        LOG_INFO("module",
            "HunterPetAutocast REVIVE audit: owner={} petnumber={} "
            "observedRevive={} loading={} deadSnapshot={} aliveSnapshot={}; "
            "NOT proof IP completed; no autocast change",
            owner->GetGUID().GetCounter(),
            pet->GetCharmInfo() ? pet->GetCharmInfo()->GetPetNumber() : 0,
            uint32(probe->observations), pet->isBeingLoaded(),
            probe->beforeRevive, DescribeHunterPetAutocast(pet));

        // The event belongs to THIS Pet and cannot follow a new tame.
        // A new death/revive invalidates any older deferred observation.
        pet->m_Events.AddEventAtOffset([pet, sequence]()
        {
            if (!AuditEnabled() || !pet->IsInWorld() ||
                pet->getPetType() != HUNTER_PET || !pet->IsAlive())
                return;
            ReviveProbe* state = pet->CustomData.Get<ReviveProbe>(REVIVE_KEY);
            Player* currentOwner = pet->GetOwner();
            if (!state || state->revivalSequence != sequence ||
                !currentOwner || currentOwner->GetPet() != pet)
                return;

            LOG_INFO("module",
                "HunterPetAutocast REVIVE audit: pet-clock owner={} "
                "reviveSeq={} loading={} allAuto={}; "
                "NOT proof IP completed; no autocast change",
                currentOwner->GetGUID().GetCounter(), sequence,
                pet->isBeingLoaded(), DescribeHunterPetAutocast(pet));
        }, Milliseconds(2500));
    }

    // Multiple abilities may be toggled before the next Player update.
    // This is a bounded read-only observation queue, NOT saved preferences.
    struct PendingChoice
    {
        ObjectGuid petGuid;
        uint32 petNumber = 0;
        uint32 spellId = 0;
        bool requestedEnabled = false;
        uint8 barSlot = MAX_UNIT_ACTION_BAR_INDEX; // only for SET_ACTION
        char const* origin = "CMSG_PET_SPELL_AUTOCAST";
    };

    struct PendingChoiceQueue final : DataMap::Base
    {
        std::vector<PendingChoice> choices;
        bool overflowed = false;
    };

    void QueuePendingChoice(Player* owner, Pet* pet, uint32 spellId,
        bool requestedEnabled, uint8 barSlot, char const* origin)
    {
        PendingChoiceQueue* queue =
            owner->CustomData.GetDefault<PendingChoiceQueue>(AUDIT_KEY);

        PendingChoice item;
        item.petGuid = pet->GetGUID();
        item.petNumber = pet->GetCharmInfo()->GetPetNumber();
        item.spellId = spellId;
        item.requestedEnabled = requestedEnabled;
        item.barSlot = barSlot;
        item.origin = origin;

        // Repeated identical packets are not independent evidence.
        // Distinct spells and opposite ON/OFF choices must not overwrite.
        auto duplicate = std::find_if(queue->choices.begin(),
            queue->choices.end(), [&item](PendingChoice const& candidate)
            {
                return candidate.petGuid == item.petGuid &&
                    candidate.spellId == item.spellId &&
                    candidate.requestedEnabled == item.requestedEnabled &&
                    candidate.barSlot == item.barSlot;
            });
        if (duplicate != queue->choices.end())
            return;

        if (queue->choices.size() >= MAX_TOGGLE_AUDIT_QUEUE)
        {
            queue->overflowed = true;
            return;
        }

        queue->choices.push_back(item);
    }

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

            // Audit all native autocastable abilities; no rank eligibility
            // or post-IP completion can be inferred from these packets.
            SpellInfo const* info = sSpellMgr->GetSpellInfo(spellId);
            if (!info || !info->IsAutocastable())
                return;

            Pet* pet = owner->GetPet();
            if (!pet || pet->getPetType() != HUNTER_PET ||
                pet->isBeingLoaded() || !pet->HasSpell(spellId))
                return;

            LearnPacketProbe* sample =
                pet->CustomData.GetDefault<LearnPacketProbe>(LEARN_KEY);
            // Coalesce and cap this pet's pending learn notifications.
            // Another learned spell in the same tick must not erase one.
            if (std::find(sample->pendingSpells.begin(),
                sample->pendingSpells.end(), spellId) !=
                sample->pendingSpells.end() ||
                sample->pendingSpells.size() >= MAX_LEARNED_AUDIT_QUEUE)
                return;
            sample->pendingSpells.push_back(spellId);

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

            QueuePendingChoice(owner, pet, spellId, enabledByte != 0,
                MAX_UNIT_ACTION_BAR_INDEX, "CMSG_PET_SPELL_AUTOCAST");

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

            QueuePendingChoice(owner, pet, spellId, requestedEnabled,
                uint8(position), "CMSG_PET_SET_ACTION");

            return true; // read-only; native handler owns all validation
        }
    };

    class HunterPetAutocastUpdateObserver final : public PlayerScript
    {
    public:
        HunterPetAutocastUpdateObserver()
            : PlayerScript("NaxxramasHunterPetAutocastUpdateObserver",
                {PLAYERHOOK_ON_AFTER_UPDATE,
                 PLAYERHOOK_ON_BEFORE_LOAD_PET_FROM_DB}) { }

        // Core invokes this after selecting a stable PetInfo but BEFORE
        // creating/loading the runtime Pet. Seeing it never proves the
        // load succeeded, that the Pet is ready, or that its ID is durable.
        void OnPlayerBeforeLoadPetFromDB(Player* owner,
            uint32& petEntry, uint32& petNumber, bool& current,
            bool& forceLoadFromDB) override
        {
            if (!AuditEnabled() || !owner ||
                owner->getClass() != CLASS_HUNTER)
                return;

            LOG_INFO("module",
                "HunterPetAutocast NATIVE-LOAD-ATTEMPT audit: owner={} "
                "requestedEntry={} requestedNumber={} current={} "
                "forceLoadBeforeHook={}; attempt ONLY, not creation "
                "or completion proof; no arguments changed",
                owner->GetGUID().GetCounter(), petEntry, petNumber,
                current, forceLoadFromDB);
        }

        void OnPlayerAfterUpdate(Player* owner, uint32 diff) override
        {
            if (!AuditEnabled() || !owner ||
                owner->getClass() != CLASS_HUNTER)
                return;

            ObserveLifecycle(owner, diff);
            ObserveRevival(owner);
            ObserveAbilityStability(owner, diff);

            // Inspect the same pet's still-known rank during a subsequent
            // update, without executing any action. A packet alone does
            // not prove completion of IP's delayed reconciliation.
            if (Pet* pet = owner->GetPet())
            {
                LearnPacketProbe* learned =
                    pet->CustomData.Get<LearnPacketProbe>(LEARN_KEY);
                if (learned && !learned->pendingSpells.empty())
                {
                    for (uint32 const spellId : learned->pendingSpells)
                    {
                        LOG_INFO("module",
                            "HunterPetAutocast LEARN-PACKET audit: "
                            "next-update owner={} spell={} stillKnown={} "
                            "loading={}; no autocast restoration",
                            owner->GetGUID().GetCounter(), spellId,
                            pet->HasSpell(spellId), pet->isBeingLoaded());
                    }
                    learned->pendingSpells.clear();
                }
            }

            PendingChoiceQueue* queue =
                owner->CustomData.Get<PendingChoiceQueue>(AUDIT_KEY);
            if (!queue || (queue->choices.empty() && !queue->overflowed))
                return;

            // Atomically drain observations on this Player update. Never
            // retain a candidate across relogs or defer native mutation.
            std::vector<PendingChoice> observations;
            observations.swap(queue->choices);
            if (queue->overflowed)
            {
                LOG_INFO("module",
                    "HunterPetAutocast AUDIT ONLY: owner={} at least one "
                    "toggle candidate omitted by bounded audit queue; "
                    "not proof of acceptance or user intent",
                    owner->GetGUID().GetCounter());
                queue->overflowed = false;
            }

            for (PendingChoice const& choice : observations)
            {
                Pet* pet = owner->GetPet();
                if (!pet || pet->getPetType() != HUNTER_PET ||
                    pet->GetGUID() != choice.petGuid ||
                    pet->isBeingLoaded() || !pet->GetCharmInfo() ||
                    pet->GetCharmInfo()->GetPetNumber() != choice.petNumber)
                    continue;

                bool confirmedEnabled = false;
                if (!NativeState(pet, choice.spellId, confirmedEnabled) ||
                    confirmedEnabled != choice.requestedEnabled)
                    continue;

                if (choice.barSlot < MAX_UNIT_ACTION_BAR_INDEX)
                {
                    UnitActionBarEntry const* bar =
                        pet->GetCharmInfo()->GetActionBarEntry(choice.barSlot);
                    if (!bar || !bar->IsActionBarForSpell() ||
                        bar->GetAction() != choice.spellId ||
                        bar->GetType() !=
                            (choice.requestedEnabled ? ACT_ENABLED : ACT_DISABLED))
                        continue;
                }

                // A matching later native state is not definitive attribution.
                // This is NEVER stored as a user preference or replayed.
                LOG_INFO("module",
                    "HunterPetAutocast AUDIT ONLY: owner={} petnumber={} "
                    "spell={} requested={} source={} native=matching-state-only; "
                    "actor not attributable; no mutation",
                    owner->GetGUID().GetCounter(), choice.petNumber,
                    choice.spellId, choice.requestedEnabled ? "ON" : "OFF",
                    choice.origin);
            }
        }
    };
}

void AddHunterPetAutocastAuditScripts()
{
    new HunterPetAutocastPacketObserver();
    new HunterPetAutocastActionBarObserver();
    new HunterPetAutocastLearnPacketObserver();
    new HunterPetAutocastLifecycleObserver();
    new HunterPetAutocastPostEventObserver();
    new HunterPetAutocastDeathObserver();
    new HunterPetAutocastUpdateObserver();
}
