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
    CHECK(NormalCoverMs == 201u);
    CHECK(SameUpdateGuardMs >= 1u);
    CHECK(!CharmBarIsAuthoritativeSavedSpellbook());
    CHECK(!MayTouchDatabase(false));
    CHECK(MayTouchDatabase(true));

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

void CheckLoadDecisions()
{
    ChainLists const lists = Defaults();
    OwnerProof owner;
    owner.lookup = OwnerLookup::Unique;
    owner.creatureEntry = 42719;
    owner.createdBySpell = 1515;
    owner.savetime = 50;

    StoredCacheRow cached;
    cached.chainFirst = 17253;
    cached.on = true;
    cached.creatureEntry = 42719;
    cached.createdBySpell = 1515;
    cached.seenSavetime = 50;
    std::vector<SourceSpell> const petSpell = { Spell(17253, 17253, false), Spell(16827, 16827, true) };
    std::vector<SourceSpell> const charmOnly = { Spell(49966, 49966, true) };
    (void)charmOnly;

    LoadDecision const preferred = DecideLoad(true, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(preferred.origin == SnapshotOrigin::ModuleCache);
    CHECK(preferred.chains.size() == 1u);
    CHECK(preferred.chains.at(17253));
    CHECK(preferred.allowDefaultOn);
    CHECK(!CharmBarIsAuthoritativeSavedSpellbook());

    LoadDecision const fromPet = DecideLoad(true, DatabaseRead::Ok, {}, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(fromPet.origin == SnapshotOrigin::PetSpell);
    CHECK(fromPet.chains.at(17253) == false);
    CHECK(fromPet.chains.at(16827) == true);

    LoadDecision const earlyEmpty = DecideLoad(true, DatabaseRead::NotRun, {}, DatabaseRead::NotRun, {}, owner, false, lists.utility);
    CHECK(earlyEmpty.origin == SnapshotOrigin::Unavailable);
    CHECK(!earlyEmpty.allowDefaultOn);
    CHECK(earlyEmpty.chains.empty());

    OwnerProof missing;
    missing.lookup = OwnerLookup::Absent;
    LoadDecision const abandoned = DecideLoad(true, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, missing, false, lists.utility);
    CHECK(abandoned.origin == SnapshotOrigin::Unavailable);
    CHECK(abandoned.deleteStoredCache);
    CHECK(!abandoned.allowDefaultOn);

    OwnerProof ambiguous;
    ambiguous.lookup = OwnerLookup::Ambiguous;
    ambiguous.creatureEntry = 42719;
    LoadDecision const twoRows = DecideLoad(true, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, ambiguous, false, lists.utility);
    CHECK(twoRows.origin == SnapshotOrigin::Unavailable);
    CHECK(!twoRows.deleteStoredCache);
    CHECK(!twoRows.allowDefaultOn);

    OwnerProof unproven;
    LoadDecision const failedRead = DecideLoad(true, DatabaseRead::Failed, { cached }, DatabaseRead::Failed, {}, unproven, false, lists.utility);
    CHECK(failedRead.origin == SnapshotOrigin::Unavailable);
    CHECK(!failedRead.deleteStoredCache);
    CHECK(!failedRead.allowDefaultOn);

    StoredCacheRow otherPet = cached;
    otherPet.creatureEntry = 99;
    LoadDecision const recycled = DecideLoad(true, DatabaseRead::Ok, { otherPet }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(recycled.origin == SnapshotOrigin::PetSpell);
    CHECK(recycled.deleteStoredCache);
    CHECK(recycled.chains.at(17253) == false);

    StoredCacheRow staleTime = cached;
    staleTime.seenSavetime = 10;
    LoadDecision const drifted = DecideLoad(true, DatabaseRead::Ok, { staleTime }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(drifted.origin == SnapshotOrigin::PetSpell);
    CHECK(!drifted.deleteStoredCache);
    CHECK(drifted.chains.at(17253) == false);

    LoadDecision const reusedBirth = DecideLoad(true, DatabaseRead::Ok, { staleTime }, DatabaseRead::Ok, petSpell, owner, true, lists.utility);
    CHECK(reusedBirth.origin == SnapshotOrigin::NewLife);
    CHECK(reusedBirth.deleteStoredCache);
    CHECK(reusedBirth.chains.empty());
    CHECK(reusedBirth.allowDefaultOn);

    LoadDecision const missingTable = DecideLoad(false, DatabaseRead::Failed, {}, DatabaseRead::Ok, { Spell(17253, 17253, false), Spell(16827, 16827, false) }, owner, true, lists.utility);
    CHECK(missingTable.origin == SnapshotOrigin::PetSpell);
    CHECK(!missingTable.allowDefaultOn);
    CHECK(!missingTable.writeAllowed);
    std::vector<SourceSpell> const liveDamage = {
        Spell(17253, 17253, false),
        Spell(16827, 16827, false),
        Spell(26090, 26090, false),
        Spell(2649, 2649, false),
    };
    CHECK(PlanApply(missingTable.chains, liveDamage, lists, missingTable.allowDefaultOn).empty());

    std::vector<uint32_t> const orphans = OrphanPetNumbers({ 5, 6, 6 }, { 5, 7 }, true);
    CHECK(orphans.size() == 1u);
    CHECK(orphans[0] == 6u);
    CHECK(OrphanPetNumbers({ 5 }, { 1 }, false).empty());
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
    OwnerProof owner;
    owner.lookup = OwnerLookup::Unique;
    owner.creatureEntry = 42719;
    owner.createdBySpell = 1515;
    owner.savetime = 9;
    std::vector<SourceSpell> const savedDefaults = {
        Spell(17253, 17253, false),
        Spell(2649, 2649, false),
        Spell(61684, 61684, false),
        Spell(24604, 24604, false),
    };
    LoadDecision const born = DecideLoad(true, DatabaseRead::Ok, {}, DatabaseRead::Ok, savedDefaults, owner, true, lists.utility);
    CHECK(born.origin == SnapshotOrigin::NewLife);
    CHECK(born.chains.empty());
    CHECK(born.allowDefaultOn);
    std::vector<ApplyAction> const actions = PlanApply(born.chains, savedDefaults, lists, born.allowDefaultOn);
    CHECK(actions.size() == 1u);
    CHECK(actions[0].chainFirst == 17253u);
    CHECK(actions[0].desiredOn);
    CHECK(actions[0].kind == ApplyKind::DefaultOn);
    std::map<uint32_t, bool> const rows = VerifiedCacheRows(born.chains, savedDefaults, lists, born.allowDefaultOn);
    CHECK(rows.size() == 1u);
    CHECK(rows.at(17253));
}

void CheckIdentityAndOrder()
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

    OrderState loading;
    for (uint32_t pump = 0; pump < 4u; ++pump)
    {
        OrderStep const step = AdvanceOrder(loading, true, pump * LoadPollMs);
        CHECK(!step.snapshot);
        CHECK(!step.apply);
        CHECK(step.requeue);
        CHECK(step.delayMs == LoadPollMs);
    }
    CHECK(!loading.snapshotted);

    OrderStep const first = AdvanceOrder(loading, false, 800);
    CHECK(first.snapshot);
    CHECK(!first.apply);
    CHECK(first.delayMs == SameUpdateGuardMs);
    CHECK(loading.applies == 0u);

    uint64_t eventTime = 800;
    while (!loading.finished && loading.applies < 80u)
    {
        eventTime += CoverTickMs;
        OrderStep const step = AdvanceOrder(loading, false, eventTime);
        if (step.apply)
            CHECK(eventTime > loading.snapshotEventTime);
    }
    CHECK(loading.finished);
    CHECK(loading.applies > 1u);
    CHECK(eventTime >= loading.snapshotEventTime + IpWorstCaseMs);

    OrderState fast;
    OrderStep const snap = AdvanceOrder(fast, false, 50);
    CHECK(snap.snapshot);
    CHECK(!snap.apply);
    OrderStep const tooSoon = AdvanceOrder(fast, false, 100);
    CHECK(tooSoon.apply);
    CHECK(tooSoon.requeue);
    CHECK(!fast.finished);
    OrderStep const afterIp = AdvanceOrder(fast, false, 50 + NormalCoverMs);
    CHECK(afterIp.apply);
    CHECK(fast.finished);
    CHECK(fast.loadPumps == 0u);

    std::vector<DueKind> const lag = DueThisTick(1000, { { 0, DueKind::Snapshot }, { 200, DueKind::IpCheck }, { 201, DueKind::Apply } });
    CHECK(lag.size() == 3u);
    CHECK(lag[0] == DueKind::Snapshot);
    CHECK(lag[1] == DueKind::IpCheck);
    CHECK(lag[2] == DueKind::Apply);
    std::vector<DueKind> const early = DueThisTick(50, { { 0, DueKind::Snapshot }, { 200, DueKind::IpCheck }, { 201, DueKind::Apply } });
    CHECK(early.size() == 1u);
    CHECK(early[0] == DueKind::Snapshot);

    IpRetry ip;
    for (uint8_t attempt = 0; attempt < IpLoadingAttemptCap; ++attempt)
        CHECK(!PumpIpWhileLoading(ip, true));
    CHECK(!ip.ranCheck);
    CHECK(PumpIpWhileLoading(ip, true));
    CHECK(ip.ranCheck);
    CHECK(!PumpIpWhileLoading(ip, false));
}

void CheckLiveBookKeepsSavedRankChoice()
{
    ChainLists const lists = Defaults();
    std::vector<SourceSpell> const before = { Spell(17253, 17261, true), Spell(2649, 2649, true) };
    std::map<uint32_t, bool> const snap = CollapseLiveBook(before, lists.utility);
    CHECK(snap.at(17253));
    CHECK(snap.find(2649) == snap.end());
    std::vector<SourceSpell> const afterIp = { Spell(17253, 27050, false), Spell(17253, 17261, true, true) };
    std::vector<ApplyAction> const actions = PlanApply(snap, afterIp, lists);
    CHECK(actions.size() == 1u);
    CHECK(actions[0].spellId == 27050u);
    CHECK(actions[0].desiredOn);
    CHECK(actions[0].kind == ApplyKind::Restore);

    std::vector<ReconcileTarget> const owned = PlanReconcile(snap, afterIp, lists, true);
    CHECK(owned.size() == 1u);
    std::vector<AutocastEntry> const autos = {
        { 17261, 17253, false },
        { 27050, 17253, true },
        { 2649, 2649, true },
    };
    std::vector<uint32_t> const stale = StaleAutocastIds(autos, owned);
    CHECK(stale.size() == 1u);
    CHECK(stale[0] == 17261u);
    CHECK(StaleAutocastIds({ { 27050, 17253, true } }, owned).empty());

    LoadDecision decision;
    decision.writeAllowed = true;
    decision.allowDefaultOn = true;
    decision.chains = snap;
    CacheCommit const batch = PlanCacheCommit(decision, afterIp, lists);
    CHECK(batch.commit);
    CHECK(batch.rows.size() == 1u);
    CHECK(batch.rows.at(17253));
    decision.writeAllowed = false;
    CHECK(!PlanCacheCommit(decision, afterIp, lists).commit);
}
} // namespace

int main()
{
    CheckConfigAndPins();
    CheckAccounts();
    CheckLists();
    CheckLoadDecisions();
    CheckPlans();
    CheckVerifiedRowsDoNotCopyPostIpOff();
    CheckNoMigration();
    CheckTameDefaultsNewDamageOnly();
    CheckIdentityAndOrder();
    CheckLiveBookKeepsSavedRankChoice();

    if (g_failures != 0)
    {
        std::fprintf(stderr, "A02_S4_POLICY_FAIL checks=%d failures=%d\n", g_checks, g_failures);
        return 1;
    }
    std::printf("A02_S4_POLICY_OK checks=%d\n", g_checks);
    return 0;
}
