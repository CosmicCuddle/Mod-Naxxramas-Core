/*
 * Naxxramas Core — experimental, default-off human hunter pet autocast
 * restore. Module only. No Individual Progression, Playerbots, core, SQL,
 * or DBC edits.
 *
 * The script calls the policy in HunterPetAutocastRestore.h. It does not
 * toggle a pet. BLOCKED: NO ATOMIC MODULE-ONLY CHOICE SOURCE.
 * DecideRestore does not return ApplyOn while that source is missing, and
 * Execute checks the same constant again before ToggleAutocast.
 *
 * Cycle state lives on the Pet via CustomData. Dismiss destroys the Pet
 * and that state with it. There is no process-global pet map.
 * FeatureEnabled is an atomic flag written at config load.
 *
 * MISMATCH: ipAlreadyReconciled is not observed. TryCommitSnapshot is
 * called with literal false. BookLooksPostReconcile only sees
 * PETSPELL_REMOVED rows, and Pet::_SaveSpells (Pet.cpp:1572-1601 at both
 * pinned cores) erases those rows. A poll after that save can commit the
 * post-IP rank as the snapshot. The runtime-faithful model is
 * RuntimeFaithfulIpSaveThenPoll. It has no reconcile flag.
 *
 * POTENTIAL ISSUE: stale old-rank ids stay in m_autospells.
 * ToggleAutocast(false) is not a public-API-safe removal: on a
 * PETSPELL_REMOVED row it rewrites the state to PETSPELL_CHANGED
 * (Pet.cpp:2274-2283 at both pinned cores). This file does not call it.
 * A book with more than one autocast chain aborts. A single chain is not
 * every pet ability. NOT TESTED in PetAI.
 */

#include "HunterPetAutocastRestore.h"

#include "AccountMgr.h"
#include "Config.h"
#include "DataMap.h"
#include "EventProcessor.h"
#include "ObjectAccessor.h"
#include "Pet.h"
#include "PetScript.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellMgr.h"
#include "WorldSession.h"

#include <atomic>
#include <map>
#include <string>
#include <vector>

namespace
{
using namespace NaxxramasCore::HunterPetAutocastRestore;

std::atomic<bool> FeatureEnabled{false};

char const* CycleKey = "naxx_a02_hunter_pet_autocast_restore";

class PetAutocastCycle : public DataMap::Base
{
public:
    uint64_t ownerGuid = 0;
    uint64_t petGuid = 0;
    uint32_t petNumber = 0;
    uint32_t generation = 0;
    uint64_t preferenceSequence = 1;
    bool pending = false;
    bool snapshotCommitted = false;
    bool refused = false;
    bool applied = false;
    std::map<uint32_t, Preference> snapshot;

    uint64_t NextSequence()
    {
        uint64_t const current = preferenceSequence == 0 ? 1u : preferenceSequence;
        preferenceSequence = current + 1u;
        return current;
    }
};

bool IsFeatureEnabled()
{
    return FeatureEnabled.load(std::memory_order_acquire);
}

AccountVerdict ClassifyPlayer(Player* player)
{
    if (!player || !player->GetSession())
        return AccountVerdict::Ineligible;

    std::string accountName;
    bool const found = AccountMgr::GetName(player->GetSession()->GetAccountId(), accountName);
    std::string const pattern = sConfigMgr->GetOption<std::string>(BotAccountsRegexKey, DefaultBotAccountsRegex);
    return ClassifyAccount(found, found ? accountName.c_str() : nullptr, pattern.c_str());
}

bool IsEligibleHumanHunter(Player* player)
{
    return player && player->getClass() == CLASS_HUNTER &&
        ClassifyPlayer(player) == AccountVerdict::ConfirmedHuman;
}

uint32_t PetNumberOf(Pet* pet)
{
    if (!pet || !pet->GetCharmInfo())
        return 0;
    return pet->GetCharmInfo()->GetPetNumber();
}

uint64_t GuidRaw(ObjectGuid guid)
{
    return guid.GetRawValue();
}

LivePetId IdOf(Player* player, Pet* pet)
{
    LivePetId id;
    if (!player || !pet)
        return id;
    id.ownerGuid = GuidRaw(player->GetGUID());
    id.petGuid = GuidRaw(pet->GetGUID());
    id.petNumber = PetNumberOf(pet);
    return id;
}

bool OwnerLoggingOut(Player* player)
{
    if (!player)
        return true;
    WorldSession* session = player->GetSession();
    return !session || session->IsLoggingOut() || session->PlayerLogout();
}

MemoryView ViewOf(PetAutocastCycle const& cycle)
{
    MemoryView view;
    view.bound.ownerGuid = cycle.ownerGuid;
    view.bound.petGuid = cycle.petGuid;
    view.bound.petNumber = cycle.petNumber;
    view.pending = cycle.generation != 0 && !cycle.applied && !cycle.refused;
    view.snapshotCommitted = cycle.snapshotCommitted;
    view.refused = cycle.refused;
    view.applied = cycle.applied;
    view.generation = cycle.generation;
    view.snapshot = cycle.snapshot;
    return view;
}

void StoreView(PetAutocastCycle& cycle, MemoryView const& view)
{
    cycle.ownerGuid = view.bound.ownerGuid;
    cycle.petGuid = view.bound.petGuid;
    cycle.petNumber = view.bound.petNumber;
    cycle.generation = view.generation;
    cycle.snapshotCommitted = view.snapshotCommitted;
    cycle.refused = view.refused;
    cycle.applied = view.applied;
    cycle.pending = view.pending;
    cycle.snapshot = view.snapshot;
}

std::vector<BookSpell> ReadBook(Pet* pet)
{
    std::vector<BookSpell> book;
    if (!pet)
        return book;

    for (auto const& entry : pet->m_spells)
    {
        SpellInfo const* info = sSpellMgr->GetSpellInfo(entry.first);
        if (!info)
            continue;

        SpellInfo const* first = info->GetFirstRankSpell();
        BookSpell spell;
        spell.id = entry.first;
        spell.chainFirst = first ? first->Id : entry.first;
        spell.autocastable = info->IsAutocastable();
        spell.removed = entry.second.state == PETSPELL_REMOVED;
        spell.autocastOn = entry.second.active == ACT_ENABLED;
        book.push_back(spell);
    }
    return book;
}

/* Clears pending only when this object is the event's bound pet and the
 * generation still matches. A newly summoned pet is left alone.
 */
bool ClearPendingIfBound(Pet* pet, LivePetId const& bound, uint32_t eventGeneration)
{
    if (!pet || GuidRaw(pet->GetGUID()) != bound.petGuid)
        return false;

    PetAutocastCycle* cycle = pet->CustomData.Get<PetAutocastCycle>(CycleKey);
    if (!cycle)
        return false;

    LivePetId live;
    live.ownerGuid = cycle->ownerGuid;
    live.petGuid = cycle->petGuid;
    live.petNumber = cycle->petNumber;
    if (live.petGuid != GuidRaw(pet->GetGUID()))
        return false;
    if (!ClearPendingAllowed(bound, eventGeneration, live, cycle->generation))
        return false;

    cycle->pending = false;
    return true;
}

bool ApplyOn(Player* player, Pet* pet, RestoreDecision const& decision)
{
    if (!AtomicModuleOnlyChoiceSourceExists())
        return false;
    if (decision.outcome != RestoreOutcome::ApplyOn || !decision.touchesPet || decision.writesOff || decision.plans.empty())
        return false;

    std::vector<SpellInfo const*> spells;
    for (ChainPlan const& plan : decision.plans)
    {
        if (!plan.applyOn || !plan.desiredOn || plan.newSpellId == 0)
            return false;
        if (!pet->HasSpell(plan.newSpellId))
            return false;
        SpellInfo const* current = sSpellMgr->GetSpellInfo(plan.newSpellId);
        if (!current || !current->IsAutocastable())
            return false;
        spells.push_back(current);
    }

    for (SpellInfo const* current : spells)
    {
        pet->ToggleAutocast(current, true);
        if (CharmInfo* charm = pet->GetCharmInfo())
            charm->SetSpellAutocast(current, true);
    }
    player->PetSpellInitialize();
    return true;
}

class HunterPetAutocastEvent : public BasicEvent
{
public:
    HunterPetAutocastEvent(ObjectGuid owner, LivePetId pet, uint32_t generation, uint32_t offsetMs, bool restorePhase)
        : _owner(owner), _pet(pet), _generation(generation), _offsetMs(offsetMs), _restorePhase(restorePhase)
    {
    }

    bool Execute(uint64 /*eventTime*/, uint32 /*delta*/) override
    {
        Player* player = ObjectAccessor::FindPlayer(_owner);
        Pet* pet = player ? player->GetPet() : nullptr;
        /* player->GetPet() may already be a different summon. Do not
         * touch that object's CustomData.
         */
        if (!pet || GuidRaw(pet->GetGUID()) != _pet.petGuid || PetNumberOf(pet) != _pet.petNumber)
            return true;

        PetAutocastCycle* cycle = pet->CustomData.Get<PetAutocastCycle>(CycleKey);
        if (!cycle || !EventGenerationMatches(_generation, cycle->generation))
            return true;

        if (cycle->applied || cycle->refused)
        {
            ClearPendingIfBound(pet, _pet, _generation);
            return true;
        }

        if (!IsFeatureEnabled() || !IsEligibleHumanHunter(player) || OwnerLoggingOut(player))
        {
            cycle->applied = true;
            ClearPendingIfBound(pet, _pet, _generation);
            return true;
        }

        if (pet->getPetType() != HUNTER_PET)
        {
            cycle->applied = true;
            ClearPendingIfBound(pet, _pet, _generation);
            return true;
        }

        LivePetId const current = IdOf(player, pet);
        bool const loggingOut = OwnerLoggingOut(player);
        CycleAbort const identity = CheckLiveIdentity(
            _pet, current, pet->IsInWorld(), pet->IsDuringRemoveFromWorld(), loggingOut);
        if (identity == CycleAbort::GuidMismatch || identity == CycleAbort::MissingPet ||
            identity == CycleAbort::BeingRemoved || identity == CycleAbort::OwnerLoggingOut)
        {
            cycle->applied = true;
            ClearPendingIfBound(pet, _pet, _generation);
            return true;
        }

        if (identity == CycleAbort::NotInWorld || pet->isBeingLoaded())
        {
            if (_restorePhase || _offsetMs >= LastIpOpportunityMs())
            {
                cycle->applied = true;
                ClearPendingIfBound(pet, _pet, _generation);
                return true;
            }
            pet->m_Events.AddEvent(
                new HunterPetAutocastEvent(_owner, _pet, _generation, _offsetMs + SnapshotPollMs, false),
                pet->m_Events.CalculateTime(SnapshotPollMs));
            return true;
        }

        if (!_restorePhase)
        {
            if (!cycle->snapshotCommitted)
            {
                /* Literal false: the module has no IP-reconcile observation.
                 * See RuntimeFaithfulIpSaveThenPoll.
                 */
                SnapshotCommit const commit = TryCommitSnapshot(
                    _pet,
                    current,
                    pet->IsInWorld(),
                    pet->IsDuringRemoveFromWorld(),
                    loggingOut,
                    !pet->isBeingLoaded(),
                    false,
                    ReadBook(pet),
                    cycle->NextSequence());
                if (!commit.committed)
                {
                    if (commit.reason == CycleAbort::IpAlreadyRan || commit.reason == CycleAbort::AmbiguousBook)
                        cycle->refused = true;
                    cycle->applied = true;
                    ClearPendingIfBound(pet, _pet, _generation);
                    return true;
                }
                cycle->snapshot = commit.chains;
                cycle->snapshotCommitted = true;
            }

            pet->m_Events.AddEvent(
                new HunterPetAutocastEvent(_owner, _pet, _generation, _offsetMs + RestoreLagMs, true),
                pet->m_Events.CalculateTime(RestoreLagMs));
            return true;
        }

        RestoreDecision const decision = DecideRestore(
            _pet,
            current,
            pet->IsInWorld(),
            pet->IsDuringRemoveFromWorld(),
            loggingOut,
            !pet->isBeingLoaded(),
            cycle->snapshotCommitted,
            cycle->snapshot,
            ReadBook(pet));
        if (decision.outcome == RestoreOutcome::NoChange)
        {
            if (_offsetMs >= LastIpOpportunityMs())
            {
                cycle->applied = true;
                ClearPendingIfBound(pet, _pet, _generation);
                return true;
            }
            pet->m_Events.AddEvent(
                new HunterPetAutocastEvent(_owner, _pet, _generation, _offsetMs + RestoreLagMs, true),
                pet->m_Events.CalculateTime(RestoreLagMs));
            return true;
        }

        /* ApplyOn stays unreachable while the choice source is missing.
         * The call is still gated so a later true constant cannot write
         * from this function by accident without the policy agreeing.
         */
        if (decision.outcome == RestoreOutcome::ApplyOn && AtomicModuleOnlyChoiceSourceExists())
            ApplyOn(player, pet, decision);

        cycle->applied = true;
        ClearPendingIfBound(pet, _pet, _generation);
        return true;
    }

private:
    ObjectGuid _owner;
    LivePetId _pet;
    uint32_t _generation = 0;
    uint32_t _offsetMs = 0;
    bool _restorePhase = false;
};

void Schedule(Pet* pet)
{
    if (!IsFeatureEnabled() || !pet || pet->getPetType() != HUNTER_PET)
        return;

    Player* owner = pet->GetOwner();
    if (!IsEligibleHumanHunter(owner) || OwnerLoggingOut(owner))
        return;
    if (pet->IsDuringRemoveFromWorld())
        return;

    LivePetId const id = IdOf(owner, pet);
    if (id.petGuid == 0 || id.petNumber == 0 || GuidRaw(pet->GetGUID()) != id.petGuid)
        return;

    PetAutocastCycle* cycle = pet->CustomData.GetDefault<PetAutocastCycle>(CycleKey);
    MemoryView view = ViewOf(*cycle);
    ScheduleResult const scheduled = ScheduleCycle(view, id);
    if (scheduled != ScheduleResult::Started)
        return;

    StoreView(*cycle, view);
    cycle->pending = true;
    pet->m_Events.AddEvent(
        new HunterPetAutocastEvent(owner->GetGUID(), id, cycle->generation, FirstPollDelayMs(), false),
        pet->m_Events.CalculateTime(FirstPollDelayMs()));
}

class NaxxramasCoreHunterPetAutocastConfig : public WorldScript
{
public:
    NaxxramasCoreHunterPetAutocastConfig()
        : WorldScript("NaxxramasCoreHunterPetAutocastConfig", { WORLDHOOK_ON_BEFORE_CONFIG_LOAD })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        FeatureEnabled.store(sConfigMgr->GetOption<bool>(EnabledConfigKey, false), std::memory_order_release);
    }
};

class NaxxramasCoreHunterPetAutocastPet : public PetScript
{
public:
    NaxxramasCoreHunterPetAutocastPet()
        : PetScript(
            "NaxxramasCoreHunterPetAutocastPet",
            { PETHOOK_ON_PET_ADD_TO_WORLD, PETHOOK_ON_INIT_STATS_FOR_LEVEL })
    {
    }

    void OnPetAddToWorld(Pet* pet) override
    {
        Schedule(pet);
    }

    void OnInitStatsForLevel(Guardian* guardian, uint8 /*petlevel*/) override
    {
        if (!guardian)
            return;
        Schedule(guardian->ToPet());
    }
};

class NaxxramasCoreHunterPetAutocastPlayer : public PlayerScript
{
public:
    NaxxramasCoreHunterPetAutocastPlayer()
        : PlayerScript("NaxxramasCoreHunterPetAutocastPlayer", { PLAYERHOOK_ON_BEFORE_LOGOUT })
    {
    }

    /* Logout only marks the pet currently on this player. A dismissed pet
     * has already destroyed its CustomData with the Pet object, so there
     * is no table to sweep.
     */
    void OnPlayerBeforeLogout(Player* player) override
    {
        if (!player)
            return;
        Pet* pet = player->GetPet();
        if (!pet)
            return;
        PetAutocastCycle* cycle = pet->CustomData.Get<PetAutocastCycle>(CycleKey);
        if (!cycle)
            return;
        if (cycle->ownerGuid != GuidRaw(player->GetGUID()) || cycle->petGuid != GuidRaw(pet->GetGUID()))
            return;
        cycle->applied = true;
        cycle->pending = false;
    }
};
} // namespace

void AddHunterPetAutocastRestoreScripts()
{
    new NaxxramasCoreHunterPetAutocastConfig();
    new NaxxramasCoreHunterPetAutocastPet();
    new NaxxramasCoreHunterPetAutocastPlayer();
}
