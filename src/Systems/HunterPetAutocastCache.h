/*
 * Naxxramas Core — hunter pet autocast cache.
 *
 * Default off. Module only. No AzerothCore, Individual Progression,
 * Playerbots, or DBC edit. The characters SQL file is not applied here.
 *
 * Individual Progression's checkHunterPetSpells learns the kept rank with
 * ACT_DECIDE, and Pet::addSpell stores an autocastable spell as
 * ACT_DISABLED (Pet.cpp:1810-1816 at both pinned cores). The saved choice
 * is read only after _LoadSpells, from characters.pet_spell once
 * character_pet proves a single owner row. The charm bar is not that book.
 * A fixed 3000ms wait is not the ordering proof. See AdvanceOrder.
 *
 * State lives on the pet. This header has no process-global pet map.
 */
#pragma once

#include <algorithm>
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

/* IP queues DelayedPetSpellCheck at CalculateTime(200) and, while
 * isBeingLoaded() and attempts < 10, requeues at 200ms, then runs anyway.
 * 200 * 11 = 2200. Pet event time does not move during m_loading because
 * Pet::Update returns before WorldObject::Update. The normal cover is one
 * millisecond past that first 200ms delay. The 2200ms cover is only for a
 * load where something already pumped pet events.
 */
inline constexpr uint32_t IpEventDelayMs = 200;
inline constexpr uint8_t IpLoadingAttemptCap = 10;
inline constexpr uint32_t IpWorstCaseMs = IpEventDelayMs * (static_cast<uint32_t>(IpLoadingAttemptCap) + 1u);
inline constexpr uint32_t LoadPollMs = 200;
inline constexpr uint32_t CoverTickMs = 50;
inline constexpr uint32_t SameUpdateGuardMs = 1;
inline constexpr uint32_t NormalCoverMs = IpEventDelayMs + SameUpdateGuardMs;
inline constexpr uint32_t ExpectedCacheColumnCount = 7;

static_assert(IpWorstCaseMs == 2200u, "IP load retries end at 2200ms");
static_assert(NormalCoverMs == 201u, "normal cover is the IP delay plus one millisecond");
static_assert(SameUpdateGuardMs >= 1u, "a requeue of 0 would run again in this Update");

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
    Unavailable = 0,
    ModuleCache,
    PetSpell,
    EmptySaved,
    NewLife
};

/* The action bar is loaded before _LoadSpells. It is not the saved book. */
inline bool CharmBarIsAuthoritativeSavedSpellbook()
{
    return false;
}

inline bool MayTouchDatabase(bool featureEnabled)
{
    return featureEnabled;
}

struct SnapshotResult
{
    SnapshotOrigin origin = SnapshotOrigin::Unavailable;
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

enum class OwnerLookup : uint8_t
{
    Unproven = 0,
    Absent,
    Unique,
    Ambiguous
};

enum class DatabaseRead : uint8_t
{
    NotRun = 0,
    Ok,
    Failed
};

struct OwnerProof
{
    OwnerLookup lookup = OwnerLookup::Unproven;
    uint32_t creatureEntry = 0;
    uint32_t createdBySpell = 0;
    uint32_t savetime = 0;
};

struct StoredCacheRow
{
    uint32_t chainFirst = 0;
    bool on = false;
    uint32_t creatureEntry = 0;
    uint32_t createdBySpell = 0;
    uint32_t seenSavetime = 0;
};

struct LoadDecision
{
    SnapshotOrigin origin = SnapshotOrigin::Unavailable;
    std::map<uint32_t, bool> chains;
    bool allowDefaultOn = false;
    bool deleteStoredCache = false;
    bool writeAllowed = false;
    uint32_t creatureEntry = 0;
    uint32_t createdBySpell = 0;
    uint32_t seenSavetime = 0;
};

inline std::vector<SourceSpell> CacheAsSpells(std::vector<StoredCacheRow> const& rows)
{
    std::vector<SourceSpell> spells;
    spells.reserve(rows.size());
    for (StoredCacheRow const& row : rows)
    {
        SourceSpell spell;
        spell.chainFirst = row.chainFirst;
        spell.spellId = row.chainFirst;
        spell.autocastable = true;
        spell.autocastOn = row.on;
        spells.push_back(spell);
    }
    return spells;
}

/* Cache bits are used only when every stored row names this character_pet
 * life: one owner row, the same creature entry, the same create spell, and
 * the savetime we last bound. A miss fails closed onto pet_spell, or onto
 * nothing when that read is not Ok. The charm bar is not an input.
 * Default-on requires a probed cache table. A missing or failed table does
 * not mean every live damage chain is new.
 */
inline LoadDecision DecideLoad(
    bool cacheTablePresent,
    DatabaseRead cacheRead,
    std::vector<StoredCacheRow> const& cache,
    DatabaseRead petSpellRead,
    std::vector<SourceSpell> const& petSpell,
    OwnerProof const& owner,
    bool bornThisSession,
    std::vector<uint32_t> const& utility)
{
    LoadDecision decision;
    if (owner.lookup != OwnerLookup::Unique || owner.creatureEntry == 0)
    {
        decision.deleteStoredCache = owner.lookup == OwnerLookup::Absent && !cache.empty();
        return decision;
    }

    decision.creatureEntry = owner.creatureEntry;
    decision.createdBySpell = owner.createdBySpell;
    decision.seenSavetime = owner.savetime;

    bool const cacheReadable = cacheTablePresent && cacheRead == DatabaseRead::Ok;
    if (cacheReadable && !cache.empty())
    {
        bool sameLife = true;
        uint32_t const seen = cache.front().seenSavetime;
        for (StoredCacheRow const& row : cache)
        {
            if (row.creatureEntry != owner.creatureEntry || row.createdBySpell != owner.createdBySpell || row.seenSavetime != seen)
                sameLife = false;
        }
        if (!sameLife)
            decision.deleteStoredCache = true;
        else if (seen != owner.savetime)
            decision.deleteStoredCache = bornThisSession;
        else
        {
            decision.chains = CollapseChains(CacheAsSpells(cache), utility);
            decision.origin = SnapshotOrigin::ModuleCache;
            decision.allowDefaultOn = true;
            decision.writeAllowed = true;
            return decision;
        }
    }

    if (bornThisSession && cacheReadable)
    {
        decision.origin = SnapshotOrigin::NewLife;
        decision.allowDefaultOn = true;
        decision.writeAllowed = true;
        return decision;
    }

    if (petSpellRead != DatabaseRead::Ok)
        return decision;

    decision.chains = CollapseChains(petSpell, utility);
    decision.origin = decision.chains.empty() ? SnapshotOrigin::EmptySaved : SnapshotOrigin::PetSpell;
    decision.allowDefaultOn = cacheReadable;
    decision.writeAllowed = cacheReadable;
    return decision;
}

/* Numbers whose character_pet row is gone. The caller has already proved
 * the owner list. An unproven list must be passed as unproven=true and
 * deletes nothing.
 */
inline std::vector<uint32_t> OrphanPetNumbers(
    std::vector<uint32_t> const& cachedNumbers,
    std::vector<uint32_t> const& liveNumbers,
    bool ownerListProven)
{
    std::vector<uint32_t> orphans;
    if (!ownerListProven)
        return orphans;
    for (uint32_t number : cachedNumbers)
    {
        if (number != 0 && !ContainsId(liveNumbers, number) && !ContainsId(orphans, number))
            orphans.push_back(number);
    }
    return orphans;
}

/* The live book is what is in memory now. It is not a load snapshot.
 * IP may already have stored ACT_DISABLED there. Load decisions use
 * DecideLoad, which does not call this.
 */
inline std::map<uint32_t, bool> CollapseLiveBook(std::vector<SourceSpell> const& book, std::vector<uint32_t> const& utility)
{
    return CollapseChains(book, utility);
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
    ChainLists const& lists,
    bool allowDefaultOn = true)
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
        else if (allowDefaultOn && IsDefaultOnChain(chain, lists))
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
    ChainLists const& lists,
    bool allowDefaultOn = true)
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
        if (allowDefaultOn && IsDefaultOnChain(row.chainFirst, lists))
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

struct ReconcileTarget
{
    uint32_t chainFirst = 0;
    uint32_t spellId = 0;
    bool desiredOn = false;
};

struct AutocastEntry
{
    uint32_t spellId = 0;
    uint32_t chainFirst = 0;
    bool stillInBook = false;
};

/* Every chain this feature owns, including ones already at the saved bit.
 * Stale ranks of those chains are removed from m_autospells. Utility is not
 * owned, so its autocast ids are left in place.
 */
inline std::vector<ReconcileTarget> PlanReconcile(
    std::map<uint32_t, bool> const& snapshot,
    std::vector<SourceSpell> const& book,
    ChainLists const& lists,
    bool allowDefaultOn)
{
    struct Current
    {
        uint32_t spellId = 0;
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
        if (slot.spellId == 0 || row.autocastOn)
            slot.spellId = row.spellId;
        if (row.autocastOn)
            slot.anyOn = true;
    }

    std::vector<ReconcileTarget> targets;
    for (auto const& entry : current)
    {
        auto saved = snapshot.find(entry.first);
        bool desiredOn = false;
        bool owned = false;
        if (saved != snapshot.end())
        {
            desiredOn = saved->second;
            owned = true;
        }
        else if (allowDefaultOn && IsDefaultOnChain(entry.first, lists))
        {
            desiredOn = true;
            owned = true;
        }
        if (!owned || entry.second.spellId == 0)
            continue;
        ReconcileTarget target;
        target.chainFirst = entry.first;
        target.spellId = entry.second.spellId;
        target.desiredOn = desiredOn;
        targets.push_back(target);
    }
    return targets;
}

inline std::vector<uint32_t> StaleAutocastIds(
    std::vector<AutocastEntry> const& autos,
    std::vector<ReconcileTarget> const& targets)
{
    std::vector<uint32_t> stale;
    for (AutocastEntry const& row : autos)
    {
        for (ReconcileTarget const& target : targets)
        {
            if (target.chainFirst != row.chainFirst)
                continue;
            bool const keep = target.desiredOn && row.stillInBook && row.spellId == target.spellId;
            if (!keep && !ContainsId(stale, row.spellId))
                stale.push_back(row.spellId);
        }
    }
    return stale;
}

struct CacheCommit
{
    bool commit = false;
    std::map<uint32_t, bool> rows;
};

inline CacheCommit PlanCacheCommit(
    LoadDecision const& decision,
    std::vector<SourceSpell> const& book,
    ChainLists const& lists)
{
    CacheCommit batch;
    if (!decision.writeAllowed)
        return batch;
    batch.rows = VerifiedCacheRows(decision.chains, book, lists, decision.allowDefaultOn);
    batch.commit = true;
    return batch;
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

struct OrderState
{
    uint32_t loadPumps = 0;
    bool snapshotted = false;
    uint64_t snapshotEventTime = 0;
    bool finished = false;
    uint32_t applies = 0;
};

struct OrderStep
{
    bool snapshot = false;
    bool apply = false;
    bool requeue = false;
    uint32_t delayMs = 0;
};

/* While isBeingLoaded(), do not snapshot and do not apply. The first
 * loaded execution snapshots and requeues by at least 1ms, so that step
 * cannot apply in the same EventProcessor::Update as an IP event that is
 * already due (those still sit later in the multimap). Later executions
 * apply until event time passes the cover. No load pumps: cover is 201ms
 * after the snapshot tick, which is after IP's original +200. Any load
 * pump: IP may have retried, so the cover is the full 2200ms budget.
 */
inline OrderStep AdvanceOrder(OrderState& state, bool beingLoaded, uint64_t eventTime)
{
    OrderStep step;
    if (state.finished)
        return step;
    if (beingLoaded)
    {
        state.loadPumps += 1u;
        step.requeue = true;
        step.delayMs = LoadPollMs;
        return step;
    }
    if (!state.snapshotted)
    {
        state.snapshotted = true;
        state.snapshotEventTime = eventTime;
        step.snapshot = true;
        step.requeue = true;
        step.delayMs = SameUpdateGuardMs;
        return step;
    }

    uint64_t const cover = state.loadPumps > 0 ? static_cast<uint64_t>(IpWorstCaseMs) : static_cast<uint64_t>(NormalCoverMs);
    step.apply = true;
    state.applies += 1u;
    if (eventTime >= state.snapshotEventTime + cover)
    {
        state.finished = true;
        return step;
    }
    step.requeue = true;
    step.delayMs = CoverTickMs;
    return step;
}

enum class DueKind : uint8_t
{
    Snapshot = 1,
    IpCheck,
    Apply
};

struct DueEvent
{
    uint64_t at = 0;
    DueKind kind = DueKind::Snapshot;
};

/* EventProcessor::Update runs due events in ascending exec time. Equal
 * times keep insertion order. This is that due-set, without the running
 * world.
 */
inline std::vector<DueKind> DueThisTick(uint64_t eventTime, std::vector<DueEvent> events)
{
    std::stable_sort(events.begin(), events.end(), [](DueEvent const& left, DueEvent const& right)
    {
        return left.at < right.at;
    });
    std::vector<DueKind> due;
    for (DueEvent const& event : events)
    {
        if (event.at <= eventTime)
            due.push_back(event.kind);
    }
    return due;
}

struct IpRetry
{
    uint8_t attempts = 0;
    bool ranCheck = false;
};

/* Mirrors DelayedPetSpellCheck: while loading and attempts < 10, requeue.
 * The next call runs the check even if the pet is still loading.
 */
inline bool PumpIpWhileLoading(IpRetry& ip, bool beingLoaded)
{
    if (ip.ranCheck)
        return false;
    if (beingLoaded && ip.attempts < IpLoadingAttemptCap)
    {
        ip.attempts = static_cast<uint8_t>(ip.attempts + 1u);
        return false;
    }
    ip.ranCheck = true;
    return true;
}

inline bool ScheduleReplacesOpenSnapshot()
{
    return false;
}
} // namespace NaxxramasCore::HunterPetAutocastCache
