// F14 P1: native tests for src/Systems/PlayerIdentityPolicy.h.
// Pure standard C++; no core, Playerbots or server. Build with -pthread.
#include "PlayerIdentityPolicy.h"

#include <atomic>
#include <cstdio>
#include <thread>
#include <vector>

using namespace NaxxramasPlayerIdentity;
using Clock = IdentityBoard::Clock;
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

    Facts Make(unsigned bits)
    {
        Facts f;
        f.inWorld = bits & 1u;
        f.hasSession = bits & 2u;
        f.socketOpen = bits & 4u;
        f.playerbotsEnabled = bits & 8u;
        f.botAiAttached = bits & 16u;
        f.botMasterIsSelf = bits & 32u;
        f.randomBotListed = bits & 64u;
        return f;
    }

    // Independent statement of the rules, written as "what must be true"
    // per identity rather than as the header's branch order.
    Identity Spec(Facts const& f)
    {
        bool const present = f.inWorld && f.hasSession;
        bool const human = present && f.socketOpen && !f.botAiAttached && !f.randomBotListed;
        bool const self = present && f.socketOpen && f.botAiAttached && f.botMasterIsSelf &&
                          !f.randomBotListed;
        bool const bot = present && !f.socketOpen && f.playerbotsEnabled && f.botAiAttached &&
                         !f.botMasterIsSelf;
        if (human)
            return Identity::Human;
        if (self)
            return Identity::SelfBot;
        if (bot && f.randomBotListed)
            return Identity::RandomBot;
        if (bot)
            return Identity::AltBot;
        return Identity::Unknown;
    }

    Facts HumanFacts()
    {
        Facts f;
        f.inWorld = f.hasSession = f.socketOpen = f.playerbotsEnabled = true;
        return f;
    }

    Facts RandomBotFacts()
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

    Identity const ALL_IDENTITIES[] = {Identity::Unknown, Identity::Human, Identity::SelfBot,
                                       Identity::RandomBot, Identity::AltBot};

    void TestClassifierTruthTable()
    {
        int humans = 0;
        for (unsigned bits = 0; bits < 128; ++bits)
        {
            Facts const f = Make(bits);
            Identity const got = Classify(f);
            CHECK(got == Spec(f));

            // No identity other than Unknown without a session in world.
            if (!f.inWorld || !f.hasSession)
                CHECK(got == Identity::Unknown);
            // Human and SelfBot need a live client socket.
            if (got == Identity::Human || got == Identity::SelfBot)
                CHECK(f.socketOpen);
            // A bot identity needs: no socket, Playerbots on, AI attached.
            if (got == Identity::RandomBot || got == Identity::AltBot)
                CHECK(!f.socketOpen && f.playerbotsEnabled && f.botAiAttached);
            // "No AI attached" never proves a human on its own.
            if (!f.socketOpen)
                CHECK(got != Identity::Human);
            humans += got == Identity::Human;
        }
        // inWorld, hasSession, socket, no AI, not random: 2 (enabled) x 2 (self flag).
        CHECK(humans == 4);
    }

    void TestNamedCases()
    {
        CHECK(Classify(HumanFacts()) == Identity::Human);
        CHECK(Classify(RandomBotFacts()) == Identity::RandomBot);
        CHECK(Classify(AltBotFacts()) == Identity::AltBot);
        CHECK(Classify(SelfBotFacts()) == Identity::SelfBot);
        CHECK(Classify(Facts{}) == Identity::Unknown);

        // Human whose client dropped (logout grace): not provable any more.
        Facts dropped = HumanFacts();
        dropped.socketOpen = false;
        CHECK(Classify(dropped) == Identity::Unknown);

        // SelfBot whose client dropped.
        Facts selfDropped = SelfBotFacts();
        selfDropped.socketOpen = false;
        CHECK(Classify(selfDropped) == Identity::Unknown);

        // Playerbots disabled: GetPlayerbotAI returns nullptr for everyone.
        // A socketless bot then looks like "no AI" and must stay Unknown.
        Facts masked = AltBotFacts();
        masked.playerbotsEnabled = false;
        masked.botAiAttached = false;
        CHECK(Classify(masked) == Identity::Unknown);
        // ...while a connected human with Playerbots disabled is still human.
        Facts humanMasked = HumanFacts();
        humanMasked.playerbotsEnabled = false;
        CHECK(Classify(humanMasked) == Identity::Human);

        // Contradictions fail closed.
        Facts socketRandom = HumanFacts();
        socketRandom.randomBotListed = true;
        CHECK(Classify(socketRandom) == Identity::Unknown);
        Facts socketForeignAi = HumanFacts();
        socketForeignAi.botAiAttached = true;
        CHECK(Classify(socketForeignAi) == Identity::Unknown);

        // Out of world or sessionless, whatever else is true.
        Facts outOfWorld = HumanFacts();
        outOfWorld.inWorld = false;
        CHECK(Classify(outOfWorld) == Identity::Unknown);
        Facts noSession = RandomBotFacts();
        noSession.hasSession = false;
        CHECK(Classify(noSession) == Identity::Unknown);
    }

    void TestParsePolicy()
    {
        CHECK(ParsePolicy(0) == Policy::HideAllTbcRaces);
        CHECK(ParsePolicy(1) == Policy::HideBotsOnly);
        for (long long raw : {-1LL, 2LL, 255LL, 256LL, 257LL, -255LL, 1LL << 40})
            CHECK(ParsePolicy(raw) == Policy::HideAllTbcRaces);
        CHECK(PolicyConfig{}.policy == Policy::HideAllTbcRaces);
        CHECK(!PolicyConfig{}.selfBotCountsAsHuman);
    }

    void TestPolicyA()
    {
        PolicyConfig const a{Policy::HideAllTbcRaces, true};
        for (Identity id : ALL_IDENTITIES)
        {
            CHECK(HideTbcRow(a, RACE_BLOODELF, false, id));
            CHECK(HideTbcRow(a, RACE_DRAENEI, false, id));
            CHECK(!HideTbcRow(a, RACE_BLOODELF, true, id));   // own row kept
            CHECK(!HideTbcRow(a, RACE_DRAENEI, true, id));
            for (unsigned race = 0; race < 256; ++race)
                if (race != RACE_BLOODELF && race != RACE_DRAENEI)
                    CHECK(!HideTbcRow(a, static_cast<std::uint8_t>(race), false, id));
        }
    }

    void TestPolicyB()
    {
        PolicyConfig const b{Policy::HideBotsOnly, false};
        for (std::uint8_t race : {RACE_BLOODELF, RACE_DRAENEI})
        {
            CHECK(!HideTbcRow(b, race, false, Identity::Human));
            CHECK(HideTbcRow(b, race, false, Identity::Unknown));
            CHECK(HideTbcRow(b, race, false, Identity::RandomBot));
            CHECK(HideTbcRow(b, race, false, Identity::AltBot));
            CHECK(HideTbcRow(b, race, false, Identity::SelfBot));
            for (Identity id : ALL_IDENTITIES)
                CHECK(!HideTbcRow(b, race, true, id));
        }
        // Non-TBC races are never hidden under B either.
        for (unsigned race = 0; race < 256; ++race)
            if (race != RACE_BLOODELF && race != RACE_DRAENEI)
                for (Identity id : ALL_IDENTITIES)
                    CHECK(!HideTbcRow(b, static_cast<std::uint8_t>(race), false, id));

        PolicyConfig const bSelf{Policy::HideBotsOnly, true};
        CHECK(!HideTbcRow(bSelf, RACE_BLOODELF, false, Identity::SelfBot));
        CHECK(!HideTbcRow(bSelf, RACE_DRAENEI, false, Identity::Human));
        CHECK(HideTbcRow(bSelf, RACE_DRAENEI, false, Identity::AltBot));
        CHECK(HideTbcRow(bSelf, RACE_BLOODELF, false, Identity::RandomBot));
        CHECK(HideTbcRow(bSelf, RACE_BLOODELF, false, Identity::Unknown));

        // An out-of-range policy value can only come from ParsePolicy, which
        // maps it to A. A raw cast still behaves as A (not "show").
        PolicyConfig const bogus{static_cast<Policy>(7), true};
        CHECK(HideTbcRow(bogus, RACE_BLOODELF, false, Identity::Human));
    }

    void TestBoard()
    {
        IdentityBoard board;
        Clock::time_point const t0{seconds(1000)};
        auto const maxAge = seconds(10);

        CHECK(board.Lookup(5, t0, maxAge) == Identity::Unknown);       // never published

        board.Publish(t0, {{5, HumanFacts()}, {6, RandomBotFacts()}, {7, AltBotFacts()},
                           {8, SelfBotFacts()}, {0, HumanFacts()}});
        CHECK(board.Lookup(5, t0, maxAge) == Identity::Human);
        CHECK(board.Lookup(6, t0, maxAge) == Identity::RandomBot);
        CHECK(board.Lookup(7, t0, maxAge) == Identity::AltBot);
        CHECK(board.Lookup(8, t0, maxAge) == Identity::SelfBot);
        CHECK(board.Lookup(0, t0, maxAge) == Identity::Unknown);       // GUID 0 ignored
        CHECK(board.Lookup(9, t0, maxAge) == Identity::Unknown);       // not sampled

        // Freshness window is inclusive at maxAge, closed after it.
        CHECK(board.Lookup(5, t0 + maxAge, maxAge) == Identity::Human);
        CHECK(board.Lookup(5, t0 + maxAge + std::chrono::nanoseconds(1), maxAge) ==
              Identity::Unknown);
        CHECK(board.Lookup(5, t0 - std::chrono::nanoseconds(1), maxAge) == Identity::Unknown);

        // Duplicate GUID in one sample: neither answer is trusted.
        board.Publish(t0, {{5, HumanFacts()}, {5, HumanFacts()}, {6, AltBotFacts()}});
        CHECK(board.Lookup(5, t0, maxAge) == Identity::Unknown);
        CHECK(board.Lookup(6, t0, maxAge) == Identity::AltBot);

        // A republish replaces, never merges: a player who left is Unknown.
        board.Publish(t0 + seconds(1), {{6, AltBotFacts()}});
        CHECK(board.Lookup(5, t0 + seconds(1), maxAge) == Identity::Unknown);
        CHECK(board.Lookup(6, t0 + seconds(1), maxAge) == Identity::AltBot);

        // Identity change between samples (human logs out, alt logs in as bot).
        board.Publish(t0 + seconds(2), {{6, HumanFacts()}});
        CHECK(board.Lookup(6, t0 + seconds(2), maxAge) == Identity::Human);

        board.Invalidate();
        CHECK(board.Lookup(6, t0 + seconds(2), maxAge) == Identity::Unknown);

        // Over the cap: nothing partial is published.
        std::vector<std::pair<std::uint32_t, Facts>> many;
        many.reserve(IdentityBoard::MAX_ENTRIES + 1);
        for (std::uint32_t g = 1; g <= IdentityBoard::MAX_ENTRIES + 1; ++g)
            many.emplace_back(g, HumanFacts());
        board.Publish(t0, many);
        CHECK(board.Lookup(1, t0, maxAge) == Identity::Unknown);
        CHECK(board.Lookup(IdentityBoard::MAX_ENTRIES, t0, maxAge) == Identity::Unknown);

        // Exactly at the cap is accepted.
        many.pop_back();
        board.Publish(t0, many);
        CHECK(board.Lookup(1, t0, maxAge) == Identity::Human);
        CHECK(board.Lookup(IdentityBoard::MAX_ENTRIES, t0, maxAge) == Identity::Human);

        // End to end under policy B: only the human row shows.
        board.Publish(t0, {{5, HumanFacts()}, {6, RandomBotFacts()}, {7, AltBotFacts()}});
        PolicyConfig const b{Policy::HideBotsOnly, false};
        CHECK(!HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(5, t0, maxAge)));
        CHECK(HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(6, t0, maxAge)));
        CHECK(HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(7, t0, maxAge)));
        CHECK(HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(8, t0, maxAge)));
        CHECK(HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(5, t0 + seconds(11), maxAge)));
    }

    // One writer (world thread stand-in) and several readers (map threads).
    // Readers may only ever see Unknown or an identity that some published
    // snapshot held. Run under -fsanitize=thread in CI to prove there is no
    // data race between Publish/Invalidate and Lookup.
    void TestConcurrentPublishAndLookup()
    {
        IdentityBoard board;
        Clock::time_point const t0{seconds(1)};
        std::atomic<bool> stop{false};
        std::atomic<int> torn{0};
        std::atomic<long> reads{0};

        std::vector<std::thread> readers;
        for (int r = 0; r < 4; ++r)
            readers.emplace_back([&] {
                while (!stop.load(std::memory_order_acquire))
                {
                    Identity const a = board.Lookup(1, t0, seconds(5));
                    Identity const c = board.Lookup(2, t0, seconds(5));
                    if (a != Identity::Unknown && a != Identity::Human && a != Identity::AltBot)
                        torn.fetch_add(1);
                    if (c != Identity::Unknown && c != Identity::Human && c != Identity::AltBot)
                        torn.fetch_add(1);
                    reads.fetch_add(1, std::memory_order_relaxed);
                }
            });

        for (int gen = 0; gen < 2000; ++gen)
        {
            bool const even = gen % 2 == 0;
            board.Publish(t0, {{1, even ? HumanFacts() : AltBotFacts()},
                               {2, even ? AltBotFacts() : HumanFacts()}});
            if (gen % 97 == 0)
                board.Invalidate();
        }
        stop.store(true, std::memory_order_release);
        for (auto& t : readers)
            t.join();
        CHECK(torn.load() == 0);
        CHECK(reads.load() > 0);

        // After the writer stops, the last publish is what readers see.
        board.Publish(t0, {{1, HumanFacts()}, {2, AltBotFacts()}});
        CHECK(board.Lookup(1, t0, seconds(5)) == Identity::Human);
        CHECK(board.Lookup(2, t0, seconds(5)) == Identity::AltBot);
    }
}

int main()
{
    TestClassifierTruthTable();
    TestNamedCases();
    TestParsePolicy();
    TestPolicyA();
    TestPolicyB();
    TestBoard();
    TestConcurrentPublishAndLookup();

    if (failures != 0)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: F14 identity classifier, %d checks\n", checks);
    return 0;
}
