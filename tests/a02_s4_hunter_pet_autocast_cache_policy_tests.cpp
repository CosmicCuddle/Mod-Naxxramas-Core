/* Policy tests for the default-off hunter pet autocast cache.
 * No worldserver, SQL connection, or DBC. A pass is not an in-game summon.
 */

#include "HunterPetAutocastCache.h"

#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>

namespace
{
int g_failures = 0;
int g_checks = 0;

#define CHECK(cond)                                                                 \
    do                                                                              \
    {                                                                               \
        ++g_checks;                                                                 \
        if (!(cond))                                                                \
        {                                                                           \
            std::fprintf(stderr, "CHECK failed %s:%d: %s\n", __FILE__, __LINE__, #cond); \
            ++g_failures;                                                           \
        }                                                                           \
    } while (0)

using namespace NaxxramasCore::HunterPetAutocastCache;

SourceSpell Spell(uint32_t chain, uint32_t id, bool on, bool removed = false, bool autocastable = true)
{
    SourceSpell row;
    row.chainFirst = chain;
    row.spellId = id;
    row.autocastable = autocastable;
    row.removed = removed;
    row.autocastOn = on;
    return row;
}

ChainLists Defaults()
{
    ChainLists lists;
    lists.damage = DefaultDamageIds();
    lists.utility = DefaultUtilityIds();
    return lists;
}

void CheckConfigAndPins()
{
    CHECK(std::strcmp(PinnedCoreOldSha, "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7") == 0);
    CHECK(std::strcmp(PinnedCoreNewSha, "8daffdabe9202c228e45d833c9a1d399597a15cd") == 0);
    CHECK(std::strcmp(PinnedIndividualProgressionSha, "4ff4b5fcc1480348f058c632573143e62d4e3a41") == 0);
    CHECK(std::strcmp(EnabledConfigKey, "NaxxramasCore.HunterPet.AutocastCache.Enabled") == 0);
    CHECK(std::strcmp(DefaultEnabledRaw, "0") == 0);
    CHECK(!EnabledFromRaw("0"));
    CHECK(!EnabledFromRaw(" 0 "));
    CHECK(EnabledFromRaw("1"));
    CHECK(!EnabledFromRaw("true"));
    CHECK(!EnabledFromRaw(nullptr));
    CHECK(!UsesProcessGlobalPetMap());
    CHECK(!ScheduleReplacesOpenSnapshot());
    CHECK(IpWorstCaseMs == 2200u);
    CHECK(RestoreWindowMs == 3000u);
    CHECK(AppliesWhileCoveringIpWorstCase() > 1u);

    std::vector<uint32_t> const parsedDamage = ParseSpellIds(DefaultDamageSpellIdsRaw);
    std::vector<uint32_t> const parsedUtility = ParseSpellIds(DefaultUtilitySpellIdsRaw);
    CHECK(parsedDamage == DefaultDamageIds());
    CHECK(parsedUtility == DefaultUtilityIds());
    CHECK(ParseSpellIds(DefaultOptionalSpellIdsRaw).empty());
    CHECK(ParseSpellIds("17253, no, 16827, 17253").size() == 2u);
    CHECK(ParseSpellIds(nullptr).empty());
    CHECK(ParseSpellIds("").empty());
}

void CheckAccounts()
{
    CHECK(ClassifyAccount(true, "RNDBOT1", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedBot);
    CHECK(ClassifyAccount(true, "Hunter", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedHuman);
    CHECK(ClassifyAccount(false, "Hunter", DefaultBotAccountsRegex) == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, "Hunter", "") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, "Hunter", "(") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, nullptr, DefaultBotAccountsRegex) == AccountVerdict::Ineligible);
    CHECK(!IsEligibleHumanAccount(AccountVerdict::ConfirmedBot));
    CHECK(!IsEligibleHumanAccount(AccountVerdict::Ineligible));
    CHECK(IsEligibleHumanAccount(AccountVerdict::ConfirmedHuman));
}

void CheckLists()
{
    ChainLists const lists = Defaults();
    CHECK(ContainsId(lists.damage, 17253));
    CHECK(ContainsId(lists.damage, 24423));
    CHECK(ContainsId(lists.damage, 26090));
    CHECK(ContainsId(lists.damage, 56626));
    CHECK(!ContainsId(lists.damage, 26094));
    CHECK(!ContainsId(lists.damage, 2649));
    CHECK(!ContainsId(lists.damage, 24604));
    CHECK(!ContainsId(lists.damage, 53508));
    CHECK(!ContainsId(lists.damage, 4167));
    CHECK(!ContainsId(lists.damage, 58604));
    CHECK(!ContainsId(lists.damage, BadAttitudeFirstRank));
    CHECK(!ContainsId(lists.damage, RakeFirstRank));
    CHECK(ContainsId(lists.utility, 2649));
    CHECK(ContainsId(lists.utility, 26094));
    CHECK(ContainsId(lists.utility, 35346));
    CHECK(!ContainsId(lists.utility, 26090));
    for (uint32_t id : JudgementFirstRanks)
    {
        CHECK(!ContainsId(lists.damage, id));
        CHECK(!ContainsId(lists.utility, id));
    }
    CHECK(lists.optionalOn.empty());
}

void CheckSnapshotPriority()
{
    ChainLists const lists = Defaults();
    std::vector<SourceSpell> const cache = { Spell(17253, 17253, true), Spell(2649, 2649, true) };
    std::vector<SourceSpell> const petSpell = { Spell(17253, 17253, false), Spell(16827, 16827, true) };
    std::vector<SourceSpell> const charm = { Spell(49966, 49966, true) };

    SnapshotResult const preferred = ChooseLoadSnapshot(cache, petSpell, charm, lists.utility);
    CHECK(preferred.origin == SnapshotOrigin::ModuleCache);
    CHECK(preferred.chains.size() == 1u);
    CHECK(preferred.chains.at(17253));
    CHECK(preferred.chains.find(2649) == preferred.chains.end());
    CHECK(preferred.chains.find(16827) == preferred.chains.end());

    SnapshotResult const fromPet = ChooseLoadSnapshot({}, petSpell, charm, lists.utility);
    CHECK(fromPet.origin == SnapshotOrigin::PetSpell);
    CHECK(fromPet.chains.at(17253) == false);
    CHECK(fromPet.chains.at(16827) == true);

    SnapshotResult const fromCharm = ChooseLoadSnapshot({}, {}, charm, lists.utility);
    CHECK(fromCharm.origin == SnapshotOrigin::CharmBar);
    CHECK(fromCharm.chains.at(49966));

    SnapshotResult const none = ChooseLoadSnapshot({}, {}, {}, lists.utility);
    CHECK(none.origin == SnapshotOrigin::Empty);
    CHECK(none.chains.empty());

    std::vector<SourceSpell> const onWins = { Spell(17253, 17255, false), Spell(17253, 17253, true, true) };
    SnapshotResult const ignoredRemoved = ChooseLoadSnapshot({}, onWins, {}, lists.utility);
    CHECK(ignoredRemoved.chains.at(17253) == false);
}

void CheckPlans()
{
    ChainLists lists = Defaults();
    std::map<uint32_t, bool> savedOff;
    savedOff[17253] = false;
    savedOff[24604] = true;
    std::vector<SourceSpell> book = {
        Spell(17253, 27050, true),
        Spell(16827, 16827, false),
        Spell(2649, 2649, false),
        Spell(24604, 24604, false),
        Spell(26090, 26090, false),
        Spell(26094, 26189, false),
        Spell(59881, 59881, false),
        Spell(50433, 50433, false),
        Spell(17253, 17253, true, true),
    };

    std::vector<ApplyAction> const actions = PlanApply(savedOff, book, lists);
    bool sawBiteOff = false;
    bool sawClawOn = false;
    bool sawHowl = false;
    bool sawPummel = false;
    for (ApplyAction const& action : actions)
    {
        CHECK(action.chainFirst != 2649u);
        CHECK(action.chainFirst != 26094u);
        CHECK(action.chainFirst != 59881u);
        CHECK(action.chainFirst != 50433u);
        CHECK(action.spellId != 17253u);
        if (action.chainFirst == 17253u)
        {
            sawBiteOff = action.desiredOn == false && action.kind == ApplyKind::Restore && action.spellId == 27050u;
        }
        if (action.chainFirst == 16827u)
            sawClawOn = action.desiredOn && action.kind == ApplyKind::DefaultOn;
        if (action.chainFirst == 24604u)
            sawHowl = true;
        if (action.chainFirst == 26090u)
            sawPummel = action.desiredOn && action.kind == ApplyKind::DefaultOn;
    }
    CHECK(sawBiteOff);
    CHECK(sawClawOn);
    CHECK(sawHowl);
    CHECK(sawPummel);

    std::vector<SourceSpell> restored = book;
    for (SourceSpell& row : restored)
    {
        if (row.chainFirst == 17253u && !row.removed)
            row.autocastOn = false;
        if (row.chainFirst == 16827u)
            row.autocastOn = true;
        if (row.chainFirst == 24604u)
            row.autocastOn = true;
        if (row.chainFirst == 26090u)
            row.autocastOn = true;
    }
    CHECK(PlanApply(savedOff, restored, lists).empty());

    lists.optionalOn.push_back(58604);
    std::vector<SourceSpell> const lava = { Spell(58604, 58604, false) };
    std::vector<ApplyAction> const lavaActions = PlanApply({}, lava, lists);
    CHECK(lavaActions.size() == 1u);
    CHECK(lavaActions[0].desiredOn);
    CHECK(lavaActions[0].kind == ApplyKind::DefaultOn);

    ChainLists const plain = Defaults();
    CHECK(PlanApply({}, lava, plain).empty());
}

void CheckVerifiedRowsDoNotCopyPostIpOff()
{
    ChainLists const lists = Defaults();
    std::map<uint32_t, bool> snapshot;
    snapshot[17253] = true;
    std::vector<SourceSpell> const postIp = {
        Spell(17253, 27050, false),
        Spell(16827, 16827, false),
        Spell(2649, 61676, true),
    };
    std::map<uint32_t, bool> const rows = VerifiedCacheRows(snapshot, postIp, lists);
    CHECK(rows.at(17253));
    CHECK(rows.at(16827));
    CHECK(rows.find(2649) == rows.end());

    std::map<uint32_t, bool> const toggles = PlayerToggleRows(postIp, lists.utility);
    CHECK(toggles.at(17253) == false);
    CHECK(toggles.at(16827) == false);
    CHECK(toggles.find(2649) == toggles.end());
    CHECK(!AllowCacheWrite(WriteCause::PlayerSave, true));
    CHECK(AllowCacheWrite(WriteCause::PlayerSave, false));
    CHECK(AllowCacheWrite(WriteCause::Snapshot, true));
    CHECK(AllowCacheWrite(WriteCause::VerifiedRestore, true));
}

void CheckNoMigration()
{
    ChainLists const lists = Defaults();
    std::map<uint32_t, bool> const saved = CollapseChains(
        { Spell(17253, 17253, false), Spell(16827, 16827, false), Spell(2649, 2649, false) },
        lists.utility);
    std::vector<SourceSpell> const book = { Spell(17253, 17253, false), Spell(16827, 16827, false) };
    CHECK(PlanApply(saved, book, lists).empty());
    CHECK(saved.find(2649) == saved.end());
}

void CheckTameDefaultsNewDamageOnly()
{
    ChainLists const lists = Defaults();
    SnapshotResult const live = CollapseLiveBook({}, lists.utility);
    CHECK(live.origin == SnapshotOrigin::Empty);
    std::vector<SourceSpell> const learned = {
        Spell(17253, 17253, false),
        Spell(2649, 2649, false),
        Spell(61684, 61684, false),
        Spell(24604, 24604, false),
    };
    std::vector<ApplyAction> const actions = PlanApply(live.chains, learned, lists);
    CHECK(actions.size() == 1u);
    CHECK(actions[0].chainFirst == 17253u);
    CHECK(actions[0].desiredOn);
    std::map<uint32_t, bool> const rows = VerifiedCacheRows(live.chains, learned, lists);
    CHECK(rows.size() == 1u);
    CHECK(rows.at(17253));
}

void CheckIdentityAndClock()
{
    Binding bound;
    bound.ownerGuid = 5;
    bound.petGuid = 9;
    bound.petNumber = 100;
    Binding live = bound;
    live.petNumber = 200;
    CHECK(CheckIdentity(bound, live, false, true, false, false) == IdentityResult::UpdatedNumber);
    CHECK(bound.petNumber == 200u);
    CHECK(CheckIdentity(bound, live, true, true, false, false) == IdentityResult::Ok);
    live.petNumber = 300;
    CHECK(CheckIdentity(bound, live, true, true, false, false) == IdentityResult::Abort);
    live = bound;
    CHECK(CheckIdentity(bound, live, true, false, false, false) == IdentityResult::Abort);
    CHECK(CheckIdentity(bound, live, true, true, true, false) == IdentityResult::Abort);
    CHECK(CheckIdentity(bound, live, true, true, false, true) == IdentityResult::Abort);
    live.petGuid = 10;
    CHECK(CheckIdentity(bound, live, false, true, false, false) == IdentityResult::Abort);

    Clock clock;
    TickDecision const loading = OnTick(clock, true);
    CHECK(!loading.apply);
    CHECK(loading.requeue);
    CHECK(!clock.open);
    CHECK(clock.elapsedMs == 0u);
    TickDecision const first = OnTick(clock, false);
    CHECK(first.apply);
    CHECK(first.requeue);
    CHECK(clock.open);
    CHECK(clock.elapsedMs == 0u);
    uint32_t applies = 1;
    while (!clock.done && applies < 40u)
    {
        TickDecision const tick = OnTick(clock, false);
        if (tick.apply)
            ++applies;
    }
    CHECK(clock.done);
    CHECK(clock.elapsedMs == RestoreWindowMs);
    CHECK(clock.elapsedMs > IpWorstCaseMs);
    CHECK(applies > 1u);
}

void CheckLiveBookKeepsSavedRankChoice()
{
    ChainLists const lists = Defaults();
    std::vector<SourceSpell> const before = { Spell(17253, 17261, true), Spell(2649, 2649, true) };
    SnapshotResult const snap = CollapseLiveBook(before, lists.utility);
    CHECK(snap.origin == SnapshotOrigin::LiveBook);
    CHECK(snap.chains.at(17253));
    CHECK(snap.chains.find(2649) == snap.chains.end());
    std::vector<SourceSpell> const afterIp = { Spell(17253, 27050, false), Spell(17253, 17261, true, true) };
    std::vector<ApplyAction> const actions = PlanApply(snap.chains, afterIp, lists);
    CHECK(actions.size() == 1u);
    CHECK(actions[0].spellId == 27050u);
    CHECK(actions[0].desiredOn);
    CHECK(actions[0].kind == ApplyKind::Restore);
}
} // namespace

int main()
{
    CheckConfigAndPins();
    CheckAccounts();
    CheckLists();
    CheckSnapshotPriority();
    CheckPlans();
    CheckVerifiedRowsDoNotCopyPostIpOff();
    CheckNoMigration();
    CheckTameDefaultsNewDamageOnly();
    CheckIdentityAndClock();
    CheckLiveBookKeepsSavedRankChoice();

    if (g_failures != 0)
    {
        std::fprintf(stderr, "A02_S4_POLICY_FAIL checks=%d failures=%d\n", g_checks, g_failures);
        return 1;
    }
    std::printf("A02_S4_POLICY_OK checks=%d\n", g_checks);
    return 0;
}
