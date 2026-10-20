/*
 * Naxxramas Core — human hunter pet autocast restore policy.
 *
 * Default-off EXPERIMENTAL prototype. A passing test is not gameplay
 * acceptance and is not functional S2 completion.
 *
 * Decisions are fail-closed. Unknown accounts, unvalidated autocast
 * packets, a live pet GUID mismatch, and an explicit OFF that the new
 * rank does not already show do not toggle the pet. Removed spell rows
 * are not a preference source. Timer offsets are not treated as proof
 * that this module ran before Individual Progression.
 *
 * POTENTIAL ISSUE: stale old-rank ids can remain in m_autospells.
 * Pet::ToggleAutocast(spell, false) at Pet.cpp:2254-2283 finds a
 * PETSPELL_REMOVED row and, because that state is not PETSPELL_NEW,
 * rewrites it to PETSPELL_CHANGED (Pet.cpp:2282-2283). That can resurrect
 * the old rank on the next save. This policy never requests that call.
 */
#pragma once

#include <cstdint>
#include <map>
#include <regex>
#include <string>
#include <vector>

namespace NaxxramasCore::HunterPetAutocastRestore
{
inline constexpr char const* EnabledConfigKey = "NaxxramasCore.HunterPetAutocastRestore.Enabled";
inline constexpr char const* DefaultEnabledRaw = "0";
inline constexpr char const* BotAccountsRegexKey = "IndividualProgression.BotAccountsRegex";
/* GetOption fallback only, the same argument IP passes when the key is absent.
 * An empty or invalid configured value is ineligible. It is not "not a bot".
 */
inline constexpr char const* DefaultBotAccountsRegex = "^RNDBOT.*";

inline constexpr char const* PinnedCoreOldSha = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7";
inline constexpr char const* PinnedCoreNewSha = "8daffdabe9202c228e45d833c9a1d399597a15cd";
inline constexpr char const* PinnedIndividualProgressionSha = "4ff4b5fcc1480348f058c632573143e62d4e3a41";
inline constexpr char const* PinnedPlayerbotsSha = "037c01418b5d01506917a3db9b44fd56ac5f965c";

inline constexpr uint32_t IpEventDelayMs = 200;
inline constexpr uint32_t SnapshotPollMs = 50;
inline constexpr uint32_t RestoreLagMs = 150;
inline constexpr uint8_t IpLoadingAttemptCap = 10;

inline constexpr uint32_t IpOpportunityMs(uint8_t attempts)
{
    return IpEventDelayMs * (static_cast<uint32_t>(attempts) + 1u);
}

inline constexpr uint32_t LastIpOpportunityMs()
{
    return IpOpportunityMs(IpLoadingAttemptCap);
}

inline constexpr uint32_t FirstPollDelayMs()
{
    return SnapshotPollMs;
}

static_assert(IpEventDelayMs == 200u, "DelayedPetSpellCheck cadence");
static_assert(IpLoadingAttemptCap == 10u, "DelayedPetSpellCheck attempt cap");
static_assert(LastIpOpportunityMs() == 2200u, "attempt 10 fires at 2200ms");

inline bool EnabledFromRaw(char const* raw)
{
    if (!raw)
        return false;

    std::string text(raw);
    std::size_t begin = 0;
    while (begin < text.size() && (text[begin] == ' ' || text[begin] == '\t'))
        ++begin;
    std::size_t end = text.size();
    while (end > begin && (text[end - 1] == ' ' || text[end - 1] == '\t'))
        --end;
    return text.compare(begin, end - begin, "1") == 0;
}

/* ConfirmedHuman is the only verdict that may schedule or restore.
 * ConfirmedBot matched a compiled pattern. Everything else is Ineligible,
 * including a missing session, a failed name lookup, and an empty or
 * invalid pattern. Ineligible is not "not a bot".
 */
enum class AccountVerdict : uint8_t
{
    ConfirmedHuman = 0,
    ConfirmedBot,
    Ineligible
};

inline AccountVerdict ClassifyAccount(bool nameFound, char const* accountName, char const* pattern)
{
    if (!nameFound || !accountName || accountName[0] == '\0' || !pattern || pattern[0] == '\0')
        return AccountVerdict::Ineligible;

    try
    {
        std::regex compiled(pattern);
        if (std::regex_match(accountName, compiled))
            return AccountVerdict::ConfirmedBot;
        return AccountVerdict::ConfirmedHuman;
    }
    catch (std::regex_error const&)
    {
        return AccountVerdict::Ineligible;
    }
}

inline bool IsEligibleHumanAccount(AccountVerdict verdict)
{
    return verdict == AccountVerdict::ConfirmedHuman;
}

/* Unvalidated CMSG_PET_SPELL_AUTOCAST cache is not a preference. The receive
 * hook runs before the core handler accepts the spell, the rank, or the pet.
 */
inline constexpr bool UnvalidatedPacketDrivesToggle()
{
    return false;
}

enum class EventPump : uint8_t
{
    PetUpdateWhileLoading = 0,
    ProcessorAdvanced
};

struct IpExecution
{
    bool processorRan = false;
    bool requeued = false;
    bool hunterCheckRan = false;
};

inline IpExecution IpDelayedCheckOnPump(EventPump pump, bool isBeingLoaded, uint8_t attempts)
{
    IpExecution result;
    if (pump == EventPump::PetUpdateWhileLoading)
        return result;

    result.processorRan = true;
    if (isBeingLoaded && attempts < IpLoadingAttemptCap)
    {
        result.requeued = true;
        return result;
    }

    result.hunterCheckRan = true;
    return result;
}

inline bool FrozenLoadPumpsReconcile()
{
    for (uint8_t attempt = 0; attempt <= IpLoadingAttemptCap; ++attempt)
    {
        IpExecution const exec = IpDelayedCheckOnPump(EventPump::PetUpdateWhileLoading, true, attempt);
        if (exec.processorRan || exec.requeued || exec.hunterCheckRan)
            return true;
    }
    return false;
}

struct BookSpell
{
    uint32_t id = 0;
    uint32_t chainFirst = 0;
    bool autocastable = false;
    bool removed = false;
    bool autocastOn = false;
};

struct Preference
{
    uint32_t spellId = 0;
    bool autocastOn = false;
    bool present = false;
    uint64_t sequence = 0;
};

struct LivePetId
{
    uint64_t ownerGuid = 0;
    uint64_t petGuid = 0;
    uint32_t petNumber = 0;
};

enum class CycleAbort : uint8_t
{
    None = 0,
    MissingPet,
    GuidMismatch,
    NotInWorld,
    BeingRemoved,
    OwnerLoggingOut,
    StillLoading,
    NoSnapshot,
    StaleSnapshot,
    AmbiguousBook,
    ExplicitOffConflict,
    InterveningChange,
    IpAlreadyRan,
    UnvalidatedPacketIgnored,
    NestedSchedule,
    DuplicateResetBlocked
};

inline CycleAbort CheckLiveIdentity(
    LivePetId const& bound,
    LivePetId const& current,
    bool inWorld,
    bool beingRemoved,
    bool ownerLoggingOut)
{
    if (ownerLoggingOut)
        return CycleAbort::OwnerLoggingOut;
    if (bound.ownerGuid == 0 || bound.petGuid == 0 || bound.petNumber == 0 || current.petGuid == 0)
        return CycleAbort::MissingPet;
    if (bound.ownerGuid != current.ownerGuid || bound.petGuid != current.petGuid || bound.petNumber != current.petNumber)
        return CycleAbort::GuidMismatch;
    if (beingRemoved)
        return CycleAbort::BeingRemoved;
    if (!inWorld)
        return CycleAbort::NotInWorld;
    return CycleAbort::None;
}

struct MemoryView
{
    LivePetId bound{};
    bool pending = false;
    bool snapshotCommitted = false;
    bool refused = false;
    bool applied = false;
    uint32_t generation = 0;
    std::map<uint32_t, Preference> snapshot;
};

enum class ScheduleResult : uint8_t
{
    Started = 0,
    IgnoredDuplicate,
    Refused
};

/* A second hook for the same live GUID must not clear a snapshot or a
 * pending cycle. BeginCycle used to reset that memory on every schedule.
 */
inline ScheduleResult ScheduleCycle(MemoryView& memory, LivePetId const& pet)
{
    if (pet.ownerGuid == 0 || pet.petGuid == 0 || pet.petNumber == 0)
        return ScheduleResult::Refused;
    if (memory.refused && memory.bound.petGuid == pet.petGuid)
        return ScheduleResult::Refused;
    if (memory.bound.petGuid == pet.petGuid && (memory.pending || memory.snapshotCommitted || memory.applied))
        return ScheduleResult::IgnoredDuplicate;

    memory.bound = pet;
    memory.snapshot.clear();
    memory.snapshotCommitted = false;
    memory.pending = true;
    memory.applied = false;
    memory.refused = false;
    memory.generation += 1u;
    return ScheduleResult::Started;
}

inline bool EventGenerationMatches(uint32_t eventGeneration, uint32_t memoryGeneration)
{
    return eventGeneration != 0u && eventGeneration == memoryGeneration;
}

inline bool BookLooksPostReconcile(std::vector<BookSpell> const& book)
{
    for (BookSpell const& spell : book)
    {
        if (spell.removed && spell.autocastable && spell.id != 0u)
            return true;
    }
    return false;
}

inline std::map<uint32_t, Preference> SnapshotChains(std::vector<BookSpell> const& book, uint64_t sequence)
{
    std::map<uint32_t, int> counts;
    std::map<uint32_t, Preference> snapshot;
    for (BookSpell const& spell : book)
    {
        if (spell.removed || !spell.autocastable || spell.chainFirst == 0u || spell.id == 0u)
            continue;

        ++counts[spell.chainFirst];
        Preference& preference = snapshot[spell.chainFirst];
        preference.spellId = spell.id;
        preference.autocastOn = spell.autocastOn;
        preference.present = true;
        preference.sequence = sequence;
    }

    for (auto const& entry : counts)
    {
        if (entry.second != 1)
            snapshot.erase(entry.first);
    }
    return snapshot;
}

struct SnapshotCommit
{
    bool committed = false;
    CycleAbort reason = CycleAbort::None;
    std::map<uint32_t, Preference> chains;
};

inline SnapshotCommit TryCommitSnapshot(
    LivePetId const& bound,
    LivePetId const& current,
    bool inWorld,
    bool beingRemoved,
    bool ownerLoggingOut,
    bool loaded,
    bool ipAlreadyReconciled,
    std::vector<BookSpell> const& book,
    uint64_t sequence)
{
    SnapshotCommit commit;
    CycleAbort const identity = CheckLiveIdentity(bound, current, inWorld, beingRemoved, ownerLoggingOut);
    if (identity != CycleAbort::None)
    {
        commit.reason = identity;
        return commit;
    }
    if (!loaded)
    {
        commit.reason = CycleAbort::StillLoading;
        return commit;
    }
    if (ipAlreadyReconciled || BookLooksPostReconcile(book))
    {
        commit.reason = CycleAbort::IpAlreadyRan;
        return commit;
    }

    std::map<uint32_t, int> counts;
    for (BookSpell const& spell : book)
    {
        if (spell.removed || !spell.autocastable || spell.chainFirst == 0u || spell.id == 0u)
            continue;
        ++counts[spell.chainFirst];
    }
    for (auto const& entry : counts)
    {
        if (entry.second != 1)
        {
            commit.reason = CycleAbort::AmbiguousBook;
            return commit;
        }
    }

    commit.chains = SnapshotChains(book, sequence);
    if (commit.chains.empty())
    {
        commit.reason = CycleAbort::NoSnapshot;
        return commit;
    }
    commit.committed = true;
    commit.reason = CycleAbort::None;
    return commit;
}

struct ChainPlan
{
    uint32_t chainFirst = 0;
    uint32_t newSpellId = 0;
    uint32_t oldSpellId = 0;
    bool desiredOn = false;
    bool applyOn = false;
};

enum class RestoreOutcome : uint8_t
{
    NoChange = 0,
    ApplyOn,
    HonourOff,
    Abort
};

struct RestoreDecision
{
    RestoreOutcome outcome = RestoreOutcome::Abort;
    CycleAbort reason = CycleAbort::NoSnapshot;
    std::vector<ChainPlan> plans;
    bool touchesPet = false;
    bool writesOff = false;
};

inline RestoreDecision RejectUnvalidatedPacket()
{
    RestoreDecision decision;
    decision.outcome = RestoreOutcome::Abort;
    decision.reason = CycleAbort::UnvalidatedPacketIgnored;
    decision.touchesPet = false;
    decision.writesOff = false;
    return decision;
}

/* Packet preferences are not an argument. A REMOVED row is not a donor.
 * Explicit OFF is honoured only when the new rank is already OFF, and then
 * nothing is written. A new rank that is ON while the snapshot says OFF
 * aborts the whole pet: ToggleAutocast(false) is not a safe OFF write on a
 * rank that was just learned, and a partial ON apply is not used instead.
 */
inline RestoreDecision DecideRestore(
    LivePetId const& bound,
    LivePetId const& current,
    bool inWorld,
    bool beingRemoved,
    bool ownerLoggingOut,
    bool loaded,
    bool snapshotCommitted,
    std::map<uint32_t, Preference> const& snapshot,
    std::vector<BookSpell> const& book)
{
    RestoreDecision decision;
    decision.writesOff = false;
    decision.touchesPet = false;

    CycleAbort const identity = CheckLiveIdentity(bound, current, inWorld, beingRemoved, ownerLoggingOut);
    if (identity != CycleAbort::None)
    {
        decision.outcome = RestoreOutcome::Abort;
        decision.reason = identity == CycleAbort::GuidMismatch && snapshotCommitted
            ? CycleAbort::StaleSnapshot
            : identity;
        return decision;
    }
    if (!loaded)
    {
        decision.outcome = RestoreOutcome::Abort;
        decision.reason = CycleAbort::StillLoading;
        return decision;
    }
    if (!snapshotCommitted || snapshot.empty() || bound.petGuid != current.petGuid)
    {
        decision.outcome = RestoreOutcome::Abort;
        decision.reason = CycleAbort::NoSnapshot;
        return decision;
    }

    struct Group
    {
        std::vector<BookSpell const*> current;
        std::vector<BookSpell const*> removed;
    };

    std::map<uint32_t, Group> groups;
    for (BookSpell const& spell : book)
    {
        if (!spell.autocastable || spell.id == 0u)
            continue;
        if (spell.chainFirst == 0u)
        {
            decision.outcome = RestoreOutcome::Abort;
            decision.reason = CycleAbort::AmbiguousBook;
            return decision;
        }
        if (spell.removed)
            groups[spell.chainFirst].removed.push_back(&spell);
        else
            groups[spell.chainFirst].current.push_back(&spell);
    }

    for (auto const& grouped : groups)
    {
        if (snapshot.find(grouped.first) == snapshot.end())
        {
            decision.outcome = RestoreOutcome::Abort;
            decision.reason = CycleAbort::AmbiguousBook;
            return decision;
        }
        if (grouped.second.current.size() != 1u || grouped.second.removed.size() > 1u)
        {
            decision.outcome = RestoreOutcome::Abort;
            decision.reason = CycleAbort::AmbiguousBook;
            return decision;
        }
    }

    bool anyOn = false;
    bool anyOff = false;
    for (auto const& saved : snapshot)
    {
        auto const grouped = groups.find(saved.first);
        if (grouped == groups.end() || grouped->second.current.size() != 1u || grouped->second.removed.size() > 1u)
        {
            decision.outcome = RestoreOutcome::Abort;
            decision.reason = CycleAbort::AmbiguousBook;
            decision.plans.clear();
            return decision;
        }

        Preference const& pref = saved.second;
        if (!pref.present || pref.spellId == 0u)
        {
            decision.outcome = RestoreOutcome::Abort;
            decision.reason = CycleAbort::AmbiguousBook;
            decision.plans.clear();
            return decision;
        }

        BookSpell const* currentSpell = grouped->second.current[0];
        if (grouped->second.removed.size() == 1u)
        {
            BookSpell const* removed = grouped->second.removed[0];
            if (removed->id != pref.spellId || removed->autocastOn != pref.autocastOn)
            {
                decision.outcome = RestoreOutcome::Abort;
                decision.reason = CycleAbort::InterveningChange;
                decision.plans.clear();
                return decision;
            }
        }

        if (currentSpell->id == pref.spellId)
        {
            if (!pref.autocastOn && currentSpell->autocastOn)
            {
                decision.outcome = RestoreOutcome::Abort;
                decision.reason = CycleAbort::ExplicitOffConflict;
                decision.plans.clear();
                return decision;
            }
            continue;
        }

        if (!pref.autocastOn)
        {
            if (currentSpell->autocastOn)
            {
                decision.outcome = RestoreOutcome::Abort;
                decision.reason = CycleAbort::ExplicitOffConflict;
                decision.plans.clear();
                return decision;
            }
            anyOff = true;
            continue;
        }

        if (currentSpell->autocastOn)
            continue;

        ChainPlan plan;
        plan.chainFirst = saved.first;
        plan.newSpellId = currentSpell->id;
        plan.oldSpellId = pref.spellId;
        plan.desiredOn = true;
        plan.applyOn = true;
        decision.plans.push_back(plan);
        anyOn = true;
    }

    if (anyOn)
    {
        decision.outcome = RestoreOutcome::ApplyOn;
        decision.reason = CycleAbort::None;
        decision.touchesPet = true;
        return decision;
    }
    if (anyOff)
    {
        decision.outcome = RestoreOutcome::HonourOff;
        decision.reason = CycleAbort::None;
        decision.touchesPet = false;
        return decision;
    }

    decision.outcome = RestoreOutcome::NoChange;
    decision.reason = CycleAbort::None;
    decision.touchesPet = false;
    return decision;
}

enum class SimStep : uint8_t
{
    BindHook = 0,
    DuplicateHook,
    ModulePoll,
    IpCheck,
    PetSave,
    ModuleRestore,
    Logout,
    RelogNewGuid,
    ResummonSameNumber,
    SwapPet,
    UnvalidatedPacket,
    LoadCompletes,
    IpExhaustWhileLoading,
    OtherModuleTurnsOn,
    MarkNotInWorld,
    MarkBeingRemoved
};

struct SimInput
{
    bool explicitOn = true;
    bool startLoading = true;
    bool spellsLoadedAtStart = false;
    uint64_t petGuid = 100;
    uint64_t ownerGuid = 7;
    uint32_t petNumber = 45;
    uint32_t oldId = 17253;
    uint32_t newId = 17255;
    uint32_t chain = 17253;
};

struct SimResult
{
    RestoreOutcome outcome = RestoreOutcome::Abort;
    CycleAbort reason = CycleAbort::None;
    uint32_t toggles = 0;
    bool wroteOff = false;
    uint64_t touchedGuid = 0;
    bool snapshotCommitted = false;
    uint64_t snapshotGuid = 0;
    bool duplicateIgnored = false;
    uint32_t generation = 0;
};

struct SimWorld
{
    SimInput input;
    LivePetId pet{};
    bool inWorld = true;
    bool beingRemoved = false;
    bool loggingOut = false;
    bool loading = true;
    bool ipReconciled = false;
    uint8_t ipAttempts = 0;
    std::vector<BookSpell> book;
    MemoryView memory;
    uint32_t toggles = 0;
    bool wroteOff = false;
    uint64_t touchedGuid = 0;
    RestoreOutcome outcome = RestoreOutcome::Abort;
    CycleAbort reason = CycleAbort::None;
    bool duplicateIgnored = false;
    bool packetIgnored = false;
};

inline BookSpell MakeSpell(uint32_t id, uint32_t chain, bool on, bool removed = false)
{
    BookSpell spell;
    spell.id = id;
    spell.chainFirst = chain;
    spell.autocastable = true;
    spell.removed = removed;
    spell.autocastOn = on;
    return spell;
}

inline SimWorld MakeWorld(SimInput const& input)
{
    SimWorld world;
    world.input = input;
    world.pet.ownerGuid = input.ownerGuid;
    world.pet.petGuid = input.petGuid;
    world.pet.petNumber = input.petNumber;
    world.loading = input.startLoading;
    if (input.spellsLoadedAtStart || !input.startLoading)
        world.book.push_back(MakeSpell(input.oldId, input.chain, input.explicitOn));
    return world;
}

inline bool SwapRankIfPresent(SimWorld& world)
{
    bool found = false;
    for (BookSpell& spell : world.book)
    {
        if (!spell.removed && spell.id == world.input.oldId)
        {
            spell.removed = true;
            found = true;
        }
    }
    if (!found)
        return false;

    world.book.push_back(MakeSpell(world.input.newId, world.input.chain, false));
    return true;
}

inline void ApplyModuleRestore(SimWorld& world)
{
    if (world.memory.applied)
    {
        world.outcome = RestoreOutcome::Abort;
        world.reason = CycleAbort::NestedSchedule;
        return;
    }

    RestoreDecision const decision = DecideRestore(
        world.memory.bound,
        world.pet,
        world.inWorld,
        world.beingRemoved,
        world.loggingOut,
        !world.loading,
        world.memory.snapshotCommitted,
        world.memory.snapshot,
        world.book);
    world.outcome = decision.outcome;
    world.reason = decision.reason;
    if (decision.writesOff)
        world.wroteOff = true;
    if (decision.outcome == RestoreOutcome::NoChange)
        return;

    world.memory.applied = true;
    world.memory.pending = false;
    if (decision.outcome == RestoreOutcome::ApplyOn && decision.touchesPet)
    {
        ++world.toggles;
        world.touchedGuid = world.pet.petGuid;
        for (ChainPlan const& plan : decision.plans)
        {
            for (BookSpell& spell : world.book)
            {
                if (!spell.removed && spell.id == plan.newSpellId)
                    spell.autocastOn = true;
            }
        }
    }
}

inline SimResult RunSequence(std::vector<SimStep> const& steps, SimInput const& input)
{
    SimWorld world = MakeWorld(input);
    for (SimStep const step : steps)
    {
        switch (step)
        {
            case SimStep::BindHook:
            case SimStep::DuplicateHook:
            {
                ScheduleResult const scheduled = ScheduleCycle(world.memory, world.pet);
                if (step == SimStep::DuplicateHook)
                    world.duplicateIgnored = scheduled == ScheduleResult::IgnoredDuplicate;
                world.reason = scheduled == ScheduleResult::IgnoredDuplicate
                    ? CycleAbort::DuplicateResetBlocked
                    : world.reason;
                break;
            }
            case SimStep::ModulePoll:
            {
                if (world.memory.snapshotCommitted)
                {
                    world.reason = CycleAbort::DuplicateResetBlocked;
                    break;
                }
                SnapshotCommit const commit = TryCommitSnapshot(
                    world.memory.bound,
                    world.pet,
                    world.inWorld,
                    world.beingRemoved,
                    world.loggingOut,
                    !world.loading,
                    world.ipReconciled,
                    world.book,
                    1u);
                world.reason = commit.reason;
                if (commit.committed)
                {
                    world.memory.snapshot = commit.chains;
                    world.memory.snapshotCommitted = true;
                }
                else if (commit.reason == CycleAbort::IpAlreadyRan)
                {
                    world.memory.refused = true;
                    world.memory.pending = false;
                }
                break;
            }
            case SimStep::IpCheck:
            {
                IpExecution const exec = IpDelayedCheckOnPump(
                    EventPump::ProcessorAdvanced, world.loading, world.ipAttempts);
                if (exec.requeued)
                {
                    ++world.ipAttempts;
                    break;
                }
                if (exec.hunterCheckRan)
                {
                    world.ipReconciled = true;
                    SwapRankIfPresent(world);
                }
                break;
            }
            case SimStep::PetSave:
            {
                std::vector<BookSpell> kept;
                for (BookSpell const& spell : world.book)
                {
                    if (!spell.removed)
                        kept.push_back(spell);
                }
                world.book.swap(kept);
                break;
            }
            case SimStep::ModuleRestore:
                ApplyModuleRestore(world);
                break;
            case SimStep::Logout:
                world.loggingOut = true;
                break;
            case SimStep::RelogNewGuid:
                world.loggingOut = false;
                world.inWorld = true;
                world.beingRemoved = false;
                world.loading = false;
                world.memory = MemoryView{};
                world.pet.petGuid += 1u;
                break;
            case SimStep::ResummonSameNumber:
                world.pet.petGuid += 1u;
                world.inWorld = true;
                world.beingRemoved = false;
                world.loading = false;
                world.loggingOut = false;
                break;
            case SimStep::SwapPet:
                world.pet.petGuid += 1u;
                world.pet.petNumber += 1u;
                world.inWorld = true;
                world.beingRemoved = false;
                world.loading = false;
                break;
            case SimStep::UnvalidatedPacket:
                world.packetIgnored = true;
                world.reason = CycleAbort::UnvalidatedPacketIgnored;
                break;
            case SimStep::LoadCompletes:
                world.loading = false;
                if (world.book.empty())
                    world.book.push_back(MakeSpell(world.input.oldId, world.input.chain, world.input.explicitOn));
                break;
            case SimStep::IpExhaustWhileLoading:
            {
                for (uint8_t attempt = 0; attempt <= IpLoadingAttemptCap; ++attempt)
                {
                    IpExecution const exec = IpDelayedCheckOnPump(EventPump::ProcessorAdvanced, true, attempt);
                    if (!exec.hunterCheckRan)
                        continue;
                    world.ipReconciled = true;
                    world.ipAttempts = IpLoadingAttemptCap;
                    SwapRankIfPresent(world);
                }
                break;
            }
            case SimStep::OtherModuleTurnsOn:
                for (BookSpell& spell : world.book)
                {
                    if (!spell.removed)
                        spell.autocastOn = true;
                }
                break;
            case SimStep::MarkNotInWorld:
                world.inWorld = false;
                break;
            case SimStep::MarkBeingRemoved:
                world.beingRemoved = true;
                break;
        }
    }

    SimResult result;
    result.outcome = world.outcome;
    result.reason = world.reason;
    result.toggles = world.toggles;
    result.wroteOff = world.wroteOff;
    result.touchedGuid = world.touchedGuid;
    result.snapshotCommitted = world.memory.snapshotCommitted;
    result.snapshotGuid = world.memory.snapshotCommitted ? world.memory.bound.petGuid : 0u;
    result.duplicateIgnored = world.duplicateIgnored;
    result.generation = world.memory.generation;
    return result;
}

/* (a) Loading delays both the module poll and IP. IP then learn-defaults
 * the rank to OFF, a pet save erases the REMOVED row, and the hypothetical
 * restore has no trustworthy snapshot. Explicit ON and explicit OFF both
 * abort. Nothing is written, including no invented ON and no claim that
 * the learn-default OFF was the player's explicit OFF.
 */
inline SimResult CounterexampleDelayedLoadThenSave(bool explicitOn)
{
    SimInput input;
    input.explicitOn = explicitOn;
    input.startLoading = true;
    input.spellsLoadedAtStart = false;
    return RunSequence(
        {
            SimStep::BindHook,
            SimStep::LoadCompletes,
            SimStep::IpCheck,
            SimStep::PetSave,
            SimStep::ModuleRestore,
        },
        input);
}
} // namespace NaxxramasCore::HunterPetAutocastRestore
