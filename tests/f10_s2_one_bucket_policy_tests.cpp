/* Policy and stock-splash model for the F10 one-bucket decision.
 * Compiles HallowsEndSoloFire.h only. No worldserver, SQL, or DBC.
 * A pass is not gameplay acceptance. 42348 missile speed is not known here.
 */

#include "HallowsEndSoloFire.h"

#include <cstdio>
#include <cstdlib>
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

using namespace NaxxramasCore::HallowsEndSoloFire;

char const* ReasonName(OneBucketReason reason)
{
    switch (reason)
    {
        case OneBucketReason::RemoveFireAura:
            return "RemoveFireAura";
        case OneBucketReason::MissOrCancel:
            return "MissOrCancel";
        case OneBucketReason::WrongSpell:
            return "WrongSpell";
        case OneBucketReason::WrongEffect:
            return "WrongEffect";
        case OneBucketReason::WrongTarget:
            return "WrongTarget";
        case OneBucketReason::OneBucketOff:
            return "OneBucketOff";
        case OneBucketReason::SoloEnabledOff:
            return "SoloEnabledOff";
        case OneBucketReason::NotPlayer:
            return "NotPlayer";
        case OneBucketReason::BotCaster:
            return "BotCaster";
        case OneBucketReason::FireAuraAbsent:
            return "FireAuraAbsent";
        case OneBucketReason::ShadeCount:
            return "ShadeCount";
        case OneBucketReason::Census:
            return "Census";
    }
    return "Unknown";
}

OneBucketFacts Armed()
{
    OneBucketFacts facts;
    facts.hitAccepted = true;
    facts.spellId = BucketLandSpellId;
    facts.effectIndex = BucketLandEffectIndex;
    facts.targetEntry = FireTriggerEntry;
    facts.targetHasFireAura = true;
    facts.oneBucket = 1;
    facts.soloEnabled = 1;
    facts.casterIsPlayer = true;
    facts.casterIsBot = false;
    facts.casterInCensus = true;
    facts.realPlayersInCensus = 1;
    facts.activeBurningShadeCount = 1;
    return facts;
}

struct AuraModel
{
    bool fire = true;
    int32_t amount = 3;
    bool unrelated = true;
};

struct SimResult
{
    bool fire = false;
    bool unrelated = false;
    int32_t amount = 0;
    bool child = false;
    int splashCasts = 0;
    int featureRemoves = 0;
    int featureCasts = 0;
    int questCredits = 0;
    int featureStrippedUnrelated = 0;
};

void StockNormalSplash(AuraModel& aura)
{
    /* hallows_end.cpp:570-582. Amount > 2 loses 2. Otherwise RemoveAllAuras. */
    if (!aura.fire)
        return;
    if (aura.amount > 2)
    {
        aura.amount -= 2;
        return;
    }
    aura.fire = false;
    aura.unrelated = false;
    aura.amount = 0;
}

void StockTrainSplash(AuraModel& aura, bool casterIsPlayer, int& credits)
{
    /* hallows_end.cpp:920-933. Player caster only. Credit is inside the aura. */
    if (!casterIsPlayer || !aura.fire)
        return;
    if (aura.amount > 1)
        aura.amount -= 1;
    else
    {
        aura.fire = false;
        aura.unrelated = false;
        aura.amount = 0;
    }
    ++credits;
}

SimResult Simulate(
    char const* timing,
    OneBucketFacts facts,
    AuraModel start,
    bool child)
{
    SimResult result;
    result.child = child;
    result.fire = start.fire;
    result.unrelated = start.unrelated;
    result.amount = start.amount;

    AuraModel aura = start;
    bool const bucketHit =
        facts.hitAccepted && facts.spellId == BucketLandSpellId;
    bool const normal = bucketHit && facts.targetEntry == FireTriggerEntry;
    bool const train = bucketHit && facts.targetEntry == TrainingFireEntry;

    auto stock = [&]()
    {
        if (!bucketHit)
            return;
        /* HandleDummy casts 42348 for a creature hit. It does not cast again
         * from this feature. Training and normal fires are both creature hits.
         */
        if (normal || train || facts.targetEntry != 0)
            ++result.splashCasts;
        if (normal)
            StockNormalSplash(aura);
        else if (train)
            StockTrainSplash(aura, facts.casterIsPlayer, result.questCredits);
    };

    auto feature = [&]()
    {
        facts.targetHasFireAura = aura.fire;
        OneBucketDecision decision = DecideOneBucket(facts);
        if (!decision.removeFireAura)
            return;
        if (aura.fire)
        {
            aura.fire = false;
            aura.amount = 0;
            ++result.featureRemoves;
        }
    };

    if (std::strcmp(timing, "immediate") == 0)
    {
        stock();
        feature();
    }
    else if (std::strcmp(timing, "delayed") == 0)
    {
        feature();
        stock();
    }
    else
    {
        std::fprintf(stderr, "unknown timing %s\n", timing);
        std::exit(2);
    }

    result.fire = aura.fire;
    result.unrelated = aura.unrelated;
    result.amount = aura.amount;
    return result;
}

void PrintSim(SimResult const& result)
{
    std::printf(
        "fire=%d unrelated=%d amount=%d child=%d splashes=%d featureRemoves=%d "
        "featureCasts=%d credit=%d featureStrippedUnrelated=%d\n",
        result.fire ? 1 : 0,
        result.unrelated ? 1 : 0,
        result.amount,
        result.child ? 1 : 0,
        result.splashCasts,
        result.featureRemoves,
        result.featureCasts,
        result.questCredits,
        result.featureStrippedUnrelated);
}

void CheckParsing()
{
    CHECK(OneBucketFromRaw("0") == 0);
    CHECK(OneBucketFromRaw("1") == 1);
    CHECK(OneBucketFromRaw(" 1 ") == 1);
    CHECK(OneBucketFromRaw("+1") == 1);
    CHECK(OneBucketFromRaw("01") == 1);
    CHECK(OneBucketFromRaw("2") == 0);
    CHECK(OneBucketFromRaw("-1") == 0);
    CHECK(OneBucketFromRaw("true") == 0);
    CHECK(OneBucketFromRaw("") == 0);
    CHECK(OneBucketFromRaw(DefaultOneBucketRaw) == 0);
    CHECK(std::strcmp(OneBucketConfigKey, "NaxxramasCore.HallowsEnd.SoloFire.OneBucket") == 0);
    CHECK(std::strcmp(DefaultOneBucketRaw, "0") == 0);
    CHECK(BucketLandSpellId == 42339u);
    CHECK(WaterSplashSpellId == 42348u);
    CHECK(FireAuraSpellId == 42074u);
    CHECK(FireTriggerEntry == 23686u);
    CHECK(TrainingFireEntry == 23537u);
    CHECK(ShadeEntry == 23543u);
    CHECK(BucketLandEffectIndex == 0u);
}

void CheckArmedRemovesOnlyByDecision()
{
    OneBucketDecision decision = DecideOneBucket(Armed());
    CHECK(decision.removeFireAura);
    CHECK(decision.reason == OneBucketReason::RemoveFireAura);
    for (int32_t amount = 1; amount <= 3; ++amount)
    {
        OneBucketFacts facts = Armed();
        OneBucketDecision again = DecideOneBucket(facts);
        CHECK(again.removeFireAura);
        CHECK(amount > 0);
    }
}

void CheckRefusal(OneBucketFacts facts, OneBucketReason reason)
{
    OneBucketDecision decision = DecideOneBucket(facts);
    CHECK(!decision.removeFireAura);
    CHECK(decision.reason == reason);
}

void CheckNegatives()
{
    OneBucketFacts facts = Armed();
    facts.hitAccepted = false;
    CheckRefusal(facts, OneBucketReason::MissOrCancel);

    facts = Armed();
    facts.spellId = WaterSplashSpellId;
    CheckRefusal(facts, OneBucketReason::WrongSpell);

    facts = Armed();
    facts.spellId = 0;
    CheckRefusal(facts, OneBucketReason::WrongSpell);

    facts = Armed();
    facts.effectIndex = 1;
    CheckRefusal(facts, OneBucketReason::WrongEffect);

    facts = Armed();
    facts.targetEntry = TrainingFireEntry;
    CheckRefusal(facts, OneBucketReason::WrongTarget);

    facts = Armed();
    facts.targetEntry = 99999;
    CheckRefusal(facts, OneBucketReason::WrongTarget);

    facts = Armed();
    facts.oneBucket = 0;
    CheckRefusal(facts, OneBucketReason::OneBucketOff);

    facts = Armed();
    facts.oneBucket = 2;
    CheckRefusal(facts, OneBucketReason::OneBucketOff);

    facts = Armed();
    facts.soloEnabled = 0;
    CheckRefusal(facts, OneBucketReason::SoloEnabledOff);

    facts = Armed();
    facts.oneBucket = 0;
    facts.soloEnabled = 0;
    CheckRefusal(facts, OneBucketReason::OneBucketOff);

    facts = Armed();
    facts.casterIsPlayer = false;
    CheckRefusal(facts, OneBucketReason::NotPlayer);

    facts = Armed();
    facts.casterIsBot = true;
    CheckRefusal(facts, OneBucketReason::BotCaster);

    facts = Armed();
    facts.casterIsBot = true;
    facts.realPlayersInCensus = 1;
    facts.casterInCensus = true;
    CheckRefusal(facts, OneBucketReason::BotCaster);

    facts = Armed();
    facts.targetHasFireAura = false;
    CheckRefusal(facts, OneBucketReason::FireAuraAbsent);

    facts = Armed();
    facts.activeBurningShadeCount = 0;
    CheckRefusal(facts, OneBucketReason::ShadeCount);

    facts = Armed();
    facts.activeBurningShadeCount = 2;
    CheckRefusal(facts, OneBucketReason::ShadeCount);

    facts = Armed();
    facts.realPlayersInCensus = 0;
    facts.casterInCensus = false;
    CheckRefusal(facts, OneBucketReason::Census);

    facts = Armed();
    facts.realPlayersInCensus = 2;
    facts.casterInCensus = true;
    CheckRefusal(facts, OneBucketReason::Census);

    facts = Armed();
    facts.realPlayersInCensus = 1;
    facts.casterInCensus = false;
    CheckRefusal(facts, OneBucketReason::Census);

    facts = Armed();
    facts.casterIsBot = true;
    facts.realPlayersInCensus = 0;
    facts.casterInCensus = true;
    CheckRefusal(facts, OneBucketReason::BotCaster);
}

void CheckSim(
    char const* timing,
    OneBucketFacts facts,
    int32_t amount,
    bool expectFire,
    bool expectUnrelated,
    int expectRemoves,
    int expectSplashes,
    int expectCredit)
{
    AuraModel start;
    start.fire = true;
    start.amount = amount;
    start.unrelated = true;
    SimResult result = Simulate(timing, facts, start, true);
    CHECK(result.child);
    CHECK(result.fire == expectFire);
    CHECK(result.unrelated == expectUnrelated);
    CHECK(result.featureRemoves == expectRemoves);
    CHECK(result.splashCasts == expectSplashes);
    CHECK(result.featureCasts == 0);
    CHECK(result.questCredits == expectCredit);
    CHECK(result.featureStrippedUnrelated == 0);
}

void CheckTimings()
{
    OneBucketFacts on = Armed();
    OneBucketFacts off = Armed();
    off.oneBucket = 0;

    CheckSim("immediate", on, 3, false, true, 1, 1, 0);
    CheckSim("immediate", on, 2, false, false, 0, 1, 0);
    CheckSim("immediate", on, 1, false, false, 0, 1, 0);
    CheckSim("delayed", on, 3, false, true, 1, 1, 0);
    CheckSim("delayed", on, 2, false, true, 1, 1, 0);
    CheckSim("delayed", on, 1, false, true, 1, 1, 0);

    CheckSim("immediate", off, 3, true, true, 0, 1, 0);
    CheckSim("immediate", off, 1, false, false, 0, 1, 0);
    CheckSim("delayed", off, 3, true, true, 0, 1, 0);
    CheckSim("delayed", off, 1, false, false, 0, 1, 0);

    OneBucketFacts outside = Armed();
    outside.casterInCensus = false;
    CheckSim("immediate", outside, 3, true, true, 0, 1, 0);
    CheckSim("delayed", outside, 3, true, true, 0, 1, 0);

    OneBucketFacts train = Armed();
    train.targetEntry = TrainingFireEntry;
    CheckSim("immediate", train, 3, true, true, 0, 1, 1);
    CheckSim("immediate", train, 1, false, false, 0, 1, 1);
    CheckSim("delayed", train, 3, true, true, 0, 1, 1);

    OneBucketFacts miss = Armed();
    miss.hitAccepted = false;
    AuraModel start;
    start.amount = 3;
    SimResult missed = Simulate("immediate", miss, start, true);
    CHECK(missed.fire);
    CHECK(missed.unrelated);
    CHECK(missed.splashCasts == 0);
    CHECK(missed.featureRemoves == 0);
    CHECK(missed.child);
    CHECK(missed.questCredits == 0);

    OneBucketFacts splashOnly = Armed();
    splashOnly.spellId = WaterSplashSpellId;
    SimResult notBucket = Simulate("immediate", splashOnly, start, true);
    CHECK(notBucket.featureRemoves == 0);
    CHECK(notBucket.splashCasts == 0);
    CHECK(notBucket.fire);
    CHECK(notBucket.child);

    OneBucketFacts noAura = Armed();
    noAura.targetHasFireAura = false;
    AuraModel cold;
    cold.fire = false;
    cold.amount = 0;
    cold.unrelated = true;
    SimResult absent = Simulate("immediate", noAura, cold, true);
    CHECK(!absent.fire);
    CHECK(absent.unrelated);
    CHECK(absent.featureRemoves == 0);
    CHECK(absent.child);
}

int RunSelfCheck()
{
    CheckParsing();
    CheckArmedRemovesOnlyByDecision();
    CheckNegatives();
    CheckTimings();
    if (g_failures != 0)
    {
        std::fprintf(stderr, "%d checks failed\n", g_failures);
        return 1;
    }
    std::puts("F10_ONE_BUCKET_POLICY_OK");
    return 0;
}

long ReadInt(char const* text)
{
    char* end = nullptr;
    long value = std::strtol(text, &end, 10);
    if (!text || end == text || *end != '\0')
    {
        std::fprintf(stderr, "bad integer %s\n", text ? text : "(null)");
        std::exit(2);
    }
    return value;
}

OneBucketFacts FactsFromArgs(char** argv)
{
    OneBucketFacts facts;
    facts.hitAccepted = ReadInt(argv[0]) != 0;
    facts.spellId = static_cast<uint32_t>(ReadInt(argv[1]));
    facts.effectIndex = static_cast<uint8_t>(ReadInt(argv[2]));
    facts.targetEntry = static_cast<uint32_t>(ReadInt(argv[3]));
    facts.targetHasFireAura = ReadInt(argv[4]) != 0;
    facts.oneBucket = static_cast<int32_t>(ReadInt(argv[5]));
    facts.soloEnabled = static_cast<int32_t>(ReadInt(argv[6]));
    facts.casterIsPlayer = ReadInt(argv[7]) != 0;
    facts.casterIsBot = ReadInt(argv[8]) != 0;
    facts.casterInCensus = ReadInt(argv[9]) != 0;
    facts.realPlayersInCensus = static_cast<uint32_t>(ReadInt(argv[10]));
    facts.activeBurningShadeCount = static_cast<uint32_t>(ReadInt(argv[11]));
    return facts;
}
}

int main(int argc, char** argv)
{
    if (argc == 1)
        return RunSelfCheck();

    if (argc == 14 && std::strcmp(argv[1], "--decide") == 0)
    {
        OneBucketDecision decision = DecideOneBucket(FactsFromArgs(argv + 2));
        std::printf(
            "remove=%d reason=%s\n",
            decision.removeFireAura ? 1 : 0,
            ReasonName(decision.reason));
        return 0;
    }

    if (argc == 18 && std::strcmp(argv[1], "--simulate") == 0)
    {
        OneBucketFacts facts = FactsFromArgs(argv + 3);
        AuraModel start;
        start.fire = facts.targetHasFireAura;
        start.amount = static_cast<int32_t>(ReadInt(argv[15]));
        start.unrelated = ReadInt(argv[16]) != 0;
        bool child = ReadInt(argv[17]) != 0;
        if (!start.fire)
            start.amount = 0;
        PrintSim(Simulate(argv[2], facts, start, child));
        return 0;
    }

    std::fprintf(stderr, "usage: %s [--decide ...] [--simulate timing ...]\n", argv[0]);
    return 2;
}
