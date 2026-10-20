/*
 * Naxxramas Core — experimental, default-off human hunter pet autocast
 * restore. Module only. No Individual Progression, Playerbots, core, SQL,
 * or DBC edits.
 *
 * The script calls the policy in HunterPetAutocastRestore.h. It toggles a
 * pet only when DecideRestore returns ApplyOn for the live pet GUID captured
 * at schedule time. Explicit OFF is not written. Unvalidated autocast
 * packets are not read. A removed spell row is not a preference.
 *
 * POTENTIAL ISSUE: stale old-rank ids stay in m_autospells. ToggleAutocast
 * (false) is not a public-API-safe removal: on a PETSPELL_REMOVED row it
 * rewrites the state to PETSPELL_CHANGED (Pet.cpp:2254-2283 at both pinned
 * cores). NOT TESTED in PetAI.
 *
 * POTENTIAL ISSUE / documented blocker: a post-swap explicit OFF that leaves
 * the new rank at the learn-default ACT_DISABLED is not distinguishable from
 * "IP just learned it OFF". An ON restore can overwrite that unseen choice.
 * A visible conflict (snapshot OFF, current rank ON, or a REMOVED row whose
 * byte no longer matches the snapshot) aborts with no write. NOT TESTED
 * in game.
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

#include <string>
#include <unordered_map>
#include <vector>

namespace
{
using namespace NaxxramasCore::HunterPetAutocastRestore;

bool FeatureEnabled = false;
uint64_t PreferenceSequence = 1;

char const* PendingKey = "naxx_a02_hunter_pet_autocast_restore";

class PendingAutocastRestore : public DataMap::Base
{
public:
    bool pending = false;
    uint64_t petGuid = 0;
    uint32_t generation = 0;
};

struct PetMemory
{
    uint64_t ownerGuid = 0;
    uint64_t petGuid = 0;
    uint32_t petNumber = 0;
    uint32_t generation = 0;
    bool snapshotCommitted = false;
    bool refused = false;
    bool applied = false;
    std::map<uint32_t, Preference> snapshot;
};

std::unordered_map<uint64_t, PetMemory> PetMemories;

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

MemoryView ViewOf(PetMemory const& memory)
{
    MemoryView view;
    view.bound.ownerGuid = memory.ownerGuid;
    view.bound.petGuid = memory.petGuid;
    view.bound.petNumber = memory.petNumber;
    view.pending = memory.generation != 0 && !memory.applied && !memory.refused;
    view.snapshotCommitted = memory.snapshotCommitted;
    view.refused = memory.refused;
    view.applied = memory.applied;
    view.generation = memory.generation;
    view.snapshot = memory.snapshot;
    return view;
}

void StoreView(PetMemory& memory, MemoryView const& view)
{
    memory.ownerGuid = view.bound.ownerGuid;
    memory.petGuid = view.bound.petGuid;
    memory.petNumber = view.bound.petNumber;
    memory.generation = view.generation;
    memory.snapshotCommitted = view.snapshotCommitted;
    memory.refused = view.refused;
    memory.applied = view.applied;
    memory.snapshot = view.snapshot;
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

void ClearPending(Pet* pet)
{
    if (!pet)
        return;
    if (PendingAutocastRestore* pending = pet->CustomData.Get<PendingAutocastRestore>(PendingKey))
        pending->pending = false;
}

void ForgetOwner(uint64_t ownerGuid)
{
    for (auto it = PetMemories.begin(); it != PetMemories.end();)
    {
        if (it->second.ownerGuid == ownerGuid)
            it = PetMemories.erase(it);
        else
            ++it;
    }
}

bool ApplyOn(Player* player, Pet* pet, RestoreDecision const& decision)
{
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
        auto memoryIt = PetMemories.find(_pet.petGuid);
        if (memoryIt == PetMemories.end() || !EventGenerationMatches(_generation, memoryIt->second.generation))
        {
            ClearPending(pet);
            return true;
        }
        PetMemory& memory = memoryIt->second;
        if (memory.applied || memory.refused)
        {
            ClearPending(pet);
            return true;
        }

        if (!FeatureEnabled || !IsEligibleHumanHunter(player) || OwnerLoggingOut(player))
        {
            memory.applied = true;
            ClearPending(pet);
            return true;
        }

        if (!pet || pet->getPetType() != HUNTER_PET)
        {
            memory.applied = true;
            ClearPending(pet);
            return true;
        }

        LivePetId const current = IdOf(player, pet);
        bool const loggingOut = OwnerLoggingOut(player);
        CycleAbort const identity = CheckLiveIdentity(
            _pet, current, pet->IsInWorld(), pet->IsDuringRemoveFromWorld(), loggingOut);
        if (identity == CycleAbort::GuidMismatch || identity == CycleAbort::MissingPet ||
            identity == CycleAbort::BeingRemoved || identity == CycleAbort::OwnerLoggingOut)
        {
            memory.applied = true;
            ClearPending(pet);
            return true;
        }

        if (identity == CycleAbort::NotInWorld || pet->isBeingLoaded())
        {
            if (_restorePhase || _offsetMs >= LastIpOpportunityMs())
            {
                memory.applied = true;
                ClearPending(pet);
                return true;
            }
            pet->m_Events.AddEvent(
                new HunterPetAutocastEvent(_owner, _pet, _generation, _offsetMs + SnapshotPollMs, false),
                pet->m_Events.CalculateTime(SnapshotPollMs));
            return true;
        }

        if (!_restorePhase)
        {
            if (!memory.snapshotCommitted)
            {
                SnapshotCommit const commit = TryCommitSnapshot(
                    _pet,
                    current,
                    pet->IsInWorld(),
                    pet->IsDuringRemoveFromWorld(),
                    loggingOut,
                    !pet->isBeingLoaded(),
                    false,
                    ReadBook(pet),
                    ++PreferenceSequence);
                if (!commit.committed)
                {
                    if (commit.reason == CycleAbort::IpAlreadyRan || commit.reason == CycleAbort::AmbiguousBook)
                        memory.refused = true;
                    memory.applied = true;
                    ClearPending(pet);
                    return true;
                }
                memory.snapshot = commit.chains;
                memory.snapshotCommitted = true;
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
            memory.snapshotCommitted,
            memory.snapshot,
            ReadBook(pet));
        if (decision.outcome == RestoreOutcome::NoChange)
        {
            if (_offsetMs >= LastIpOpportunityMs())
            {
                memory.applied = true;
                ClearPending(pet);
                return true;
            }
            pet->m_Events.AddEvent(
                new HunterPetAutocastEvent(_owner, _pet, _generation, _offsetMs + RestoreLagMs, true),
                pet->m_Events.CalculateTime(RestoreLagMs));
            return true;
        }

        if (decision.outcome == RestoreOutcome::ApplyOn)
            ApplyOn(player, pet, decision);

        memory.applied = true;
        ClearPending(pet);
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
    if (!FeatureEnabled || !pet || pet->getPetType() != HUNTER_PET)
        return;

    Player* owner = pet->GetOwner();
    if (!IsEligibleHumanHunter(owner) || OwnerLoggingOut(owner))
        return;
    if (pet->IsDuringRemoveFromWorld())
        return;

    LivePetId const id = IdOf(owner, pet);
    if (id.petGuid == 0 || id.petNumber == 0)
        return;

    PetMemory& memory = PetMemories[id.petGuid];
    MemoryView view = ViewOf(memory);
    ScheduleResult const scheduled = ScheduleCycle(view, id);
    if (scheduled != ScheduleResult::Started)
        return;

    StoreView(memory, view);
    PendingAutocastRestore* pending = pet->CustomData.GetDefault<PendingAutocastRestore>(PendingKey);
    pending->pending = true;
    pending->petGuid = id.petGuid;
    pending->generation = memory.generation;
    pet->m_Events.AddEvent(
        new HunterPetAutocastEvent(owner->GetGUID(), id, memory.generation, FirstPollDelayMs(), false),
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
        FeatureEnabled = sConfigMgr->GetOption<bool>(EnabledConfigKey, false);
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

    void OnPlayerBeforeLogout(Player* player) override
    {
        if (!player)
            return;
        if (Pet* pet = player->GetPet())
            ClearPending(pet);
        ForgetOwner(GuidRaw(player->GetGUID()));
    }
};
} // namespace

void AddHunterPetAutocastRestoreScripts()
{
    new NaxxramasCoreHunterPetAutocastConfig();
    new NaxxramasCoreHunterPetAutocastPet();
    new NaxxramasCoreHunterPetAutocastPlayer();
}
