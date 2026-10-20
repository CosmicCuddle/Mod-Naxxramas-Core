/* Deterministic policy tests for HunterPetAutocastRestore.h.
 * No worldserver, SQL, or DBC. A pass is not an in-game summon,
 * relog, or rank-change acceptance.
 */

#include "HunterPetAutocastRestore.h"

#include <cstdio>
#include <cstring>
#include <string>

namespace
{
int g_failures = 0;

#define CHECK(cond)                                                                 \
    do                                                                              \
    {                                                                               \
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
    CHECK(std::strcmp(DefaultBotAccountsRegex, "^RNDBOT.*") == 0);
    CHECK(IpEventDelayMs == 200u);
    CHECK(IpLoadingAttemptCap == 10u);
    CHECK(SnapshotPollMs == 50u);
    CHECK(RestoreLagMs == 150u);
    CHECK(FirstPollDelayMs() == 50u);
    CHECK(IpOpportunityMs(0) == 200u);
    CHECK(IpOpportunityMs(IpLoadingAttemptCap) == 2200u);
    CHECK(EnabledFromRaw("0") == false);
    CHECK(EnabledFromRaw(" 0 ") == false);
    CHECK(EnabledFromRaw("1") == true);
    CHECK(EnabledFromRaw(" 1 ") == true);
    CHECK(EnabledFromRaw("true") == false);
    CHECK(EnabledFromRaw("2") == false);
    CHECK(EnabledFromRaw("") == false);
    CHECK(EnabledFromRaw(nullptr) == false);
    CHECK(EnabledFromRaw(DefaultEnabledRaw) == false);
}

void CheckBots()
{
    CHECK(AccountIsBot(true, "RNDBOT1", DefaultBotAccountsRegex));
    CHECK(AccountIsBot(true, "RNDBOT", DefaultBotAccountsRegex));
    CHECK(!AccountIsBot(true, "Human", DefaultBotAccountsRegex));
    CHECK(!AccountIsBot(true, "rndbot1", DefaultBotAccountsRegex));
    CHECK(!AccountIsBot(true, "xRNDBOT", DefaultBotAccountsRegex));
    CHECK(AccountIsBot(true, "ALTBOT", "^ALT.*"));
    CHECK(!AccountIsBot(true, "RNDBOT1", "^ALT.*"));
    CHECK(!AccountIsBot(true, "Human", "^ALT.*"));
    CHECK(!AccountIsBot(false, "RNDBOT1", "^RNDBOT.*"));
    CHECK(!AccountIsBot(true, "", "^RNDBOT.*"));
    CHECK(!AccountIsBot(true, "RNDBOT1", ""));
    CHECK(!AccountIsBot(true, "RNDBOT1", "("));
    CHECK(!AccountIsBot(true, nullptr, "^RNDBOT.*"));
    CHECK(!AccountIsBot(true, "RNDBOT1", nullptr));
}

void CheckTiming()
{
    IpExecution const frozen = IpDelayedCheckOnPump(EventPump::PetUpdateWhileLoading, true, 0);
    CHECK(!frozen.processorRan);
    CHECK(!frozen.requeued);
    CHECK(!frozen.hunterCheckRan);

    IpExecution const ordinary = IpDelayedCheckOnPump(EventPump::ProcessorAdvanced, false, 0);
    CHECK(ordinary.processorRan);
    CHECK(!ordinary.requeued);
    CHECK(ordinary.hunterCheckRan);

    IpExecution const retry = IpDelayedCheckOnPump(EventPump::ProcessorAdvanced, true, 0);
    CHECK(retry.processorRan);
    CHECK(retry.requeued);
    CHECK(!retry.hunterCheckRan);

    IpExecution const ninth = IpDelayedCheckOnPump(EventPump::ProcessorAdvanced, true, 9);
    CHECK(ninth.requeued);
    CHECK(!ninth.hunterCheckRan);

    IpExecution const capped = IpDelayedCheckOnPump(EventPump::ProcessorAdvanced, true, IpLoadingAttemptCap);
    CHECK(capped.processorRan);
    CHECK(!capped.requeued);
    CHECK(capped.hunterCheckRan);

    OrdinarySchedule const afterLoad = OrdinaryScheduleAfterLoad();
    CHECK(afterLoad.snapshotted);
    CHECK(afterLoad.snapshotOffsetMs == 50u);
    CHECK(afterLoad.ipOffsetMs == 200u);
    CHECK(afterLoad.snapshotOffsetMs < afterLoad.ipOffsetMs);
    CHECK(afterLoad.restoreOffsetMs == 350u);
    CHECK(afterLoad.restoreOffsetMs >= afterLoad.ipOffsetMs + RestoreLagMs);

    PollDecision const stillLoadingEarly = DecideSnapshotPoll(50u, false);
    CHECK(stillLoadingEarly.action == PollAction::DeferBeforeIp);
    CHECK(stillLoadingEarly.rescheduleMs == SnapshotPollMs);
    CHECK(50u + stillLoadingEarly.rescheduleMs < IpEventDelayMs);

    PollDecision const cannotLead = DecideSnapshotPoll(150u, false);
    CHECK(cannotLead.action == PollAction::UseRemovedFallback);
    CHECK(150u + cannotLead.rescheduleMs >= IpEventDelayMs + RestoreLagMs);

    PollDecision const sameInstant = DecideSnapshotPoll(200u, true);
    CHECK(sameInstant.action == PollAction::UseRemovedFallback);
    CHECK(sameInstant.rescheduleMs == RestoreLagMs);

    PollDecision const pastCap = DecideSnapshotPoll(LastIpOpportunityMs(), false);
    CHECK(pastCap.action == PollAction::GiveUp);
    CHECK(pastCap.rescheduleMs == 0u);
}

BookSpell Spell(uint32_t id, uint32_t chain, bool on, bool removed = false)
{
    BookSpell spell;
    spell.id = id;
    spell.chainFirst = chain;
    spell.autocastable = true;
    spell.removed = removed;
    spell.autocastOn = on;
    return spell;
}

void CheckRestore()
{
    std::vector<BookSpell> before{
        Spell(17253u, 17253u, true),
        Spell(16827u, 16827u, false),
        Spell(2649u, 2649u, true),
    };
    before.push_back(Spell(20782u, 20782u, false));
    before.back().autocastable = false;

    std::map<uint32_t, Preference> snapshot = SnapshotChains(before, 1u);
    CHECK(snapshot.size() == 3u);
    CHECK(snapshot[17253u].autocastOn);
    CHECK(!snapshot[16827u].autocastOn);
    CHECK(snapshot[2649u].spellId == 2649u);
    CHECK(snapshot.count(20782u) == 0u);

    std::vector<BookSpell> ambiguous{ Spell(1u, 10u, true), Spell(2u, 10u, false) };
    CHECK(SnapshotChains(ambiguous, 1u).empty());

    std::vector<BookSpell> after{
        Spell(17253u, 17253u, true, true),
        Spell(17255u, 17253u, false),
        Spell(16827u, 16827u, false),
        Spell(2649u, 2649u, true),
    };
    std::map<uint32_t, Preference> noPacket;
    std::vector<ChainRestore> plans = PlanRestores(after, snapshot, noPacket, false);
    CHECK(plans.size() == 1u);
    CHECK(plans[0].chainFirst == 17253u);
    CHECK(plans[0].oldSpellId == 17253u);
    CHECK(plans[0].newSpellId == 17255u);
    CHECK(plans[0].desiredOn);
    CHECK(plans[0].apply);

    snapshot[17253u].autocastOn = false;
    plans = PlanRestores(after, snapshot, noPacket, false);
    CHECK(plans.empty());

    snapshot[17253u].autocastOn = true;
    snapshot[17253u].spellId = 17255u;
    plans = PlanRestores(after, snapshot, noPacket, false);
    CHECK(plans.empty());

    snapshot = SnapshotChains(before, 4u);
    Preference packet;
    packet.spellId = 17253u;
    packet.autocastOn = false;
    packet.present = true;
    packet.sequence = 9u;
    std::map<uint32_t, Preference> packets{ { 17253u, packet } };
    plans = PlanRestores(after, snapshot, packets, false);
    CHECK(plans.empty());

    packet.sequence = 1u;
    packets[17253u] = packet;
    plans = PlanRestores(after, snapshot, packets, false);
    CHECK(plans.size() == 1u);
    CHECK(plans[0].desiredOn);

    packet.spellId = 17255u;
    packet.sequence = 9u;
    packet.autocastOn = true;
    packets[17253u] = packet;
    plans = PlanRestores(after, snapshot, packets, false);
    CHECK(plans.empty());

    std::map<uint32_t, Preference> remembered = snapshot;
    plans = PlanRestores(after, remembered, noPacket, false);
    CHECK(plans.size() == 1u);
    NoteRestored(remembered, packets, plans[0], 20u);
    CHECK(PlanRestores(after, remembered, packets, false).empty());

    std::vector<BookSpell> removedOnly{
        Spell(17253u, 17253u, true, true),
        Spell(17255u, 17253u, false),
    };
    plans = PlanRestores(removedOnly, {}, {}, true);
    CHECK(plans.size() == 1u);
    CHECK(plans[0].oldSpellId == 17253u);
    CHECK(plans[0].newSpellId == 17255u);
    CHECK(plans[0].desiredOn);

    plans = PlanRestores(removedOnly, {}, {}, false);
    CHECK(plans.empty());

    std::vector<BookSpell> removedOff{
        Spell(17253u, 17253u, false, true),
        Spell(17255u, 17253u, false),
    };
    CHECK(PlanRestores(removedOff, {}, {}, true).empty());

    std::vector<BookSpell> twoRemoved{
        Spell(17253u, 17253u, true, true),
        Spell(17254u, 17253u, false, true),
        Spell(17255u, 17253u, false),
    };
    CHECK(PlanRestores(twoRemoved, {}, {}, true).empty());

    std::vector<BookSpell> otherChain{
        Spell(17253u, 17253u, true, true),
        Spell(99u, 99u, false),
    };
    CHECK(PlanRestores(otherChain, {}, {}, true).empty());

    CHECK(PetNumberMatches(15u, 15u));
    CHECK(!PetNumberMatches(0u, 0u));
    CHECK(!PetNumberMatches(0u, 15u));
    CHECK(!PetNumberMatches(15u, 16u));
}

} // namespace

int main()
{
    CheckProvenance();
    CheckBots();
    CheckTiming();
    CheckRestore();
    if (g_failures != 0)
    {
        std::fprintf(stderr, "A02_S2_POLICY_FAIL %d\n", g_failures);
        return 1;
    }
    std::printf("A02_S2_POLICY_OK\n");
    return 0;
}
