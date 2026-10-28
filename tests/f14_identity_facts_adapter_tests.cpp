// F14 P5: native tests of the REAL src/Systems/PlayerIdentityFacts.cpp.
//
// The adapter .cpp is compiled unmodified in this TU against small stubs in
// tests/f14_facts_stubs. Build twice:
//   with Playerbots:    -Itests/f14_facts_stubs/core -Itests/f14_facts_stubs/playerbots
//   without Playerbots: -Itests/f14_facts_stubs/core            (-DEXPECT_NO_PLAYERBOTS)
// Only this test defines WorldThreadSamplingGrant; module sources never do.
#include "PlayerIdentityFacts.cpp"

#include <cstdio>

namespace NaxxramasPlayerIdentity
{
    struct WorldThreadSamplingGrant
    {
        static WorldThreadSampling Token() { return WorldThreadSampling(); }
    };
}

using namespace NaxxramasPlayerIdentity;

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

    WorldThreadSampling const TOKEN = WorldThreadSamplingGrant::Token();

    Identity Of(Player* p) { return Classify(SampleFacts(TOKEN, p)); }

    bool SameFacts(Facts const& a, Facts const& b)
    {
        return a.inWorld == b.inWorld && a.hasSession == b.hasSession &&
               a.socketOpen == b.socketOpen && a.playerbotsEnabled == b.playerbotsEnabled &&
               a.botAiAttached == b.botAiAttached && a.botMasterIsSelf == b.botMasterIsSelf &&
               a.randomBotListed == b.randomBotListed;
    }

    bool IsEmpty(Facts const& f) { return SameFacts(f, Facts{}); }

    struct Fixture
    {
        WorldSession session;
        Player player;
        Fixture(bool inWorld, bool socket)
        {
            player.inWorld = inWorld;
            player.session = &session;
            session.socketClosed = !socket;
        }
    };

#if !defined(EXPECT_NO_PLAYERBOTS)
    PlayerbotsMgr& Bots() { return PlayerbotsMgr::instance(); }
    RandomPlayerbotMgr& Random() { return RandomPlayerbotMgr::instance(); }

    void Reset()
    {
        sPlayerbotAIConfig.Enabled = true;
        Bots().ais.clear();
        Random().current.clear();
    }

    void TestFourIdentitiesPositively()
    {
        Reset();
        CHECK(AdapterHasPlayerbots());

        // Human: live client socket, no AI.
        Fixture human(true, true);
        CHECK(Of(&human.player) == Identity::Human);

        // SelfBot: the human's own session with AI mastered by itself.
        Fixture self(true, true);
        PlayerbotAI selfAi;
        selfAi.master = &self.player;
        Bots().ais[&self.player] = &selfAi;
        Facts const sf = SampleFacts(TOKEN, &self.player);
        CHECK(sf.socketOpen && sf.botAiAttached && sf.botMasterIsSelf && !sf.randomBotListed);
        CHECK(Classify(sf) == Identity::SelfBot);

        // Random bot: no socket, AI mastered by nobody/other, random set.
        Fixture random(true, false);
        PlayerbotAI randomAi;
        Bots().ais[&random.player] = &randomAi;
        Random().current.insert(&random.player);
        CHECK(Of(&random.player) == Identity::RandomBot);

        // AltBot: no socket, AI mastered by its owner, not random.
        Fixture owner(true, true);
        Fixture alt(true, false);
        PlayerbotAI altAi;
        altAi.master = &owner.player;
        Bots().ais[&alt.player] = &altAi;
        CHECK(Of(&alt.player) == Identity::AltBot);
        CHECK(Of(&owner.player) == Identity::Human);
    }

    void TestMissingAndClosed()
    {
        Reset();
        CHECK(IsEmpty(SampleFacts(TOKEN, nullptr)));
        CHECK(Of(nullptr) == Identity::Unknown);

        // Out of world, sessionless and closed-socket humans are not provable.
        Fixture out(false, true);
        CHECK(Of(&out.player) == Identity::Unknown);

        Player noSession;
        noSession.inWorld = true;
        Facts const ns = SampleFacts(TOKEN, &noSession);
        CHECK(!ns.hasSession && !ns.socketOpen);
        CHECK(Classify(ns) == Identity::Unknown);

        Fixture dropped(true, false);                 // logout grace, no AI
        CHECK(Of(&dropped.player) == Identity::Unknown);
    }

    void TestConfigMaskedNeverLooksHuman()
    {
        Reset();
        Fixture alt(true, false);
        Fixture owner(true, true);
        PlayerbotAI altAi;
        altAi.master = &owner.player;
        Bots().ais[&alt.player] = &altAi;
        Fixture random(true, false);
        PlayerbotAI randomAi;
        Bots().ais[&random.player] = &randomAi;
        Random().current.insert(&random.player);

        sPlayerbotAIConfig.Enabled = false;          // e.g. after .reload config
        Facts const masked = SampleFacts(TOKEN, &alt.player);
        CHECK(!masked.playerbotsEnabled && !masked.botAiAttached);
        CHECK(Classify(masked) == Identity::Unknown);
        CHECK(Of(&random.player) == Identity::Unknown);
        CHECK(Of(&owner.player) == Identity::Human);  // socket is the human signal

        // OLD-vs-NEW witness: the Playerbots IsRealPlayer rule
        // (player && !GET_PLAYERBOT_AI(player)) calls both bots human here.
        auto const oldIsRealPlayer = [](Player* p) {
            return p && !PlayerbotsMgr::instance().GetPlayerbotAI(p);
        };
        CHECK(oldIsRealPlayer(&alt.player));
        CHECK(oldIsRealPlayer(&random.player));
        CHECK(Of(&alt.player) != Identity::Human);
        CHECK(Of(&random.player) != Identity::Human);
        // ...and a human whose client dropped: old says human, new Unknown.
        sPlayerbotAIConfig.Enabled = true;
        Fixture dropped(true, false);
        CHECK(oldIsRealPlayer(&dropped.player));
        CHECK(Of(&dropped.player) == Identity::Unknown);
    }

    void TestContradictionsFailClosed()
    {
        Reset();
        // A socketed session in the random set (should never happen).
        Fixture weird(true, true);
        Random().current.insert(&weird.player);
        CHECK(SampleFacts(TOKEN, &weird.player).randomBotListed);
        CHECK(Of(&weird.player) == Identity::Unknown);

        // A socketed session whose AI is mastered by someone else.
        Reset();
        Fixture other(true, true);
        Fixture controlled(true, true);
        PlayerbotAI ai;
        ai.master = &other.player;
        Bots().ais[&controlled.player] = &ai;
        CHECK(Of(&controlled.player) == Identity::Unknown);

        // A linkdead SelfBot (AI on itself, socket gone).
        Reset();
        Fixture linkdead(true, false);
        PlayerbotAI selfAi;
        selfAi.master = &linkdead.player;
        Bots().ais[&linkdead.player] = &selfAi;
        CHECK(Of(&linkdead.player) == Identity::Unknown);
    }

    void TestReadOnlyAndNoRetainedPointer()
    {
        Reset();
        Fixture alt(true, false);
        Fixture owner(true, true);
        PlayerbotAI altAi;
        altAi.master = &owner.player;
        Bots().ais[&alt.player] = &altAi;

        Facts const first = SampleFacts(TOKEN, &alt.player);
        // Nothing the adapter can reach changed.
        CHECK(alt.player.inWorld && alt.session.socketClosed && altAi.master == &owner.player);
        CHECK(Bots().ais.size() == 1 && Random().current.empty() && sPlayerbotAIConfig.Enabled);
        // Facts is plain data: no pointer survives the call.
        static_assert(sizeof(Facts) == 7 * sizeof(bool), "Facts must stay pointer-free flags");
        // Same input, same answer; and a later change is seen only on resample.
        CHECK(SameFacts(first, SampleFacts(TOKEN, &alt.player)));
        alt.session.socketClosed = false;
        CHECK(Classify(first) == Identity::AltBot);
        CHECK(Of(&alt.player) == Identity::Unknown);  // socket + foreign AI
    }

    void TestBoardIntegration()
    {
        Reset();
        Fixture human(true, true);
        Fixture alt(true, false);
        PlayerbotAI altAi;
        altAi.master = &human.player;
        Bots().ais[&alt.player] = &altAi;

        IdentityBoard board;
        IdentityBoard::Clock::time_point const t0{std::chrono::seconds(10)};
        board.Publish(t0, {{101, SampleFacts(TOKEN, &human.player)},
                           {102, SampleFacts(TOKEN, &alt.player)}});
        CHECK(board.Lookup(101, t0, std::chrono::seconds(5)) == Identity::Human);
        CHECK(board.Lookup(102, t0, std::chrono::seconds(5)) == Identity::AltBot);
        PolicyConfig const b{Policy::HideBotsOnly, false};
        CHECK(!HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(101, t0, std::chrono::seconds(5))));
        CHECK(HideTbcRow(b, RACE_BLOODELF, false, board.Lookup(102, t0, std::chrono::seconds(5))));
    }
#else
    void TestNoPlayerbotsBuildIsAlwaysUnknown()
    {
        CHECK(!AdapterHasPlayerbots());
        Fixture human(true, true);
        Facts const f = SampleFacts(TOKEN, &human.player);
        CHECK(IsEmpty(f));
        CHECK(Classify(f) == Identity::Unknown);
        CHECK(human.player.reads == 0 && human.session.reads == 0);   // nothing read
        CHECK(Of(nullptr) == Identity::Unknown);
        PolicyConfig const b{Policy::HideBotsOnly, false};
        CHECK(HideTbcRow(b, RACE_DRAENEI, false, Classify(f)));      // B degrades to A
    }
#endif
}

int main()
{
#if !defined(EXPECT_NO_PLAYERBOTS)
    TestFourIdentitiesPositively();
    TestMissingAndClosed();
    TestConfigMaskedNeverLooksHuman();
    TestContradictionsFailClosed();
    TestReadOnlyAndNoRetainedPointer();
    TestBoardIntegration();
    char const* mode = "with Playerbots";
#else
    TestNoPlayerbotsBuildIsAlwaysUnknown();
    char const* mode = "without Playerbots";
#endif
    if (failures != 0)
    {
        std::printf("FAILED (%s): %d of %d checks\n", mode, failures, checks);
        return 1;
    }
    std::printf("PASS: F14 facts adapter %s, %d checks\n", mode, checks);
    return 0;
}
