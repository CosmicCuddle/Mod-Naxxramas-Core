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
    CHECK(std::strcmp(PinnedPlayerbotsSha, "037c01418b5d01506917a3db9b44fd56ac5f965c") == 0);
    CHECK(!MissingPlayerbotApiMayMutatePet());
    CHECK(!FunctionalOnOffPersistenceIsComplete());
    CHECK(std::strcmp(FunctionalPersistenceBlocker, "BLOCKED: functional ON/OFF persistence is not complete") == 0);
    CHECK(std::strcmp(SameEntryRecycleBlocker, "BLOCKED: same-entry recycled number and savetime are indistinguishable") == 0);
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
    CHECK(std::strcmp(RestoreUtilityKey, "NaxxramasCore.HunterPet.AutocastCache.RestoreUtility") == 0);
    CHECK(std::strcmp(DefaultRestoreUtilityRaw, "0") == 0);
    CHECK(!EnabledFromRaw(DefaultRestoreUtilityRaw));
    CHECK(std::strcmp(ManualCacheSqlPath, "docs/install/manual_hunter_pet_autocast_cache.sql") == 0);
    CHECK(!NullQueryResultIsVerifiedEmpty());
    CHECK(!VoidCommitTransactionIsSuccessSignal());
    CHECK(!DirectCommitExposesErrorCode());
    CHECK(AsyncCommitCallbackBoolIsSuccessSignal());
    CHECK(!MarkWriteVerified(false, true));
    CHECK(!MarkWriteVerified(true, false));
    CHECK(MarkWriteVerified(true, true));
    CHECK(!MarkSavetimeRebound(false, true));
    CHECK(!MarkSavetimeRebound(true, false));
    CHECK(MarkSavetimeRebound(true, true));
    CHECK(!PacketBeforeHandlerIsAcceptedChoice());
    CHECK(!MayApplyFromPlayerSave());
    CHECK(!DismissBeforeApplyPreservesChoice());
    CHECK(!MayPersistChoiceBeforeSingleApply(0));
    CHECK(MayPersistChoiceBeforeSingleApply(MaxApplies));
    CHECK(SameEntryRecycleAfterSavetimeRebindIsIndistinguishable());
    CountRead const failedCount = InterpretCountQuery(false, 0);
    CHECK(failedCount.status == DatabaseRead::Failed);
    CHECK(!failedCount.verifiedEmpty);
    CountRead const emptyCount = InterpretCountQuery(true, 0);
    CHECK(emptyCount.status == DatabaseRead::Ok);
    CHECK(emptyCount.verifiedEmpty);
    CountRead const someCount = InterpretCountQuery(true, 3);
    CHECK(someCount.status == DatabaseRead::Ok);
    CHECK(!someCount.verifiedEmpty);
    CHECK(someCount.count == 3u);
    CHECK(InterpretSchemaCount(false, 0) == SchemaProbe::Unknown);
    CHECK(InterpretSchemaCount(true, 0) == SchemaProbe::Absent);
    CHECK(InterpretSchemaCount(true, 3) == SchemaProbe::Absent);
    CHECK(InterpretSchemaCount(true, ExpectedCacheColumnCount) == SchemaProbe::Present);

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

    CHECK(IsRealPlayerAtPin(PlayerbotIdentity::RealPlayer));
    CHECK(!IsRealPlayerAtPin(PlayerbotIdentity::Playerbot));
    CHECK(!IsRealPlayerAtPin(PlayerbotIdentity::SelfBot));
    CHECK(!IsRealPlayerAtPin(PlayerbotIdentity::Unavailable));
    CHECK(!MayMutateHunterPet(PlayerbotIdentity::Playerbot, AccountVerdict::ConfirmedHuman));
    CHECK(!MayMutateHunterPet(PlayerbotIdentity::SelfBot, AccountVerdict::ConfirmedHuman));
    CHECK(!MayMutateHunterPet(PlayerbotIdentity::SelfBot, AccountVerdict::ConfirmedBot));
    CHECK(!MayMutateHunterPet(PlayerbotIdentity::RealPlayer, AccountVerdict::ConfirmedBot));
    CHECK(!MayMutateHunterPet(PlayerbotIdentity::Unavailable, AccountVerdict::ConfirmedHuman));
    CHECK(!MayMutateHunterPet(PlayerbotIdentity::RealPlayer, AccountVerdict::Ineligible));
    CHECK(MayMutateHunterPet(PlayerbotIdentity::RealPlayer, AccountVerdict::ConfirmedHuman));
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
    owner.liveBound = true;
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

    LoadDecision const preferred = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(preferred.origin == SnapshotOrigin::ModuleCache);
    CHECK(preferred.chains.size() == 1u);
    CHECK(preferred.chains.at(17253));
    CHECK(preferred.allowDefaultOn);
    CHECK(!CharmBarIsAuthoritativeSavedSpellbook());

    LoadDecision const fromPet = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, {}, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(fromPet.origin == SnapshotOrigin::PetSpell);
    CHECK(fromPet.chains.at(17253) == false);
    CHECK(fromPet.chains.at(16827) == true);

    LoadDecision const earlyEmpty = DecideLoad(SchemaProbe::Present, DatabaseRead::NotRun, {}, DatabaseRead::NotRun, {}, owner, false, lists.utility);
    CHECK(earlyEmpty.origin == SnapshotOrigin::Unavailable);
    CHECK(!earlyEmpty.allowDefaultOn);
    CHECK(earlyEmpty.chains.empty());

    OwnerProof missing;
    missing.lookup = OwnerLookup::Absent;
    LoadDecision const abandoned = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, missing, false, lists.utility);
    CHECK(abandoned.origin == SnapshotOrigin::Unavailable);
    CHECK(abandoned.deleteStoredCache);
    CHECK(!abandoned.allowDefaultOn);

    OwnerProof ambiguous;
    ambiguous.lookup = OwnerLookup::Ambiguous;
    ambiguous.creatureEntry = 42719;
    LoadDecision const twoRows = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, ambiguous, false, lists.utility);
    CHECK(twoRows.origin == SnapshotOrigin::Unavailable);
    CHECK(!twoRows.deleteStoredCache);
    CHECK(!twoRows.allowDefaultOn);

    OwnerProof unproven;
    LoadDecision const failedRead = DecideLoad(SchemaProbe::Present, DatabaseRead::Failed, { cached }, DatabaseRead::Failed, {}, unproven, false, lists.utility);
    CHECK(failedRead.origin == SnapshotOrigin::Unavailable);
    CHECK(!failedRead.deleteStoredCache);
    CHECK(!failedRead.allowDefaultOn);

    StoredCacheRow otherPet = cached;
    otherPet.creatureEntry = 99;
    LoadDecision const recycled = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, { otherPet }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(recycled.origin == SnapshotOrigin::PetSpell);
    CHECK(recycled.deleteStoredCache);
    CHECK(recycled.chains.at(17253) == false);

    StoredCacheRow staleTime = cached;
    staleTime.seenSavetime = 10;
    LoadDecision const drifted = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, { staleTime }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(drifted.origin == SnapshotOrigin::PetSpell);
    CHECK(!drifted.deleteStoredCache);
    CHECK(drifted.chains.at(17253) == false);

    LoadDecision const reusedBirth = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, { staleTime }, DatabaseRead::Ok, petSpell, owner, true, lists.utility);
    CHECK(reusedBirth.origin == SnapshotOrigin::NewLife);
    CHECK(reusedBirth.deleteStoredCache);
    CHECK(reusedBirth.chains.empty());
    CHECK(reusedBirth.allowDefaultOn);

    LoadDecision const missingTable = DecideLoad(SchemaProbe::Absent, DatabaseRead::Failed, {}, DatabaseRead::Ok, { Spell(17253, 17253, false), Spell(16827, 16827, false) }, owner, true, lists.utility);
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

    LoadDecision const nullCache = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Failed, {}, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(nullCache.origin == SnapshotOrigin::Unavailable);
    CHECK(nullCache.chains.empty());
    CHECK(!nullCache.allowDefaultOn);
    CHECK(!nullCache.writeAllowed);
    CHECK(!nullCache.deleteStoredCache);
    CHECK(PlanApply(nullCache.chains, petSpell, lists, nullCache.allowDefaultOn).empty());

    LoadDecision const nullPetSpell = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, {}, DatabaseRead::Failed, {}, owner, false, lists.utility);
    CHECK(nullPetSpell.origin == SnapshotOrigin::Unavailable);
    CHECK(!nullPetSpell.allowDefaultOn);
    CHECK(!nullPetSpell.writeAllowed);

    LoadDecision const unknownSchema = DecideLoad(
        SchemaProbe::Unknown, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, owner, true, lists.utility);
    CHECK(unknownSchema.origin == SnapshotOrigin::Unavailable);
    CHECK(!unknownSchema.allowDefaultOn);
    CHECK(!unknownSchema.deleteStoredCache);
    CHECK(unknownSchema.chains.empty());
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
    owner.liveBound = true;
    owner.creatureEntry = 42719;
    owner.createdBySpell = 1515;
    owner.savetime = 9;
    std::vector<SourceSpell> const savedDefaults = {
        Spell(17253, 17253, false),
        Spell(2649, 2649, false),
        Spell(61684, 61684, false),
        Spell(24604, 24604, false),
    };
    LoadDecision const born = DecideLoad(SchemaProbe::Present, DatabaseRead::Ok, {}, DatabaseRead::Ok, savedDefaults, owner, true, lists.utility);
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
    CHECK(loading.applies == MaxApplies);
    CHECK(eventTime >= loading.snapshotEventTime + IpWorstCaseMs);
    OrderStep const loadAgain = AdvanceOrder(loading, false, eventTime + 1000);
    CHECK(!loadAgain.apply);
    CHECK(!loadAgain.requeue);
    CHECK(loading.applies == MaxApplies);

    OrderState fast;
    OrderStep const snap = AdvanceOrder(fast, false, 50);
    CHECK(snap.snapshot);
    CHECK(!snap.apply);
    OrderStep const tooSoon = AdvanceOrder(fast, false, 100);
    CHECK(!tooSoon.apply);
    CHECK(tooSoon.requeue);
    CHECK(!fast.finished);
    CHECK(fast.applies == 0u);
    OrderStep const afterIp = AdvanceOrder(fast, false, 50 + NormalCoverMs);
    CHECK(afterIp.apply);
    CHECK(fast.finished);
    CHECK(fast.applies == MaxApplies);
    CHECK(fast.loadPumps == 0u);
    OrderStep const second = AdvanceOrder(fast, false, 50 + NormalCoverMs + CoverTickMs);
    CHECK(!second.apply);
    CHECK(!second.requeue);
    CHECK(fast.applies == MaxApplies);

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

void CheckUtilityPreferenceFlag()
{
    ChainLists off = Defaults();
    CHECK(!off.restoreUtility);
    ChainLists on = off;
    on.restoreUtility = true;

    std::vector<SourceSpell> const before = {
        Spell(2649, 2649, true),
        Spell(1742, 1742, false),
        Spell(17253, 17253, true),
    };
    std::map<uint32_t, bool> const snapOff = CollapseChains(before, off.utility, off.restoreUtility);
    std::map<uint32_t, bool> const snapOn = CollapseChains(before, on.utility, on.restoreUtility);
    CHECK(snapOff.find(2649) == snapOff.end());
    CHECK(snapOff.find(1742) == snapOff.end());
    CHECK(snapOff.at(17253));
    CHECK(snapOn.at(2649));
    CHECK(snapOn.at(1742) == false);
    CHECK(snapOn.at(17253));

    std::vector<SourceSpell> const after = {
        Spell(2649, 14927, false),
        Spell(1742, 1742, true),
        Spell(61684, 61684, false),
        Spell(17253, 27050, false),
    };
    std::vector<ApplyAction> const untouched = PlanApply(snapOff, after, off, true);
    for (ApplyAction const& action : untouched)
    {
        CHECK(action.chainFirst != 2649u);
        CHECK(action.chainFirst != 1742u);
        CHECK(action.chainFirst != 61684u);
    }
    std::map<uint32_t, bool> const offRows = VerifiedCacheRows(snapOff, after, off, true);
    CHECK(offRows.find(2649) == offRows.end());
    CHECK(offRows.find(1742) == offRows.end());
    CHECK(offRows.find(61684) == offRows.end());
    CHECK(PlanReconcile(snapOff, after, off, true).size() >= 1u);
    for (ReconcileTarget const& target : PlanReconcile(snapOff, after, off, true))
        CHECK(!ContainsId(off.utility, target.chainFirst));

    std::vector<ApplyAction> const restored = PlanApply(snapOn, after, on, true);
    bool growlOn = false;
    bool cowerOff = false;
    bool dash = false;
    for (ApplyAction const& action : restored)
    {
        CHECK(action.chainFirst != 61684u);
        if (action.chainFirst == 2649u)
            growlOn = action.desiredOn && action.kind == ApplyKind::Restore && action.spellId == 14927u;
        if (action.chainFirst == 1742u)
            cowerOff = !action.desiredOn && action.kind == ApplyKind::Restore;
        if (action.chainFirst == 61684u)
            dash = true;
    }
    CHECK(growlOn);
    CHECK(cowerOff);
    CHECK(!dash);
    CHECK(!EligibleForDefaultOn(2649, on));
    CHECK(EligibleForPreferenceRestore(2649, on));
    CHECK(!EligibleForPreferenceRestore(2649, off));
    CHECK(EligibleForDefaultOn(17253, off));
    std::map<uint32_t, bool> const written = VerifiedCacheRows(snapOn, after, on, true);
    CHECK(written.at(2649));
    CHECK(written.at(1742) == false);
    CHECK(written.find(61684) == written.end());
    std::vector<ApplyAction> const newUtility = PlanApply({}, { Spell(61684, 61684, false), Spell(2649, 2649, false) }, on, true);
    CHECK(newUtility.empty());
    CHECK(PlanApply({}, { Spell(61684, 61684, false) }, off, true).empty());
}

void CheckReconcileLeavesOtherSpells()
{
    ChainLists lists = Defaults();
    std::map<uint32_t, bool> snapshot;
    snapshot[17253] = true;
    std::vector<SourceSpell> const book = {
        Spell(17253, 27050, false),
        Spell(17253, 17261, true, true),
        Spell(2649, 2649, true),
        Spell(24604, 24604, true),
        Spell(99901, 99901, true),
    };
    std::vector<ReconcileTarget> const targets = PlanReconcile(snapshot, book, lists, true);
    CHECK(targets.size() == 1u);
    CHECK(targets[0].chainFirst == 17253u);
    CHECK(targets[0].spellId == 27050u);
    CHECK(targets[0].desiredOn);

    LiveAutocastState state;
    state.activeBySpell[27050] = false;
    state.activeBySpell[2649] = true;
    state.activeBySpell[24604] = true;
    state.activeBySpell[99901] = true;
    state.autospells = { 17261, 27050, 2649, 24604, 99901 };
    LiveAutocastState const after = ApplyReconcileModel(state, book, targets);
    CHECK(after.activeBySpell.at(27050));
    CHECK(after.activeBySpell.at(2649));
    CHECK(after.activeBySpell.at(24604));
    CHECK(after.activeBySpell.at(99901));
    CHECK(std::find(after.autospells.begin(), after.autospells.end(), 2649u) != after.autospells.end());
    CHECK(std::find(after.autospells.begin(), after.autospells.end(), 24604u) != after.autospells.end());
    CHECK(std::find(after.autospells.begin(), after.autospells.end(), 99901u) != after.autospells.end());
    CHECK(std::find(after.autospells.begin(), after.autospells.end(), 17261u) == after.autospells.end());

    lists.restoreUtility = true;
    std::map<uint32_t, bool> utilitySnap;
    utilitySnap[2649] = false;
    std::vector<ReconcileTarget> const utilityTargets = PlanReconcile(utilitySnap, book, lists, false);
    bool growl = false;
    bool other = false;
    for (ReconcileTarget const& target : utilityTargets)
    {
        if (target.chainFirst == 2649u)
            growl = !target.desiredOn;
        if (target.chainFirst == 24604u || target.chainFirst == 99901u)
            other = true;
    }
    CHECK(growl);
    CHECK(!other);
    LiveAutocastState utilityState = state;
    LiveAutocastState const utilityAfter = ApplyReconcileModel(utilityState, book, utilityTargets);
    CHECK(utilityAfter.activeBySpell.at(2649) == false);
    CHECK(utilityAfter.activeBySpell.at(24604));
    CHECK(utilityAfter.activeBySpell.at(99901));
    CHECK(utilityAfter.activeBySpell.at(27050) == false);
    CHECK(std::find(utilityAfter.autospells.begin(), utilityAfter.autospells.end(), 24604u) != utilityAfter.autospells.end());
    CHECK(std::find(utilityAfter.autospells.begin(), utilityAfter.autospells.end(), 99901u) != utilityAfter.autospells.end());
}

void CheckCoverClickDismissAndRelog()
{
    CoverClickResult const during = ClickDuringCoverBeforeApply();
    CHECK(during.singleApplyUsesSnapshot);
    CHECK(!during.clickPreserved);
    CHECK(during.blockedModuleOnly);

    OrderState cover;
    CHECK(AdvanceOrder(cover, false, 1000).snapshot);
    OrderStep const mid = AdvanceOrder(cover, false, 1000 + 100);
    CHECK(!mid.apply);
    CHECK(cover.applies == 0u);
    CHECK(!MayPersistChoiceBeforeSingleApply(cover.applies));
    CHECK(!DismissBeforeApplyPreservesChoice());
    OrderStep const once = AdvanceOrder(cover, false, 1000 + NormalCoverMs);
    CHECK(once.apply);
    CHECK(cover.applies == MaxApplies);
    CHECK(cover.finished);
    CoverClickResult const after = ClickAfterSingleApply(cover.applies);
    CHECK(after.clickPreserved);
    CHECK(!after.singleApplyUsesSnapshot);
    CHECK(!after.blockedModuleOnly);
    CHECK(!AdvanceOrder(cover, false, 1000 + NormalCoverMs + 500).apply);

    ChainLists const lists = Defaults();
    std::map<uint32_t, bool> const snapshot = { { 17253, true } };
    std::vector<SourceSpell> const clickedOff = { Spell(17253, 27050, false) };
    std::vector<ApplyAction> const overwrite = PlanApply(snapshot, clickedOff, lists, false);
    CHECK(overwrite.size() == 1u);
    CHECK(overwrite[0].desiredOn);
    CHECK(overwrite[0].kind == ApplyKind::Restore);
    CHECK(!MayApplyFromPlayerSave());

    OwnerProof owner;
    owner.lookup = OwnerLookup::Unique;
    owner.liveBound = true;
    owner.creatureEntry = 42719;
    owner.createdBySpell = 1515;
    owner.savetime = 80;
    StoredCacheRow stale = {};
    stale.chainFirst = 17253;
    stale.on = true;
    stale.creatureEntry = 42719;
    stale.createdBySpell = 1515;
    stale.seenSavetime = 50;
    std::vector<SourceSpell> const savedOff = { Spell(17253, 17253, false) };
    LoadDecision const dismissed = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { stale }, DatabaseRead::Ok, savedOff, owner, false, lists.utility);
    CHECK(dismissed.origin == SnapshotOrigin::PetSpell);
    CHECK(dismissed.chains.at(17253) == false);
    CHECK(!dismissed.deleteStoredCache);

    StoredCacheRow kept = stale;
    kept.on = false;
    kept.seenSavetime = 80;
    LoadDecision const relog = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { kept }, DatabaseRead::Ok, { Spell(17253, 17253, true) }, owner, false, lists.utility);
    CHECK(relog.origin == SnapshotOrigin::ModuleCache);
    CHECK(relog.chains.at(17253) == false);
    CHECK(relog.chains.find(2649) == relog.chains.end());
    std::vector<SourceSpell> const relogBook = { Spell(17253, 27050, true), Spell(2649, 2649, false), Spell(61684, 61684, false) };
    std::vector<ApplyAction> const relogActions = PlanApply(relog.chains, relogBook, lists, relog.allowDefaultOn);
    CHECK(relogActions.size() == 1u);
    CHECK(relogActions[0].chainFirst == 17253u);
    CHECK(!relogActions[0].desiredOn);
    for (ApplyAction const& action : relogActions)
        CHECK(!ContainsId(lists.utility, action.chainFirst));
}

void CheckSameEntryRecycleFailsClosedWhereItCan()
{
    CHECK(SameEntryRecycleAfterSavetimeRebindIsIndistinguishable());
    ChainLists const lists = Defaults();
    OwnerProof owner;
    owner.lookup = OwnerLookup::Unique;
    owner.liveBound = true;
    owner.creatureEntry = 42719;
    owner.createdBySpell = 1515;
    owner.savetime = 90;
    StoredCacheRow row;
    row.chainFirst = 17253;
    row.on = true;
    row.creatureEntry = 42719;
    row.createdBySpell = 1515;
    row.seenSavetime = 90;
    std::vector<SourceSpell> const petSpell = { Spell(17253, 17253, false) };

    StoredCacheRow otherEntry = row;
    otherEntry.creatureEntry = 100;
    LoadDecision const entryMiss = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { otherEntry }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(entryMiss.deleteStoredCache);
    CHECK(entryMiss.origin == SnapshotOrigin::PetSpell);
    CHECK(entryMiss.chains.at(17253) == false);

    StoredCacheRow otherSpell = row;
    otherSpell.createdBySpell = 9;
    LoadDecision const spellMiss = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { otherSpell }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(spellMiss.deleteStoredCache);
    CHECK(spellMiss.origin != SnapshotOrigin::ModuleCache);

    StoredCacheRow otherTime = row;
    otherTime.seenSavetime = 10;
    LoadDecision const timeMiss = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { otherTime }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(!timeMiss.deleteStoredCache);
    CHECK(timeMiss.origin == SnapshotOrigin::PetSpell);
    CHECK(timeMiss.chains.at(17253) == false);

    LoadDecision const collision = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { row }, DatabaseRead::Ok, petSpell, owner, false, lists.utility);
    CHECK(collision.origin == SnapshotOrigin::ModuleCache);
    CHECK(collision.chains.at(17253));
    CHECK(!collision.deleteStoredCache);
    CHECK(SameEntryRecycleAfterSavetimeRebindIsIndistinguishable());
    CHECK(!FunctionalOnOffPersistenceIsComplete());
}

void CheckLiveEntryBind()
{
    ChainLists const lists = Defaults();
    LivePetIdentity live;
    live.creatureEntry = 200;
    live.createdBySpell = 1515;
    live.createdBySpellAvailable = true;

    OwnerProof const failed = InterpretOwnerAggregate(false, 0, 0, 0, 0, 0, live);
    CHECK(failed.lookup == OwnerLookup::Unproven);
    CHECK(!failed.liveBound);

    OwnerProof const absent = InterpretOwnerAggregate(true, 0, 0, 0, 0, 0, live);
    CHECK(absent.lookup == OwnerLookup::Absent);
    CHECK(!absent.liveBound);

    OwnerProof const many = InterpretOwnerAggregate(true, 2, 1, 1515, 50, 200, live);
    CHECK(many.lookup == OwnerLookup::Ambiguous);
    CHECK(!many.liveBound);

    OwnerProof const mismatch = InterpretOwnerAggregate(true, 1, 0, 0, 0, 100, live);
    CHECK(mismatch.lookup == OwnerLookup::Mismatch);
    CHECK(mismatch.creatureEntry == 100u);
    CHECK(!mismatch.liveBound);

    LivePetIdentity otherSpell = live;
    otherSpell.createdBySpell = 999;
    OwnerProof const spellMiss = InterpretOwnerAggregate(true, 1, 1, 1515, 50, 200, otherSpell);
    CHECK(spellMiss.lookup == OwnerLookup::Mismatch);
    CHECK(!spellMiss.liveBound);

    LivePetIdentity noSpell = live;
    noSpell.createdBySpell = 0;
    noSpell.createdBySpellAvailable = false;
    OwnerProof const unboundSpell = InterpretOwnerAggregate(true, 1, 1, 1515, 50, 200, noSpell);
    CHECK(unboundSpell.lookup == OwnerLookup::Mismatch);
    CHECK(!unboundSpell.liveBound);

    LivePetIdentity noEntry;
    OwnerProof const noLive = InterpretOwnerAggregate(true, 1, 1, 1515, 50, 200, noEntry);
    CHECK(noLive.lookup == OwnerLookup::Unproven);

    OwnerProof const unique = InterpretOwnerAggregate(true, 1, 1, 1515, 50, 200, live);
    CHECK(unique.lookup == OwnerLookup::Unique);
    CHECK(unique.liveBound);
    CHECK(unique.creatureEntry == 200u);
    CHECK(unique.createdBySpell == 1515u);
    CHECK(unique.savetime == 50u);

    StoredCacheRow cached;
    cached.chainFirst = 17253;
    cached.on = true;
    cached.creatureEntry = 100;
    cached.createdBySpell = 1515;
    cached.seenSavetime = 50;
    std::vector<SourceSpell> const petSpell = { Spell(17253, 17253, true), Spell(16827, 16827, true) };
    LoadDecision const refused = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, mismatch, false, lists.utility);
    CHECK(refused.origin == SnapshotOrigin::Unavailable);
    CHECK(refused.chains.empty());
    CHECK(!refused.allowDefaultOn);
    CHECK(!refused.writeAllowed);
    CHECK(!refused.deleteStoredCache);
    CHECK(PlanApply(refused.chains, petSpell, lists, refused.allowDefaultOn).empty());

    OwnerProof unbound = unique;
    unbound.liveBound = false;
    LoadDecision const notBound = DecideLoad(
        SchemaProbe::Present, DatabaseRead::Ok, { cached }, DatabaseRead::Ok, petSpell, unbound, false, lists.utility);
    CHECK(notBound.origin == SnapshotOrigin::Unavailable);
    CHECK(!notBound.allowDefaultOn);
    CHECK(!notBound.writeAllowed);
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
    CheckUtilityPreferenceFlag();
    CheckReconcileLeavesOtherSpells();
    CheckCoverClickDismissAndRelog();
    CheckSameEntryRecycleFailsClosedWhereItCan();
    CheckLiveEntryBind();

    if (g_failures != 0)
    {
        std::fprintf(stderr, "A02_S4_POLICY_FAIL checks=%d failures=%d\n", g_checks, g_failures);
        return 1;
    }
    std::printf("A02_S4_POLICY_OK checks=%d\n", g_checks);
    return 0;
}
