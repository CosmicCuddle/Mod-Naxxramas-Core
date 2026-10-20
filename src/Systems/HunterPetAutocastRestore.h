/*
 * Naxxramas Core — human hunter pet autocast save/restore policy.
 *
 * Pure decisions for the module script. No worldserver, SQL, or DBC.
 * A passing test is not gameplay acceptance.
 *
 * IP's DelayedPetSpellCheck is queued at m_time+200. Pet::Update returns
 * before that processor runs while m_loading is set, so the 200ms does not
 * elapse during the load, and the 10-try requeue does not run on that path.
 * The module queues one earlier event on the same frozen clock and turns
 * autocast ON only. ToggleAutocast(false) does not write OFF on a new rank.
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
/* GetOption fallback only, the same argument IP passes at IndividualProgression.cpp:1070.
 * The live check uses whatever that config key holds. This is not a match list.
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
static_assert(RestoreLagMs >= 150u, "restore waits at least 150ms after IP");
static_assert(SnapshotPollMs > 0u && SnapshotPollMs < IpEventDelayMs, "snapshot poll is inside the IP gap");
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

/* IP's isBotAccount is account-name regex_match, not a Playerbots call.
 * A regex that does not compile is not a bot match: IP would throw, and
 * throwing here would take the world thread down on a config typo.
 */
inline bool AccountIsBot(bool nameFound, char const* accountName, char const* pattern)
{
    if (!nameFound || !accountName || !pattern || pattern[0] == '\0')
        return false;

    try
    {
        return std::regex_match(accountName, std::regex(pattern));
    }
    catch (std::regex_error const&)
    {
        return false;
    }
}

inline constexpr bool IsIpOpportunity(uint32_t offsetMs)
{
    return offsetMs >= IpEventDelayMs && offsetMs <= LastIpOpportunityMs() && offsetMs % IpEventDelayMs == 0u;
}

/* The next IP tick strictly after offsetMs, or 0 when that tick has passed. */
inline constexpr uint32_t NextIpOpportunityAfter(uint32_t offsetMs)
{
    if (offsetMs >= LastIpOpportunityMs())
        return 0u;

    uint32_t const next = (offsetMs / IpEventDelayMs + 1u) * IpEventDelayMs;
    return next <= LastIpOpportunityMs() ? next : 0u;
}

/* What DelayedPetSpellCheck::Execute does if this pump is the one that reaches it.
 * PetUpdateWhileLoading is not a pump: Pet::Update returns before Creature::Update.
 */
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

enum class PollAction : uint8_t
{
    DeferBeforeIp = 0,
    CommitSnapshot,
    UseRemovedFallback,
    GiveUp
};

struct PollDecision
{
    PollAction action = PollAction::GiveUp;
    uint32_t rescheduleMs = 0;
};

/* offsetMs is event time since the hook, on pet->m_Events.
 * Ordinary summon: the pet is loaded before the first pump, so the 50ms
 * event commits and the restore is scheduled 150ms after IP's 200ms key.
 * A fire while still loading is not that path. It must not walk IP's
 * private 10-try counter, which this module cannot see.
 */
inline PollDecision DecideSnapshotPoll(uint32_t offsetMs, bool petLoaded)
{
    PollDecision decision;
    if (!petLoaded)
    {
        if (offsetMs + SnapshotPollMs < IpEventDelayMs)
        {
            decision.action = PollAction::DeferBeforeIp;
            decision.rescheduleMs = SnapshotPollMs;
            return decision;
        }

        if (offsetMs >= LastIpOpportunityMs())
        {
            decision.action = PollAction::GiveUp;
            decision.rescheduleMs = 0;
            return decision;
        }

        decision.action = PollAction::UseRemovedFallback;
        if (offsetMs < IpEventDelayMs)
            decision.rescheduleMs = (IpEventDelayMs - offsetMs) + RestoreLagMs;
        else
            decision.rescheduleMs = RestoreLagMs;
        return decision;
    }

    if (offsetMs < IpEventDelayMs)
    {
        decision.action = PollAction::CommitSnapshot;
        decision.rescheduleMs = (IpEventDelayMs - offsetMs) + RestoreLagMs;
        return decision;
    }

    if (offsetMs >= LastIpOpportunityMs() + RestoreLagMs)
    {
        decision.action = PollAction::GiveUp;
        decision.rescheduleMs = 0;
        return decision;
    }

    decision.action = PollAction::UseRemovedFallback;
    decision.rescheduleMs = RestoreLagMs;
    return decision;
}

struct OrdinarySchedule
{
    uint32_t snapshotOffsetMs = 0;
    uint32_t ipOffsetMs = 0;
    uint32_t restoreOffsetMs = 0;
    bool snapshotted = false;
};

/* Both keys are CalculateTime offsets from the hook. m_time stays put until
 * a processor update, which Pet::Update does not do while m_loading is set.
 */
inline OrdinarySchedule OrdinaryScheduleAfterLoad()
{
    OrdinarySchedule schedule;
    schedule.ipOffsetMs = IpEventDelayMs;
    schedule.snapshotOffsetMs = FirstPollDelayMs();
    PollDecision const decision = DecideSnapshotPoll(schedule.snapshotOffsetMs, true);
    schedule.snapshotted = decision.action == PollAction::CommitSnapshot;
    schedule.restoreOffsetMs = schedule.snapshotOffsetMs + decision.rescheduleMs;
    return schedule;
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

struct ChainRestore
{
    uint32_t chainFirst = 0;
    uint32_t newSpellId = 0;
    uint32_t oldSpellId = 0;
    bool desiredOn = false;
    bool apply = false;
};

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

inline std::vector<ChainRestore> PlanRestores(
    std::vector<BookSpell> const& book,
    std::map<uint32_t, Preference> const& snapshot,
    std::map<uint32_t, Preference> const& packet,
    bool allowRemovedFallback)
{
    struct Group
    {
        std::vector<BookSpell const*> current;
        std::vector<BookSpell const*> removed;
    };

    std::map<uint32_t, Group> groups;
    for (BookSpell const& spell : book)
    {
        if (!spell.autocastable || spell.chainFirst == 0u || spell.id == 0u)
            continue;
        if (spell.removed)
            groups[spell.chainFirst].removed.push_back(&spell);
        else
            groups[spell.chainFirst].current.push_back(&spell);
    }

    std::vector<ChainRestore> plans;
    for (auto const& grouped : groups)
    {
        Group const& group = grouped.second;
        if (group.current.size() != 1u)
            continue;

        BookSpell const* current = group.current[0];
        auto const packetIt = packet.find(grouped.first);
        auto const snapshotIt = snapshot.find(grouped.first);
        Preference const* chosen = nullptr;
        Preference removedPreference;

        bool const packetNewer = packetIt != packet.end() && packetIt->second.present &&
            (snapshotIt == snapshot.end() || !snapshotIt->second.present ||
             packetIt->second.sequence > snapshotIt->second.sequence);
        if (packetNewer)
            chosen = &packetIt->second;
        else if (snapshotIt != snapshot.end() && snapshotIt->second.present)
            chosen = &snapshotIt->second;
        else if (allowRemovedFallback && group.removed.size() == 1u)
        {
            removedPreference.spellId = group.removed[0]->id;
            removedPreference.autocastOn = group.removed[0]->autocastOn;
            removedPreference.present = true;
            chosen = &removedPreference;
        }

        if (!chosen || !chosen->present || chosen->spellId == 0u || chosen->spellId == current->id)
            continue;

        /* A new rank is already ACT_DISABLED. ToggleAutocast(false) does not
         * write that byte unless the new id is already in m_autospells.
         */
        if (!chosen->autocastOn)
            continue;

        ChainRestore plan;
        plan.chainFirst = grouped.first;
        plan.newSpellId = current->id;
        plan.oldSpellId = chosen->spellId;
        plan.desiredOn = true;
        plan.apply = true;
        plans.push_back(plan);
    }
    return plans;
}

inline void NoteRestored(
    std::map<uint32_t, Preference>& snapshot,
    std::map<uint32_t, Preference>& packet,
    ChainRestore const& plan,
    uint64_t sequence)
{
    if (!plan.apply)
        return;

    Preference& saved = snapshot[plan.chainFirst];
    saved.spellId = plan.newSpellId;
    saved.autocastOn = plan.desiredOn;
    saved.present = true;
    saved.sequence = sequence;

    auto const packetIt = packet.find(plan.chainFirst);
    if (packetIt != packet.end())
    {
        packetIt->second.spellId = plan.newSpellId;
        packetIt->second.autocastOn = plan.desiredOn;
        packetIt->second.present = true;
        packetIt->second.sequence = sequence;
    }
}

inline bool PetNumberMatches(uint32_t scheduled, uint32_t current)
{
    return scheduled != 0u && scheduled == current;
}
} // namespace NaxxramasCore::HunterPetAutocastRestore
