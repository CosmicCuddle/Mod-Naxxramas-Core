// F14: native tests for src/Systems/F14VerifiedRandomBotPolicy.h.
// Pure standard C++; no core, Playerbots, IP or server. Build with -pthread.
#include "F14VerifiedRandomBotPolicy.h"

#include <chrono>
#include <cstdio>
#include <vector>

using namespace NaxxramasF14VerifiedRandomBot;
using NaxxramasPlayerIdentity::Facts;
using NaxxramasPlayerIdentity::IdentityBoard;
using NaxxramasPlayerIdentity::Policy;
using NaxxramasPlayerIdentity::PolicyConfig;
using NaxxramasPlayerIdentity::RACE_BLOODELF;
using NaxxramasPlayerIdentity::RACE_DRAENEI;
using std::chrono::seconds;

namespace
{
    int failures = 0;
    int checks = 0;

#define CHECK(cond)                                                          \
    do                                                                       \
    {                                                                        \
        ++checks;                                                            \
        if (!(cond))                                                         \
        {                                                                    \
            ++failures;                                                      \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);      \
        }                                                                    \
    } while (0)

    std::uint8_t const TBC_RACES[] = {RACE_BLOODELF, RACE_DRAENEI};

    // Every enum value, plus out-of-range raw values a bad caller could pass.
    ObserverEra const ERAS[] = {ObserverEra::Unknown, ObserverEra::Vanilla,
                                ObserverEra::TbcOrLater, static_cast<ObserverEra>(3),
                                static_cast<ObserverEra>(255)};
    Identity const IDENTITIES[] = {Identity::Unknown, Identity::Human, Identity::SelfBot,
                                   Identity::RandomBot, Identity::AltBot,
                                   static_cast<Identity>(7), static_cast<Identity>(255)};
    Identity const NON_RANDOM[] = {Identity::Unknown, Identity::Human, Identity::SelfBot,
                                   Identity::AltBot};

    Observer VanillaPlayer()
    {
        return Observer{ObserverEra::Vanilla, true};
    }

    Row VerifiedRandomBot(std::uint8_t race)
    {
        return Row{race, true, Identity::RandomBot, true};
    }

    // Facts in the shape #197/#202 sample them.
    Facts HumanFacts()
    {
        Facts f;
        f.inWorld = f.hasSession = f.socketOpen = f.playerbotsEnabled = true;
        return f;
    }

    Facts HeadlessRandomFacts()
    {
        Facts f;
        f.inWorld = f.hasSession = f.playerbotsEnabled = f.botAiAttached = true;
        f.randomBotListed = true;
        return f;
    }

    Facts AltBotFacts()
    {
        Facts f;
        f.inWorld = f.hasSession = f.playerbotsEnabled = f.botAiAttached = true;
        return f;
    }

    Facts SelfBotFacts()
    {
        Facts f = HumanFacts();
        f.botAiAttached = f.botMasterIsSelf = true;
        return f;
    }

    // 1. Full cross product. Exactly one combination per TBC race may hide,
    //    and it is the one where all six positive inputs hold.
    void TestCrossProduct()
    {
        long total = 0;
        long hidden = 0;
        int hiddenBloodElf = 0;
        int hiddenDraenei = 0;
        for (ObserverEra era : ERAS)
            for (int gm = 0; gm < 2; ++gm)
                for (int notSelf = 0; notSelf < 2; ++notSelf)
                    for (unsigned race = 0; race < 256; ++race)
                        for (Identity id : IDENTITIES)
                            for (int verified = 0; verified < 2; ++verified)
                            {
                                Observer const o{era, gm == 1};
                                Row const r{static_cast<std::uint8_t>(race), notSelf == 1, id,
                                            verified == 1};
                                bool const hide = HideFromVanillaObserver(o, r);
                                ++total;
                                if (!hide)
                                    continue;
                                ++hidden;
                                hiddenBloodElf += race == RACE_BLOODELF;
                                hiddenDraenei += race == RACE_DRAENEI;
                                // A hidden row must satisfy every positive input.
                                CHECK(era == ObserverEra::Vanilla);
                                CHECK(gm == 1);
                                CHECK(notSelf == 1);
                                CHECK(id == Identity::RandomBot);
                                CHECK(verified == 1);
                            }
        CHECK(total == 5L * 2 * 2 * 256 * 7 * 2);
        CHECK(hidden == 2);
        CHECK(hiddenBloodElf == 1);
        CHECK(hiddenDraenei == 1);
    }

    // 2. Defaults and single-field flips: each positive input on its own is
    //    necessary. Starting from the one hiding case, clearing any single
    //    field shows the row.
    void TestEachConditionNecessary()
    {
        CHECK(!HideFromVanillaObserver(Observer{}, Row{}));
        for (std::uint8_t race : TBC_RACES)
        {
            Row const full = VerifiedRandomBot(race);
            CHECK(HideFromVanillaObserver(VanillaPlayer(), full));

            CHECK(!HideFromVanillaObserver(Observer{}, full));                            // era unknown, GM unknown
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::Vanilla, false}, full)); // GM or GM unknown
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::Unknown, true}, full));  // era unknown
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::TbcOrLater, true}, full));

            Row ownRow = full;
            ownRow.confirmedNotObserver = false;
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), ownRow));

            Row unverified = full;
            unverified.verifiedSelectedRandomBot = false;
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), unverified));

            Row rowDefaults{};
            rowDefaults.race = race;
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowDefaults));
        }
        // A verified Random Playerbot of any non-TBC race is never hidden.
        for (unsigned race = 0; race < 256; ++race)
            if (race != RACE_BLOODELF && race != RACE_DRAENEI)
                CHECK(!HideFromVanillaObserver(VanillaPlayer(),
                                               VerifiedRandomBot(static_cast<std::uint8_t>(race))));
    }

    // 3. CS01's named negative witnesses: Unknown, AltBot, Human (and
    //    SelfBot) Blood Elf / Draenei stay visible to a Vanilla player even
    //    if a caller wrongly sets the verified flag.
    void TestNegativeWitnesses()
    {
        for (std::uint8_t race : TBC_RACES)
            for (Identity id : NON_RANDOM)
                for (int verified = 0; verified < 2; ++verified)
                    CHECK(!HideFromVanillaObserver(VanillaPlayer(),
                                                   Row{race, true, id, verified == 1}));
    }

    // 4. Observer side: Vanilla hides only the verified bot; TBC+, unknown
    //    era and GMs see it.
    void TestObservers()
    {
        for (std::uint8_t race : TBC_RACES)
        {
            Row const bot = VerifiedRandomBot(race);
            CHECK(HideFromVanillaObserver(Observer{ObserverEra::Vanilla, true}, bot));
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::TbcOrLater, true}, bot));
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::TbcOrLater, false}, bot));
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::Unknown, true}, bot));
            CHECK(!HideFromVanillaObserver(Observer{ObserverEra::Vanilla, false}, bot)); // GM
            CHECK(!HideFromVanillaObserver(Observer{static_cast<ObserverEra>(3), true}, bot));
            CHECK(!HideFromVanillaObserver(Observer{static_cast<ObserverEra>(255), true}, bot));
        }
    }

    // 5. Through #197's Classify: headless / no-socket / config heuristics
    //    alone never hide; only a RandomBot classification plus explicit
    //    verification does.
    void TestThroughClassify()
    {
        using NaxxramasPlayerIdentity::Classify;
        for (std::uint8_t race : TBC_RACES)
        {
            auto const rowFor = [race](Facts const& f, bool verified) {
                return Row{race, true, Classify(f), verified};
            };

            // Headless Random Playerbot, not verified: visible.
            CHECK(Classify(HeadlessRandomFacts()) == Identity::RandomBot);
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(HeadlessRandomFacts(), false)));
            // Same bot with explicit verification: hidden.
            CHECK(HideFromVanillaObserver(VanillaPlayer(), rowFor(HeadlessRandomFacts(), true)));

            // Humans, SelfBots and AltBots stay visible even if "verified".
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(HumanFacts(), true)));
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(SelfBotFacts(), true)));
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(AltBotFacts(), true)));

            // Playerbots disabled: a socketless bot is Unknown and visible.
            Facts masked = HeadlessRandomFacts();
            masked.playerbotsEnabled = false;
            CHECK(Classify(masked) == Identity::Unknown);
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(masked, true)));

            // Human whose client dropped: Unknown, visible.
            Facts dropped = HumanFacts();
            dropped.socketOpen = false;
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(dropped, true)));

            // Contradiction (socket open but random-listed): Unknown, visible.
            Facts contradiction = HumanFacts();
            contradiction.randomBotListed = true;
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(contradiction, true)));

            // Out of world: Unknown, visible.
            Facts outOfWorld = HeadlessRandomFacts();
            outOfWorld.inWorld = false;
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowFor(outOfWorld, true)));
        }

        // All 128 #197 fact combinations: hidden only when Classify gives
        // RandomBot, and never without verification.
        for (unsigned bits = 0; bits < 128; ++bits)
        {
            Facts f;
            f.inWorld = bits & 1u;
            f.hasSession = bits & 2u;
            f.socketOpen = bits & 4u;
            f.playerbotsEnabled = bits & 8u;
            f.botAiAttached = bits & 16u;
            f.botMasterIsSelf = bits & 32u;
            f.randomBotListed = bits & 64u;
            Identity const id = Classify(f);
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), Row{RACE_BLOODELF, true, id, false}));
            CHECK(HideFromVanillaObserver(VanillaPlayer(), Row{RACE_BLOODELF, true, id, true}) ==
                  (id == Identity::RandomBot));
        }
    }

    // 6. Through #197's IdentityBoard: missing or stale identity is Unknown
    //    and therefore visible (old policy B would have hidden it).
    void TestThroughBoard()
    {
        IdentityBoard board;
        IdentityBoard::Clock::time_point const t0{seconds(1000)};
        auto const maxAge = seconds(10);
        auto const rowAt = [&](std::uint32_t guid, IdentityBoard::Clock::time_point now) {
            return Row{RACE_DRAENEI, true, board.Lookup(guid, now, maxAge), true};
        };

        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(6, t0)));       // never published

        board.Publish(t0, {{5, HumanFacts()}, {6, HeadlessRandomFacts()}, {7, AltBotFacts()}});
        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(5, t0)));
        CHECK(HideFromVanillaObserver(VanillaPlayer(), rowAt(6, t0)));
        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(7, t0)));
        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(8, t0)));       // not sampled
        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(6, t0 + maxAge + seconds(1))));
        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(6, t0 - seconds(1))));

        board.Invalidate();
        CHECK(!HideFromVanillaObserver(VanillaPlayer(), rowAt(6, t0)));
    }

    // 7. Historical baselines from PlayerIdentityPolicy.h. The new rule is
    //    strictly narrower than both: whatever it hides, A and B also hide;
    //    and here are rows A and B hide that the owner rule keeps visible.
    void TestNarrowerThanHistoricalAandB()
    {
        using NaxxramasPlayerIdentity::HideTbcRow;
        PolicyConfig const a{Policy::HideAllTbcRaces, false};
        PolicyConfig const b{Policy::HideBotsOnly, false};

        for (ObserverEra era : ERAS)
            for (int gm = 0; gm < 2; ++gm)
                for (int notSelf = 0; notSelf < 2; ++notSelf)
                    for (std::uint8_t race : {std::uint8_t{0}, std::uint8_t{1}, RACE_BLOODELF,
                                              RACE_DRAENEI, std::uint8_t{255}})
                        for (Identity id : IDENTITIES)
                            for (int verified = 0; verified < 2; ++verified)
                            {
                                Row const r{race, notSelf == 1, id, verified == 1};
                                if (HideFromVanillaObserver(Observer{era, gm == 1}, r))
                                {
                                    bool const ownRow = notSelf == 0;
                                    CHECK(HideTbcRow(a, race, ownRow, id));
                                    CHECK(HideTbcRow(b, race, ownRow, id));
                                }
                            }

        for (std::uint8_t race : TBC_RACES)
        {
            // Human Blood Elf / Draenei: A hides, owner rule shows.
            CHECK(HideTbcRow(a, race, false, Identity::Human));
            CHECK(!HideFromVanillaObserver(VanillaPlayer(), Row{race, true, Identity::Human, false}));
            // AltBot, SelfBot, Unknown: B hides, owner rule shows.
            for (Identity id : {Identity::AltBot, Identity::SelfBot, Identity::Unknown})
            {
                CHECK(HideTbcRow(b, race, false, id));
                CHECK(!HideFromVanillaObserver(VanillaPlayer(), Row{race, true, id, false}));
            }
            // Unverified RandomBot: A and B hide, owner rule shows.
            CHECK(HideTbcRow(a, race, false, Identity::RandomBot));
            CHECK(HideTbcRow(b, race, false, Identity::RandomBot));
            CHECK(!HideFromVanillaObserver(VanillaPlayer(),
                                           Row{race, true, Identity::RandomBot, false}));
        }
    }

    // 8. Compile-time: the rule is constexpr and the defaults show.
    static_assert(!HideFromVanillaObserver(Observer{}, Row{}), "defaults must show");
    static_assert(HideFromVanillaObserver(Observer{ObserverEra::Vanilla, true},
                                          Row{RACE_BLOODELF, true, Identity::RandomBot, true}),
                  "the single positive case must hide");
    static_assert(Observer{}.era == ObserverEra::Unknown, "observer era defaults to Unknown");
    static_assert(!Observer{}.confirmedNonGameMaster, "GM status defaults to unknown");
    static_assert(!Row{}.confirmedNotObserver, "own row by default");
    static_assert(Row{}.identity == Identity::Unknown, "identity defaults to Unknown");
    static_assert(!Row{}.verifiedSelectedRandomBot, "verification defaults to absent");
}

int main()
{
    TestCrossProduct();
    TestEachConditionNecessary();
    TestNegativeWitnesses();
    TestObservers();
    TestThroughClassify();
    TestThroughBoard();
    TestNarrowerThanHistoricalAandB();

    if (failures != 0)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: F14 verified RandomBot policy, %d checks\n", checks);
    return 0;
}
