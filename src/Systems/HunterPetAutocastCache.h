/*
 * Naxxramas Core — hunter pet autocast cache.
 *
 * Default off. Module only. No AzerothCore, Individual Progression,
 * Playerbots, or DBC edit. The characters SQL file is not applied here.
 *
 * Individual Progression's checkHunterPetSpells learns the kept rank with
 * ACT_DECIDE, and Pet::addSpell stores an autocastable spell as
 * ACT_DISABLED (Pet.cpp:1810-1816 at both pinned cores). This policy
 * snapshots the pre-reset choice, then re-applies it after IP's worst
 * case. A chain that was not in that snapshot is new (tame, new ability,
 * or a new chain) and is turned on only when its first rank is on the
 * damage allowlist. Utility chains are never written.
 *
 * State lives on the pet. This header has no process-global pet map.
 */
#pragma once

#include <cstdint>
#include <exception>
#include <iterator>
#include <map>
#include <regex>
#include <string>
#include <vector>

namespace NaxxramasCore::HunterPetAutocastCache
{
inline constexpr char const* EnabledConfigKey = "NaxxramasCore.HunterPet.AutocastCache.Enabled";
inline constexpr char const* DefaultEnabledRaw = "0";
inline constexpr char const* BotAccountsRegexKey = "NaxxramasCore.HunterPet.AutocastCache.BotAccountsRegex";
inline constexpr char const* DefaultBotAccountsRegex = "^RNDBOT.*";
inline constexpr char const* DamageSpellIdsKey = "NaxxramasCore.HunterPet.AutocastCache.DamageSpellIds";
inline constexpr char const* UtilitySpellIdsKey = "NaxxramasCore.HunterPet.AutocastCache.UtilitySpellIds";
inline constexpr char const* OptionalSpellIdsKey = "NaxxramasCore.HunterPet.AutocastCache.OptionalSpellIds";
inline constexpr char const* DefaultOptionalSpellIdsRaw = "";
inline constexpr char const* CacheTableName = "mod_naxxramas_hunter_pet_autocast";

inline constexpr char const* PinnedCoreOldSha = "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7";
inline constexpr char const* PinnedCoreNewSha = "8daffdabe9202c228e45d833c9a1d399597a15cd";
inline constexpr char const* PinnedIndividualProgressionSha = "4ff4b5fcc1480348f058c632573143e62d4e3a41";

/* IP DelayedPetSpellCheck is 200ms, then up to 10 more 200ms retries.
 * 200 * 11 = 2200. The re-apply window is longer than that worst case.
 */
inline constexpr uint32_t IpEventDelayMs = 200;
inline constexpr uint8_t IpLoadingAttemptCap = 10;
inline constexpr uint32_t IpWorstCaseMs = IpEventDelayMs * (static_cast<uint32_t>(IpLoadingAttemptCap) + 1u);
inline constexpr uint32_t RestoreTickMs = 200;
inline constexpr uint32_t RestoreWindowMs = 3000;

static_assert(IpWorstCaseMs == 2200u, "IP load retries end at 2200ms");
static_assert(RestoreWindowMs > IpWorstCaseMs, "re-apply outlasts IP's worst case");
static_assert(RestoreWindowMs >= 2500u && RestoreWindowMs <= 3000u, "owner window is 2.5-3s");

/* First ranks. Names were read from Wowhead WotLK tooltips on 2026-10-20.
 * Chains were read from AzerothCore spell_ranks (same ids the 3.3.5 client uses).
 * Screech and Demoralizing Screech are one chain: first rank 24423.
 * Pummel is 26090. Thunderstomp is a different chain, first rank 26094.
 * IP's gorilla comment calls 26090 Thunderstomp; the 3.3.5 tooltip name is Pummel.
 */
inline constexpr uint32_t DefaultDamageFirstRanks[] = {
    17253, /* Bite */
    16827, /* Claw */
    49966, /* Smack */
    24844, /* Lightning Breath */
    34889, /* Fire Breath */
    24640, /* Scorpid Poison */
    35387, /* Poison Spit */
    24423, /* Demoralizing Screech (Screech chain) */
    55749, /* Acid Spit */
    35290, /* Gore */
    50518, /* Ravage */
    56626, /* Sting */
    50274, /* Spore Cloud */
    50271, /* Tendon Rip */
    50245, /* Pin */
    54680, /* Monstrous Bite */
    50498, /* Savage Rend */
    57386, /* Stampede */
    50541, /* Snatch */
    50519, /* Sonic Blast */
    50256, /* Swipe */
    54706, /* Venom Web Spray */
    54644, /* Froststorm Breath */
    61193, /* Spirit Strike */
    50285, /* Dust Cloud */
    26090  /* Pummel */
};

inline constexpr uint32_t DefaultUtilityFirstRanks[] = {
    2649,  /* Growl */
    1742,  /* Cower */
    61684, /* Dash */
    23145, /* Dive */
    61685, /* Charge */
    24450, /* Prowl */
    26064, /* Shell Shield */
    53517, /* Roar of Recovery */
    53480, /* Roar of Sacrifice */
    53401, /* Rabid */
    53476, /* Intervene */
    53478, /* Last Stand */
    55709, /* Heart of the Phoenix */
    53434, /* Call of the Wild */
    53477, /* Taunt */
    26094, /* Thunderstomp */
    35346  /* Warp */
};

/* Owner judgement. Out of the default-on list. Not utility, so a saved
 * ON/OFF in the snapshot is still restored. A new chain stays untouched
 * unless its id is added to OptionalSpellIds.
 * Bad Manner has no 3.3.5a spell. Bad Attitude is 50433 and is not this list.
 */
inline constexpr uint32_t JudgementFirstRanks[] = {
    24604, /* Furious Howl */
    53508, /* Wolverine Bite */
    4167,  /* Web */
    58604  /* Lava Breath */
};

inline constexpr uint32_t BadAttitudeFirstRank = 50433;
inline constexpr uint32_t RakeFirstRank = 59881;

inline constexpr char const* DefaultDamageSpellIdsRaw =
    "17253,16827,49966,24844,34889,24640,35387,24423,55749,35290,50518,56626,50274,50271,50245,54680,50498,57386,50541,50519,50256,54706,54644,61193,50285,26090";
inline constexpr char const* DefaultUtilitySpellIdsRaw =
    "2649,1742,61684,23145,61685,24450,26064,53517,53480,53401,53476,53478,55709,53434,53477,26094,35346";

inline constexpr bool UsesProcessGlobalPetMap()
{
    return false;
}

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

inline bool ContainsId(std::vector<uint32_t> const& ids, uint32_t id)
{
    for (uint32_t candidate : ids)
    {
        if (candidate == id)
            return true;
    }
    return false;
}

inline std::vector<uint32_t> ParseSpellIds(char const* raw)
{
    std::vector<uint32_t> ids;
    if (!raw || raw[0] == '\0')
        return ids;

    std::string text(raw);
    std::string token;
    auto flush = [&]()
    {
        if (token.empty())
            return;
        bool digits = true;
        for (char ch : token)
        {
            if (ch < '0' || ch > '9')
                digits = false;
        }
        if (digits)
        {
            try
            {
                unsigned long value = std::stoul(token);
                if (value > 0ul && value <= 0xFFFFFFFFul && !ContainsId(ids, static_cast<uint32_t>(value)))
                    ids.push_back(static_cast<uint32_t>(value));
            }
            catch (std::exception const&)
            {
            }
        }
        token.clear();
    };

    for (char ch : text)
    {
        if (ch == ',' || ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r')
            flush();
        else
            token.push_back(ch);
    }
    flush();
    return ids;
}

inline std::vector<uint32_t> DefaultDamageIds()
{
    return std::vector<uint32_t>(std::begin(DefaultDamageFirstRanks), std::end(DefaultDamageFirstRanks));
}

inline std::vector<uint32_t> DefaultUtilityIds()
{
    return std::vector<uint32_t>(std::begin(DefaultUtilityFirstRanks), std::end(DefaultUtilityFirstRanks));
}

struct SourceSpell
{
    uint32_t chainFirst = 0;
    uint32_t spellId = 0;
    bool autocastable = false;
    bool removed = false;
    bool autocastOn = false;
};

enum class SnapshotOrigin : uint8_t
{
    Empty = 0,
    ModuleCache,
    PetSpell,
    CharmBar,
    LiveBook
};

struct SnapshotResult
{
    SnapshotOrigin origin = SnapshotOrigin::Empty;
    std::map<uint32_t, bool> chains;
};

/* Drop utility, removed, and non-autocast rows. One chain: ON if any
 * remaining row is ON.
 */
inline std::map<uint32_t, bool> CollapseChains(std::vector<SourceSpell> const& rows, std::vector<uint32_t> const& utility)
{
    std::map<uint32_t, bool> chains;
    for (SourceSpell const& row : rows)
    {
        if (row.chainFirst == 0 || row.removed || !row.autocastable)
            continue;
        if (ContainsId(utility, row.chainFirst))
            continue;
        auto found = chains.find(row.chainFirst);
        if (found == chains.end())
            chains.emplace(row.chainFirst, row.autocastOn);
        else if (row.autocastOn)
            found->second = true;
    }
    return chains;
}

/* Load path. Module cache wins when it has at least one usable chain.
 * Otherwise pet_spell (characters.pet_spell: spell, active). Otherwise
 * the charm bar. An empty result is not a migration to ON.
 */
inline SnapshotResult ChooseLoadSnapshot(
    std::vector<SourceSpell> const& cacheRows,
    std::vector<SourceSpell> const& petSpellRows,
    std::vector<SourceSpell> const& charmRows,
    std::vector<uint32_t> const& utility)
{
    std::map<uint32_t, bool> fromCache = CollapseChains(cacheRows, utility);
    if (!fromCache.empty())
        return SnapshotResult{ SnapshotOrigin::ModuleCache, fromCache };

    std::map<uint32_t, bool> fromPetSpell = CollapseChains(petSpellRows, utility);
    if (!fromPetSpell.empty())
        return SnapshotResult{ SnapshotOrigin::PetSpell, fromPetSpell };

    std::map<uint32_t, bool> fromCharm = CollapseChains(charmRows, utility);
    if (!fromCharm.empty())
        return SnapshotResult{ SnapshotOrigin::CharmBar, fromCharm };

    return SnapshotResult{};
}

inline SnapshotResult CollapseLiveBook(std::vector<SourceSpell> const& book, std::vector<uint32_t> const& utility)
{
    std::map<uint32_t, bool> chains = CollapseChains(book, utility);
    if (chains.empty())
        return SnapshotResult{};
    return SnapshotResult{ SnapshotOrigin::LiveBook, chains };
}

enum class ApplyKind : uint8_t
{
    Restore = 0,
    DefaultOn
};

struct ApplyAction
{
    uint32_t chainFirst = 0;
    uint32_t spellId = 0;
    bool desiredOn = false;
    ApplyKind kind = ApplyKind::Restore;
};

struct ChainLists
{
    std::vector<uint32_t> damage;
    std::vector<uint32_t> utility;
    std::vector<uint32_t> optionalOn;
};

inline bool IsDefaultOnChain(uint32_t chainFirst, ChainLists const& lists)
{
    if (ContainsId(lists.utility, chainFirst))
        return false;
    return ContainsId(lists.damage, chainFirst) || ContainsId(lists.optionalOn, chainFirst);
}

/* Current non-removed autocastable ranks only. Utility is omitted.
 * Snapshot chains are restored to the saved bit. Chains absent from the
 * snapshot are turned on only when they are on the damage allowlist or
 * the optional list. Anything else, including judgement spells left at
 * the default empty optional list, is left as the core stored it.
 */
inline std::vector<ApplyAction> PlanApply(
    std::map<uint32_t, bool> const& snapshot,
    std::vector<SourceSpell> const& book,
    ChainLists const& lists)
{
    struct Current
    {
        uint32_t onSpellId = 0;
        uint32_t offSpellId = 0;
        bool anyOn = false;
    };

    std::map<uint32_t, Current> current;
    for (SourceSpell const& row : book)
    {
        if (row.chainFirst == 0 || row.removed || !row.autocastable)
            continue;
        if (ContainsId(lists.utility, row.chainFirst))
            continue;

        Current& slot = current[row.chainFirst];
        if (row.autocastOn)
        {
            slot.anyOn = true;
            slot.onSpellId = row.spellId;
        }
        else
            slot.offSpellId = row.spellId;
    }

    std::vector<ApplyAction> actions;
    for (auto const& entry : current)
    {
        uint32_t const chain = entry.first;
        Current const& slot = entry.second;
        auto saved = snapshot.find(chain);
        bool desiredOn = false;
        ApplyKind kind = ApplyKind::Restore;
        if (saved != snapshot.end())
            desiredOn = saved->second;
        else if (IsDefaultOnChain(chain, lists))
        {
            desiredOn = true;
            kind = ApplyKind::DefaultOn;
        }
        else
            continue;

        if (slot.anyOn == desiredOn)
            continue;

        ApplyAction action;
        action.chainFirst = chain;
        action.desiredOn = desiredOn;
        action.kind = kind;
        action.spellId = desiredOn ? (slot.offSpellId != 0 ? slot.offSpellId : slot.onSpellId)
                                    : (slot.onSpellId != 0 ? slot.onSpellId : slot.offSpellId);
        if (action.spellId == 0)
            continue;
        actions.push_back(action);
    }
    return actions;
}

/* Cache rows are the decision, not a later read of a post-IP book.
 * Snapshot bits are kept. A new damage chain is recorded ON because that
 * is the decision, even if the book still says OFF when this is built.
 */
inline std::map<uint32_t, bool> VerifiedCacheRows(
    std::map<uint32_t, bool> const& snapshot,
    std::vector<SourceSpell> const& book,
    ChainLists const& lists)
{
    std::map<uint32_t, bool> rows = snapshot;
    for (SourceSpell const& row : book)
    {
        if (row.chainFirst == 0 || row.removed || !row.autocastable)
            continue;
        if (ContainsId(lists.utility, row.chainFirst))
            continue;
        if (snapshot.find(row.chainFirst) != snapshot.end())
            continue;
        if (IsDefaultOnChain(row.chainFirst, lists))
            rows[row.chainFirst] = true;
    }
    return rows;
}

inline std::map<uint32_t, bool> PlayerToggleRows(std::vector<SourceSpell> const& book, std::vector<uint32_t> const& utility)
{
    return CollapseChains(book, utility);
}

enum class WriteCause : uint8_t
{
    Snapshot = 0,
    VerifiedRestore,
    PlayerSave
};

inline bool AllowCacheWrite(WriteCause cause, bool restoreWindowOpen)
{
    if (cause == WriteCause::PlayerSave)
        return !restoreWindowOpen;
    return cause == WriteCause::Snapshot || cause == WriteCause::VerifiedRestore;
}

struct Binding
{
    uint64_t ownerGuid = 0;
    uint64_t petGuid = 0;
    uint32_t petNumber = 0;
};

enum class IdentityResult : uint8_t
{
    Ok = 0,
    UpdatedNumber,
    Abort
};

/* Unit::InitTamedPet calls InitStatsForLevel before SetPetNumber
 * (Unit.cpp:13429-13437 at both pins). The charm number may change
 * before the window opens. After the window is open the number is fixed.
 */
inline IdentityResult CheckIdentity(
    Binding& bound,
    Binding const& live,
    bool windowOpen,
    bool inWorld,
    bool beingRemoved,
    bool loggingOut)
{
    if (loggingOut || beingRemoved || !inWorld)
        return IdentityResult::Abort;
    if (bound.ownerGuid == 0 || bound.petGuid == 0 || live.petGuid == 0)
        return IdentityResult::Abort;
    if (bound.ownerGuid != live.ownerGuid || bound.petGuid != live.petGuid)
        return IdentityResult::Abort;
    if (live.petNumber == 0)
        return IdentityResult::Abort;
    if (bound.petNumber != live.petNumber)
    {
        if (!windowOpen)
        {
            bound.petNumber = live.petNumber;
            return IdentityResult::UpdatedNumber;
        }
        return IdentityResult::Abort;
    }
    return IdentityResult::Ok;
}

struct Clock
{
    bool open = false;
    uint32_t elapsedMs = 0;
    bool done = false;
};

struct TickDecision
{
    bool apply = false;
    bool requeue = false;
    uint32_t delayMs = 0;
    bool closed = false;
};

inline TickDecision OnTick(Clock& clock, bool isBeingLoaded)
{
    TickDecision decision;
    if (clock.done)
    {
        decision.closed = true;
        return decision;
    }
    if (isBeingLoaded)
    {
        decision.requeue = true;
        decision.delayMs = RestoreTickMs;
        return decision;
    }

    decision.apply = true;
    if (!clock.open)
        clock.open = true;
    else
        clock.elapsedMs += RestoreTickMs;

    if (clock.elapsedMs >= RestoreWindowMs)
    {
        clock.done = true;
        decision.closed = true;
        return decision;
    }

    decision.requeue = true;
    decision.delayMs = RestoreTickMs;
    return decision;
}

/* Loading ticks do not open the window. After load, applies continue
 * until RestoreWindowMs has elapsed inside the window.
 */
inline uint32_t AppliesWhileCoveringIpWorstCase()
{
    Clock clock;
    uint32_t applies = 0;
    for (uint32_t step = 0; step < 4u; ++step)
    {
        TickDecision const tick = OnTick(clock, true);
        if (tick.apply || tick.closed || !tick.requeue)
            return 0;
    }
    for (uint32_t step = 0; step < 40u && !clock.done; ++step)
    {
        TickDecision const tick = OnTick(clock, false);
        if (tick.apply)
            ++applies;
    }
    if (!clock.done || clock.elapsedMs < IpWorstCaseMs)
        return 0;
    return applies;
}

inline bool ScheduleReplacesOpenSnapshot()
{
    return false;
}
} // namespace NaxxramasCore::HunterPetAutocastCache
