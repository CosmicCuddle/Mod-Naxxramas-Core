/* Deterministic policy tests for the default-off experimental restore.
 * No worldserver, SQL, or DBC. A pass is not an in-game summon, relog,
 * or rank change. PR #63's five unsafe behaviours are asserted here as
 * the corrected fail-closed results.
 */

#include "HunterPetAutocastRestore.h"

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

using namespace NaxxramasCore::HunterPetAutocastRestore;

void CheckProvenance()
{
    CHECK(std::strcmp(PinnedCoreOldSha, "a66f1bede6f5d905d9ab815715b4e2ee1c1f48e7") == 0);
    CHECK(std::strcmp(PinnedCoreNewSha, "8daffdabe9202c228e45d833c9a1d399597a15cd") == 0);
    CHECK(std::strcmp(PinnedIndividualProgressionSha, "4ff4b5fcc1480348f058c632573143e62d4e3a41") == 0);
    CHECK(std::strcmp(PinnedPlayerbotsSha, "037c01418b5d01506917a3db9b44fd56ac5f965c") == 0);
    CHECK(std::strcmp(EnabledConfigKey, "NaxxramasCore.HunterPetAutocastRestore.Enabled") == 0);
    CHECK(std::strcmp(DefaultEnabledRaw, "0") == 0);
    CHECK(EnabledFromRaw("0") == false);
    CHECK(EnabledFromRaw(" 0 ") == false);
    CHECK(EnabledFromRaw("1") == true);
    CHECK(EnabledFromRaw(" 1 ") == true);
    CHECK(EnabledFromRaw("true") == false);
    CHECK(EnabledFromRaw("2") == false);
    CHECK(EnabledFromRaw("") == false);
    CHECK(EnabledFromRaw(nullptr) == false);
    CHECK(EnabledFromRaw(DefaultEnabledRaw) == false);
    CHECK(!FrozenLoadPumpsReconcile());
    CHECK(!UnvalidatedPacketDrivesToggle());
    CHECK(EventGenerationMatches(2u, 2u));
    CHECK(!EventGenerationMatches(1u, 2u));
    CHECK(!EventGenerationMatches(0u, 0u));
}

/* Case 1. Unknown lookup, empty pattern, and invalid pattern are ineligible.
 * They are not classified as "not a bot", and they are not eligible humans.
 */
void CheckAccountEligibility()
{
    CHECK(ClassifyAccount(true, "RNDBOT1", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedBot);
    CHECK(ClassifyAccount(true, "RNDBOT", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedBot);
    CHECK(ClassifyAccount(true, "Human", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedHuman);
    CHECK(ClassifyAccount(true, "rndbot1", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedHuman);
    CHECK(ClassifyAccount(true, "xRNDBOT", DefaultBotAccountsRegex) == AccountVerdict::ConfirmedHuman);
    CHECK(ClassifyAccount(true, "ALTBOT", "^ALT.*") == AccountVerdict::ConfirmedBot);
    CHECK(ClassifyAccount(true, "Human", "^ALT.*") == AccountVerdict::ConfirmedHuman);
    CHECK(ClassifyAccount(true, "RNDBOT1", "^ALT.*") == AccountVerdict::ConfirmedHuman);

    CHECK(ClassifyAccount(false, "RNDBOT1", "^RNDBOT.*") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, "", "^RNDBOT.*") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, "RNDBOT1", "") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, "RNDBOT1", "(") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, nullptr, "^RNDBOT.*") == AccountVerdict::Ineligible);
    CHECK(ClassifyAccount(true, "RNDBOT1", nullptr) == AccountVerdict::Ineligible);
    CHECK(!IsEligibleHumanAccount(AccountVerdict::Ineligible));
    CHECK(!IsEligibleHumanAccount(AccountVerdict::ConfirmedBot));
    CHECK(IsEligibleHumanAccount(AccountVerdict::ConfirmedHuman));
}

LivePetId Pet(uint64_t guid, uint32_t number)
{
    LivePetId id;
    id.ownerGuid = 7;
    id.petGuid = guid;
    id.petNumber = number;
    return id;
}

RestoreDecision Restore(
    LivePetId const& bound,
    LivePetId const& current,
    bool snapshotCommitted,
    std::map<uint32_t, Preference> const& snapshot,
    std::vector<BookSpell> const& book,
    bool inWorld = true,
    bool beingRemoved = false,
    bool loggingOut = false,
    bool loaded = true)
{
    return DecideRestore(bound, current, inWorld, beingRemoved, loggingOut, loaded, snapshotCommitted, snapshot, book);
}

Preference Pref(uint32_t id, bool on)
{
    Preference preference;
    preference.spellId = id;
    preference.autocastOn = on;
    preference.present = true;
    preference.sequence = 1;
    return preference;
}

/* Case 2. An unverified packet ON is not a snapshot and does not plan a restore.
 * Case 3. Explicit OFF against a replacement rank that is ON aborts.
 * It is not an empty skip. Honouring OFF writes nothing.
 */
void CheckPacketAndOff()
{
    LivePetId const id = Pet(100, 45);
    std::vector<BookSpell> swappedOff{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
    };
    std::vector<BookSpell> swappedOn{
        MakeSpell(17253u, 17253u, false, true),
        MakeSpell(17255u, 17253u, true),
    };

    RestoreDecision const rejected = RejectUnvalidatedPacket();
    CHECK(rejected.outcome == RestoreOutcome::Abort);
    CHECK(rejected.reason == CycleAbort::UnvalidatedPacketIgnored);
    CHECK(!rejected.touchesPet);
    CHECK(!rejected.writesOff);
    CHECK(rejected.plans.empty());

    RestoreDecision const packetOnly = Restore(id, id, false, {}, swappedOff);
    CHECK(packetOnly.outcome == RestoreOutcome::Abort);
    CHECK(packetOnly.reason == CycleAbort::NoSnapshot);
    CHECK(packetOnly.plans.empty());
    CHECK(!packetOnly.touchesPet);
    CHECK(!packetOnly.writesOff);

    std::map<uint32_t, Preference> explicitOff{ { 17253u, Pref(17253u, false) } };
    RestoreDecision const offConflict = Restore(id, id, true, explicitOff, swappedOn);
    CHECK(offConflict.outcome == RestoreOutcome::Abort);
    CHECK(offConflict.reason == CycleAbort::ExplicitOffConflict);
    CHECK(offConflict.plans.empty());
    CHECK(!offConflict.touchesPet);
    CHECK(!offConflict.writesOff);

    std::vector<BookSpell> swappedOffMatching{
        MakeSpell(17253u, 17253u, false, true),
        MakeSpell(17255u, 17253u, false),
    };
    RestoreDecision const honoured = Restore(id, id, true, explicitOff, swappedOffMatching);
    CHECK(honoured.outcome == RestoreOutcome::HonourOff);
    CHECK(!honoured.touchesPet);
    CHECK(!honoured.writesOff);
    CHECK(honoured.plans.empty());

    std::map<uint32_t, Preference> explicitOn{ { 17253u, Pref(17253u, true) } };
    RestoreDecision const turnedOn = Restore(id, id, true, explicitOn, swappedOff);
    CHECK(turnedOn.outcome == RestoreOutcome::ApplyOn);
    CHECK(turnedOn.touchesPet);
    CHECK(!turnedOn.writesOff);
    CHECK(turnedOn.plans.size() == 1u);
    CHECK(turnedOn.plans[0].oldSpellId == 17253u);
    CHECK(turnedOn.plans[0].newSpellId == 17255u);
    CHECK(turnedOn.plans[0].applyOn);
    CHECK(turnedOn.plans[0].desiredOn);

    std::vector<BookSpell> twoRemoved{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17254u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
    };
    CHECK(Restore(id, id, true, explicitOn, twoRemoved).reason == CycleAbort::AmbiguousBook);
    CHECK(!Restore(id, id, true, explicitOn, twoRemoved).touchesPet);

    std::vector<BookSpell> removedStillThere{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
    };
    CHECK(Restore(id, id, false, {}, removedStillThere).reason == CycleAbort::NoSnapshot);
    CHECK(!Restore(id, id, false, {}, removedStillThere).touchesPet);

    std::vector<BookSpell> savedOff{ MakeSpell(17255u, 17253u, false) };
    CHECK(Restore(id, id, true, explicitOn, savedOff).outcome == RestoreOutcome::ApplyOn);
    CHECK(Restore(id, id, false, {}, savedOff).reason == CycleAbort::NoSnapshot);

    std::map<uint32_t, Preference> biteOn{ { 17253u, Pref(17253u, true) } };
    std::map<uint32_t, Preference> both = biteOn;
    both.emplace(2649u, Pref(2649u, true));
    std::vector<BookSpell> extraChain{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
        MakeSpell(2649u, 2649u, true),
        MakeSpell(14916u, 2649u, false),
    };
    /* Growl was not in the snapshot that only has bite: unknown chain aborts. */
    CHECK(Restore(id, id, true, biteOn, extraChain).reason == CycleAbort::AmbiguousBook);
    CHECK(!Restore(id, id, true, biteOn, extraChain).touchesPet);

    std::vector<BookSpell> growlUnchanged{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
        MakeSpell(2649u, 2649u, true),
    };
    RestoreDecision const partial = Restore(id, id, true, both, growlUnchanged);
    CHECK(partial.outcome == RestoreOutcome::ApplyOn);
    CHECK(partial.plans.size() == 1u);
    CHECK(partial.plans[0].chainFirst == 17253u);

    std::map<uint32_t, Preference> biteOffGrowlOn = both;
    biteOffGrowlOn[17253u].autocastOn = false;
    std::vector<BookSpell> biteForcedOn{
        MakeSpell(17253u, 17253u, false, true),
        MakeSpell(17255u, 17253u, true),
        MakeSpell(2649u, 2649u, true),
    };
    RestoreDecision const mixed = Restore(id, id, true, biteOffGrowlOn, biteForcedOn);
    CHECK(mixed.outcome == RestoreOutcome::Abort);
    CHECK(mixed.reason == CycleAbort::ExplicitOffConflict);
    CHECK(mixed.plans.empty());
    CHECK(!mixed.touchesPet);

    std::vector<BookSpell> removedDisagrees{
        MakeSpell(17253u, 17253u, false, true),
        MakeSpell(17255u, 17253u, false),
    };
    CHECK(Restore(id, id, true, explicitOn, removedDisagrees).reason == CycleAbort::InterveningChange);
    CHECK(!Restore(id, id, true, explicitOn, removedDisagrees).touchesPet);

    std::vector<BookSpell> unknownChain{ MakeSpell(1u, 0u, true) };
    CHECK(Restore(id, id, true, explicitOn, unknownChain).reason == CycleAbort::AmbiguousBook);
}

/* Case 4. The same saved pet number with a different live GUID aborts.
 * Logout, removal, and a duplicate schedule that would reset memory abort
 * or leave the snapshot in place.
 */
void CheckIdentity()
{
    LivePetId const first = Pet(100, 45);
    LivePetId const resummon = Pet(200, 45);
    LivePetId const other = Pet(300, 46);
    CHECK(CheckLiveIdentity(first, first, true, false, false) == CycleAbort::None);
    CHECK(CheckLiveIdentity(first, resummon, true, false, false) == CycleAbort::GuidMismatch);
    CHECK(CheckLiveIdentity(first, other, true, false, false) == CycleAbort::GuidMismatch);
    CHECK(CheckLiveIdentity(first, first, false, false, false) == CycleAbort::NotInWorld);
    CHECK(CheckLiveIdentity(first, first, true, true, false) == CycleAbort::BeingRemoved);
    CHECK(CheckLiveIdentity(first, first, true, false, true) == CycleAbort::OwnerLoggingOut);
    CHECK(CheckLiveIdentity(first, LivePetId{}, true, false, false) == CycleAbort::MissingPet);

    std::map<uint32_t, Preference> snapshot{ { 17253u, Pref(17253u, true) } };
    std::vector<BookSpell> book{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
    };
    RestoreDecision const stale = Restore(first, resummon, true, snapshot, book);
    CHECK(stale.outcome == RestoreOutcome::Abort);
    CHECK(stale.reason == CycleAbort::StaleSnapshot);
    CHECK(!stale.touchesPet);
    CHECK(stale.plans.empty());

    MemoryView memory;
    CHECK(ScheduleCycle(memory, first) == ScheduleResult::Started);
    std::vector<BookSpell> clean{ MakeSpell(17253u, 17253u, true) };
    SnapshotCommit const commit = TryCommitSnapshot(first, first, true, false, false, true, false, clean, 1u);
    CHECK(commit.committed);
    memory.snapshot = commit.chains;
    memory.snapshotCommitted = true;
    uint32_t const generation = memory.generation;
    CHECK(ScheduleCycle(memory, first) == ScheduleResult::IgnoredDuplicate);
    CHECK(memory.snapshotCommitted);
    CHECK(memory.generation == generation);
    CHECK(memory.snapshot[17253u].spellId == 17253u);
    CHECK(memory.snapshot[17253u].autocastOn);
    CHECK(ScheduleCycle(memory, LivePetId{}) == ScheduleResult::Refused);
    CHECK(memory.snapshotCommitted);

    memory.refused = true;
    CHECK(ScheduleCycle(memory, first) == ScheduleResult::Refused);
    CHECK(memory.snapshot[17253u].autocastOn);

    CHECK(TryCommitSnapshot(first, first, true, false, false, false, false, clean, 1u).reason == CycleAbort::StillLoading);
    CHECK(!TryCommitSnapshot(first, first, true, false, false, false, false, clean, 1u).committed);
    std::vector<BookSpell> alreadySwapped{
        MakeSpell(17253u, 17253u, true, true),
        MakeSpell(17255u, 17253u, false),
    };
    CHECK(TryCommitSnapshot(first, first, true, false, false, true, false, alreadySwapped, 1u).reason == CycleAbort::IpAlreadyRan);
    CHECK(!TryCommitSnapshot(first, first, true, false, false, true, true, clean, 1u).committed);
}

void CheckNoTouch(SimResult const& result)
{
    CHECK(result.toggles == 0u);
    CHECK(!result.wroteOff);
    CHECK(result.touchedGuid == 0u);
    CHECK(result.outcome != RestoreOutcome::ApplyOn);
}

void CheckOn(SimResult const& result, uint64_t guid)
{
    CHECK(result.outcome == RestoreOutcome::ApplyOn);
    CHECK(result.toggles == 1u);
    CHECK(!result.wroteOff);
    CHECK(result.touchedGuid == guid);
    CHECK(result.snapshotCommitted);
    CHECK(result.snapshotGuid == guid);
}

/* Case 5 and the adversarial orders. The step list is the event order.
 * Same-flush means that list, not a 50/200/350 timestamp.
 */
void CheckOrdering()
{
    SimInput on;
    on.explicitOn = true;
    SimInput off;
    off.explicitOn = false;

    std::vector<SimStep> const ipFirst{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::IpCheck,
        SimStep::ModulePoll,
        SimStep::ModuleRestore,
    };
    std::vector<SimStep> const moduleFirst{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::ModuleRestore,
    };
    CheckNoTouch(RunSequence(ipFirst, on));
    CheckNoTouch(RunSequence(ipFirst, off));
    CheckOn(RunSequence(moduleFirst, on), on.petGuid);

    SimResult const honoured = RunSequence(moduleFirst, off);
    CHECK(honoured.outcome == RestoreOutcome::HonourOff);
    CHECK(honoured.toggles == 0u);
    CHECK(!honoured.wroteOff);
    CHECK(honoured.touchedGuid == 0u);

    std::vector<SimStep> const restoreBeforeIp{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::ModuleRestore,
        SimStep::IpCheck,
        SimStep::ModuleRestore,
    };
    CheckOn(RunSequence(restoreBeforeIp, on), on.petGuid);

    std::vector<SimStep> const pollWhileLoading{
        SimStep::BindHook,
        SimStep::ModulePoll,
    };
    SimResult const deferred = RunSequence(pollWhileLoading, on);
    CHECK(!deferred.snapshotCommitted);
    CHECK(deferred.toggles == 0u);
    CHECK(deferred.reason == CycleAbort::StillLoading);

    SimInput loadedDuringLongLoad = on;
    loadedDuringLongLoad.spellsLoadedAtStart = true;
    loadedDuringLongLoad.startLoading = true;
    std::vector<SimStep> const exhaustThenLateSnapshot{
        SimStep::BindHook,
        SimStep::IpExhaustWhileLoading,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::ModuleRestore,
    };
    CheckNoTouch(RunSequence(exhaustThenLateSnapshot, loadedDuringLongLoad));

    SimInput spellsArriveAfterCap = on;
    spellsArriveAfterCap.spellsLoadedAtStart = false;
    CheckNoTouch(RunSequence(exhaustThenLateSnapshot, spellsArriveAfterCap));

    std::vector<SimStep> const frozenThenModuleFirst{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::ModuleRestore,
    };
    std::vector<SimStep> const frozenThenIpFirst{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::IpCheck,
        SimStep::ModulePoll,
        SimStep::ModuleRestore,
    };
    CheckOn(RunSequence(frozenThenModuleFirst, on), on.petGuid);
    CheckNoTouch(RunSequence(frozenThenIpFirst, on));

    std::vector<SimStep> const saveAfterSnapshot{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::PetSave,
        SimStep::ModuleRestore,
    };
    CheckOn(RunSequence(saveAfterSnapshot, on), on.petGuid);
    SimResult const offAfterSave = RunSequence(saveAfterSnapshot, off);
    CHECK(offAfterSave.outcome == RestoreOutcome::HonourOff);
    CHECK(offAfterSave.toggles == 0u);
    CHECK(!offAfterSave.wroteOff);

    SimResult const lostOn = CounterexampleDelayedLoadThenSave(true);
    SimResult const lostOff = CounterexampleDelayedLoadThenSave(false);
    CheckNoTouch(lostOn);
    CheckNoTouch(lostOff);
    CHECK(lostOn.reason == CycleAbort::NoSnapshot);
    CHECK(lostOff.reason == CycleAbort::NoSnapshot);
    CHECK(!lostOn.snapshotCommitted);
    CHECK(!lostOff.snapshotCommitted);

    std::vector<SimStep> const offForcedOn{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::OtherModuleTurnsOn,
        SimStep::ModuleRestore,
    };
    SimResult const conflict = RunSequence(offForcedOn, off);
    CHECK(conflict.outcome == RestoreOutcome::Abort);
    CHECK(conflict.reason == CycleAbort::ExplicitOffConflict);
    CHECK(conflict.toggles == 0u);
    CHECK(!conflict.wroteOff);

    std::vector<SimStep> const relog{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::RelogNewGuid,
        SimStep::ModuleRestore,
    };
    CheckNoTouch(RunSequence(relog, on));

    std::vector<SimStep> const swap{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::SwapPet,
        SimStep::ModuleRestore,
    };
    SimResult const wrongPet = RunSequence(swap, on);
    CheckNoTouch(wrongPet);
    CHECK(wrongPet.reason == CycleAbort::StaleSnapshot);

    std::vector<SimStep> const resummon{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::ResummonSameNumber,
        SimStep::ModuleRestore,
    };
    SimResult const sameNumber = RunSequence(resummon, on);
    CheckNoTouch(sameNumber);
    CHECK(sameNumber.reason == CycleAbort::StaleSnapshot);

    std::vector<SimStep> const nested{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::ModuleRestore,
        SimStep::ModuleRestore,
    };
    SimResult const once = RunSequence(nested, on);
    CHECK(once.toggles == 1u);
    CHECK(once.touchedGuid == on.petGuid);
    CHECK(!once.wroteOff);
    CHECK(once.reason == CycleAbort::NestedSchedule);

    std::vector<SimStep> const duplicate{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::DuplicateHook,
        SimStep::IpCheck,
        SimStep::ModuleRestore,
    };
    SimResult const kept = RunSequence(duplicate, on);
    CheckOn(kept, on.petGuid);
    CHECK(kept.duplicateIgnored);
    CHECK(kept.generation == 1u);

    std::vector<SimStep> const logout{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::Logout,
        SimStep::ModuleRestore,
    };
    SimResult const loggingOut = RunSequence(logout, on);
    CheckNoTouch(loggingOut);
    CHECK(loggingOut.reason == CycleAbort::OwnerLoggingOut);

    std::vector<SimStep> const removedFromWorld{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::IpCheck,
        SimStep::MarkBeingRemoved,
        SimStep::ModuleRestore,
    };
    CHECK(RunSequence(removedFromWorld, on).reason == CycleAbort::BeingRemoved);
    CheckNoTouch(RunSequence(removedFromWorld, on));

    std::vector<SimStep> const notInWorld{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::MarkNotInWorld,
        SimStep::ModuleRestore,
    };
    CHECK(RunSequence(notInWorld, on).reason == CycleAbort::NotInWorld);
    CheckNoTouch(RunSequence(notInWorld, on));

    std::vector<SimStep> const packetWithoutSnapshot{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::UnvalidatedPacket,
        SimStep::IpCheck,
        SimStep::PetSave,
        SimStep::ModuleRestore,
    };
    CheckNoTouch(RunSequence(packetWithoutSnapshot, on));

    std::vector<SimStep> const packetDoesNotSteer{
        SimStep::BindHook,
        SimStep::LoadCompletes,
        SimStep::ModulePoll,
        SimStep::UnvalidatedPacket,
        SimStep::IpCheck,
        SimStep::ModuleRestore,
    };
    CheckOn(RunSequence(packetDoesNotSteer, on), on.petGuid);
    SimResult const packetOff = RunSequence(packetDoesNotSteer, off);
    CHECK(packetOff.outcome == RestoreOutcome::HonourOff);
    CHECK(packetOff.toggles == 0u);
    CHECK(!packetOff.wroteOff);
}

} // namespace

int main()
{
    CheckProvenance();
    CheckAccountEligibility();
    CheckPacketAndOff();
    CheckIdentity();
    CheckOrdering();
    if (g_failures != 0)
    {
        std::fprintf(stderr, "A02_S2_POLICY_FAIL %d\n", g_failures);
        return 1;
    }
    std::printf("A02_S2_POLICY_OK checks=%d\n", g_checks);
    return 0;
}
