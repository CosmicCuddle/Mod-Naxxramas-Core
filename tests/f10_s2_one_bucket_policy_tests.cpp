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
        case OneBucketReason::PlayerbotsApiUnavailable:
            return "PlayerbotsApiUnavailable";
        case OneBucketReason::BotCaster:
            return "BotCaster";
        case OneBucketReason::FireAuraAbsent:
            return "FireAuraAbsent";
        case OneBucketReason::ShadeCount:
            return "ShadeCount";
        case OneBucketReason::OwnerNotIgnited:
            return "OwnerNotIgnited";
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
    facts.playerbotsApiPresent = true;
    facts.casterIsRealPlayer = true;
    facts.casterInCensus = true;
    facts.realPlayersInCensus = 1;
    facts.livingOwnerShadeCount = 1;
    facts.activeOwnerShadeCount = 1;
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
    facts.playerbotsApiPresent = false;
    facts.casterIsRealPlayer = true;
    CheckRefusal(facts, OneBucketReason::PlayerbotsApiUnavailable);

    facts = Armed();
    facts.casterIsRealPlayer = false;
    CheckRefusal(facts, OneBucketReason::BotCaster);

    facts = Armed();
    facts.casterIsRealPlayer = false;
    facts.realPlayersInCensus = 1;
    facts.casterInCensus = true;
    CheckRefusal(facts, OneBucketReason::BotCaster);

    facts = Armed();
    facts.targetHasFireAura = false;
    CheckRefusal(facts, OneBucketReason::FireAuraAbsent);

    facts = Armed();
    facts.livingOwnerShadeCount = 0;
    facts.activeOwnerShadeCount = 0;
    CheckRefusal(facts, OneBucketReason::ShadeCount);

    facts = Armed();
    facts.livingOwnerShadeCount = 2;
    facts.activeOwnerShadeCount = 2;
    CheckRefusal(facts, OneBucketReason::ShadeCount);

    facts = Armed();
    facts.livingOwnerShadeCount = 2;
    facts.activeOwnerShadeCount = 1;
    CheckRefusal(facts, OneBucketReason::ShadeCount);

    facts = Armed();
    facts.livingOwnerShadeCount = 1;
    facts.activeOwnerShadeCount = 0;
    CheckRefusal(facts, OneBucketReason::OwnerNotIgnited);

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
    facts.casterIsRealPlayer = false;
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

struct ScenarioLine
{
    bool known = false;
    int remove = 0;
    char const* reason = "Unknown";
    unsigned living = 0;
    unsigned active = 0;
    unsigned ignited = 0;
    unsigned reals = 0;
};

OneBucketObservation BaseObservation()
{
    OneBucketObservation obs;
    obs.hitAccepted = true;
    obs.spellId = BucketLandSpellId;
    obs.effectIndex = BucketLandEffectIndex;
    obs.targetEntry = FireTriggerEntry;
    obs.targetHasFireAura = true;
    obs.oneBucket = 1;
    obs.soloEnabled = 1;
    obs.casterIsPlayer = true;
    obs.playerbotsApiPresent = true;
    return obs;
}

ShadeOwnerView OwningShade(bool ignited)
{
    ShadeOwnerView shade;
    shade.alive = true;
    shade.moduleScript = true;
    shade.ownsTrigger = true;
    shade.ignitedThisTrigger = ignited;
    return shade;
}

void Publish(
    ScenarioLine& line,
    OneBucketObservation const& obs,
    std::size_t ignited)
{
    OneBucketFacts facts = FactsFromObservation(obs);
    OneBucketDecision decision = DecideOneBucket(facts);
    line.known = true;
    line.remove = decision.removeFireAura ? 1 : 0;
    line.reason = ReasonName(decision.reason);
    line.living = facts.livingOwnerShadeCount;
    line.active = facts.activeOwnerShadeCount;
    line.reals = facts.realPlayersInCensus;
    line.ignited = static_cast<unsigned>(ignited);
}

/* accountName is accepted and ignored. Classification is the pinned
 * IsRealPlayer contract: a non-null object with no PlayerbotAI.
 */
ScenarioLine ClassifiedThrow(
    char const* accountName,
    bool apiPresent,
    bool objectNonNull,
    bool aiAttached,
    bool failOpenLie)
{
    (void)accountName;
    constexpr uint64_t triggerId = 99;
    constexpr uint64_t casterId = 7;
    FireCastRequest request;
    request.unlitTriggerCount = 1;
    request.playerCountBeforeSoloFilter = 2;
    request.playerCountAfterSoloFilter = 2;
    request.initial = true;
    CycleIgnition cycle;
    if (FireCastRequestReachesIgnition(request))
        cycle.NoteCastInitiated(triggerId);

    ShadeOwnerView shades[1];
    shades[0] = OwningShade(cycle.Contains(triggerId));

    bool const contractReal = PinnedIsRealPlayerContract(objectNonNull, aiAttached);
    CensusPlayerView players[2]{};
    players[0].playerId = casterId;
    players[0].isRealPlayer = failOpenLie ? true : contractReal;
    players[1].playerId = 8;
    players[1].isRealPlayer = apiPresent && !aiAttached ? false : true;

    OneBucketObservation obs = BaseObservation();
    obs.playerbotsApiPresent = apiPresent;
    obs.casterIsPlayer = objectNonNull;
    obs.casterIsRealPlayer = failOpenLie ? true : contractReal;
    obs.casterId = casterId;
    obs.shades = shades;
    obs.shadeCount = 1;
    obs.players = players;
    obs.playerCount = 2;

    ScenarioLine line;
    Publish(line, obs, cycle.triggered.size());
    return line;
}

ScenarioLine OwnerScenario(ShadeOwnerView const* shades, std::size_t count, std::size_t ignited)
{
    CensusPlayerView players[1]{};
    players[0].playerId = 7;
    players[0].isRealPlayer = true;
    OneBucketObservation obs = BaseObservation();
    obs.casterIsRealPlayer = true;
    obs.casterId = 7;
    obs.shades = shades;
    obs.shadeCount = count;
    obs.players = players;
    obs.playerCount = 1;
    ScenarioLine line;
    Publish(line, obs, ignited);
    return line;
}

ScenarioLine EarlyReturnScenario(FireCastRequest const& request)
{
    constexpr uint64_t triggerId = 99;
    CycleIgnition cycle;
    if (FireCastRequestReachesIgnition(request))
        cycle.NoteCastInitiated(triggerId);
    ShadeOwnerView shades[1];
    shades[0] = OwningShade(cycle.Contains(triggerId));
    return OwnerScenario(shades, 1, cycle.triggered.size());
}

ScenarioLine RunScenario(char const* name)
{
    if (std::strcmp(name, "sole-real") == 0)
        return ClassifiedThrow("Ada", true, true, false, false);
    if (std::strcmp(name, "rndbot-account-human") == 0)
        return ClassifiedThrow("RNDBOT999", true, true, false, false);
    if (std::strcmp(name, "self-bot") == 0)
        return ClassifiedThrow("Ada", true, true, true, false);
    if (std::strcmp(name, "odd-account-bot") == 0)
        return ClassifiedThrow("HelgaTheFarmer", true, true, true, false);
    if (std::strcmp(name, "no-header") == 0)
        return ClassifiedThrow("Ada", false, true, false, true);

    if (std::strcmp(name, "overlap-inactive") == 0)
    {
        ShadeOwnerView shades[4];
        shades[0] = OwningShade(true);
        shades[1] = OwningShade(false);
        shades[2] = OwningShade(true);
        shades[2].alive = false;
        shades[3] = OwningShade(true);
        shades[3].ownsTrigger = false;
        return OwnerScenario(shades, 4, 1);
    }

    if (std::strcmp(name, "two-active") == 0)
    {
        ShadeOwnerView shades[2];
        shades[0] = OwningShade(true);
        shades[1] = OwningShade(true);
        return OwnerScenario(shades, 2, 2);
    }

    if (std::strcmp(name, "stale-aura") == 0)
    {
        CycleIgnition inherited;
        ShadeOwnerView shades[1];
        shades[0] = OwningShade(inherited.Contains(99));
        return OwnerScenario(shades, 1, inherited.triggered.size());
    }

    if (std::strcmp(name, "empty-triggers") == 0)
    {
        FireCastRequest request;
        request.unlitTriggerCount = 0;
        request.playerCountBeforeSoloFilter = 1;
        request.playerCountAfterSoloFilter = 1;
        request.initial = true;
        return EarlyReturnScenario(request);
    }

    if (std::strcmp(name, "empty-players") == 0)
    {
        FireCastRequest request;
        request.unlitTriggerCount = 2;
        request.playerCountBeforeSoloFilter = 0;
        request.playerCountAfterSoloFilter = 0;
        request.initial = true;
        return EarlyReturnScenario(request);
    }

    if (std::strcmp(name, "empty-solo-filter") == 0)
    {
        FireCastRequest request;
        request.unlitTriggerCount = 2;
        request.playerCountBeforeSoloFilter = 4;
        request.playerCountAfterSoloFilter = 0;
        request.initial = false;
        request.rateAllows = true;
        return EarlyReturnScenario(request);
    }

    return {};
}

void ExpectScenario(
    char const* name,
    int remove,
    char const* reason,
    unsigned living,
    unsigned active,
    unsigned ignited)
{
    ScenarioLine line = RunScenario(name);
    CHECK(line.known);
    CHECK(line.remove == remove);
    CHECK(std::strcmp(line.reason, reason) == 0);
    CHECK(line.living == living);
    CHECK(line.active == active);
    CHECK(line.ignited == ignited);
}

void CheckWiringHarness()
{
    ExpectScenario("sole-real", 1, "RemoveFireAura", 1, 1, 1);
    ExpectScenario("rndbot-account-human", 1, "RemoveFireAura", 1, 1, 1);
    ExpectScenario("self-bot", 0, "BotCaster", 1, 1, 1);
    ExpectScenario("odd-account-bot", 0, "BotCaster", 1, 1, 1);
    ExpectScenario("no-header", 0, "PlayerbotsApiUnavailable", 1, 1, 1);
    ExpectScenario("overlap-inactive", 0, "ShadeCount", 2, 1, 1);
    ExpectScenario("two-active", 0, "ShadeCount", 2, 2, 2);
    ExpectScenario("stale-aura", 0, "OwnerNotIgnited", 1, 0, 0);
    ExpectScenario("empty-triggers", 0, "OwnerNotIgnited", 1, 0, 0);
    ExpectScenario("empty-players", 0, "OwnerNotIgnited", 1, 0, 0);
    ExpectScenario("empty-solo-filter", 0, "OwnerNotIgnited", 1, 0, 0);

    ScenarioLine selfBot = RunScenario("self-bot");
    ScenarioLine oddAccount = RunScenario("odd-account-bot");
    CHECK(selfBot.remove == oddAccount.remove);
    CHECK(std::strcmp(selfBot.reason, oddAccount.reason) == 0);
    CHECK(RunScenario("no-header").reals == 0);

    CycleIgnition cycle;
    cycle.NoteCastInitiated(99);
    CHECK(cycle.Contains(99));
    cycle.Clear();
    CHECK(!cycle.Contains(99));
    CHECK(!cycle.Contains(0));

    FireCastRequest blocked;
    blocked.unlitTriggerCount = 0;
    blocked.playerCountBeforeSoloFilter = 1;
    blocked.playerCountAfterSoloFilter = 1;
    blocked.initial = true;
    CHECK(!FireCastRequestReachesIgnition(blocked));
}

int RunSelfCheck()
{
    CheckParsing();
    CheckArmedRemovesOnlyByDecision();
    CheckNegatives();
    CheckTimings();
    CheckWiringHarness();
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
    facts.playerbotsApiPresent = ReadInt(argv[8]) != 0;
    facts.casterIsRealPlayer = ReadInt(argv[9]) != 0;
    facts.casterInCensus = ReadInt(argv[10]) != 0;
    facts.realPlayersInCensus = static_cast<uint32_t>(ReadInt(argv[11]));
    facts.livingOwnerShadeCount = static_cast<uint32_t>(ReadInt(argv[12]));
    facts.activeOwnerShadeCount = static_cast<uint32_t>(ReadInt(argv[13]));
    return facts;
}

int PrintScenario(char const* name)
{
    ScenarioLine line = RunScenario(name);
    if (!line.known)
    {
        std::fprintf(stderr, "unknown scenario %s\n", name);
        return 2;
    }
    std::printf(
        "scenario=%s remove=%d reason=%s living=%u active=%u ignited=%u reals=%u\n",
        name,
        line.remove,
        line.reason,
        line.living,
        line.active,
        line.ignited,
        line.reals);
    return 0;
}
}

int main(int argc, char** argv)
{
    if (argc == 1)
        return RunSelfCheck();

    if (argc == 3 && std::strcmp(argv[1], "--scenario") == 0)
        return PrintScenario(argv[2]);

    if (argc == 16 && std::strcmp(argv[1], "--decide") == 0)
    {
        OneBucketDecision decision = DecideOneBucket(FactsFromArgs(argv + 2));
        std::printf(
            "remove=%d reason=%s\n",
            decision.removeFireAura ? 1 : 0,
            ReasonName(decision.reason));
        return 0;
    }

    if (argc == 20 && std::strcmp(argv[1], "--simulate") == 0)
    {
        OneBucketFacts facts = FactsFromArgs(argv + 3);
        AuraModel start;
        start.fire = facts.targetHasFireAura;
        start.amount = static_cast<int32_t>(ReadInt(argv[17]));
        start.unrelated = ReadInt(argv[18]) != 0;
        bool child = ReadInt(argv[19]) != 0;
        if (!start.fire)
            start.amount = 0;
        PrintSim(Simulate(argv[2], facts, start, child));
        return 0;
    }

    std::fprintf(stderr, "usage: %s [--decide ...] [--simulate timing ...] [--scenario name]\n", argv[0]);
    return 2;
}
