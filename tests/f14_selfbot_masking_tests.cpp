// F14 P12 (test-only): a SelfBot while Playerbots is config-disabled.
//
// Compiles the REAL src/Systems/PlayerIdentityFacts.cpp (adapter, #202) and
// the REAL Classify / HideTbcRow (PlayerIdentityPolicy.h, #197) against the
// existing tests/f14_facts_stubs. The stubs keep the pinned d750b4b gates
// that matter; tests/f14_selfbot_masking_facts.py checks those source facts
// against the pinned Playerbots checkout.
//
// Build: g++ -std=c++20 -Isrc/Systems -Itests/f14_facts_stubs/core
//          -Itests/f14_facts_stubs/playerbots tests/f14_selfbot_masking_tests.cpp
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
    constexpr int EXPECTED_CHECKS = 27;
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
    PolicyConfig const B{Policy::HideBotsOnly, false};
    PolicyConfig const B_SELF_AS_HUMAN{Policy::HideBotsOnly, true};

    // Mirror of Playerbots.cpp L248-L254 OnPlayerAfterUpdate: an AI is
    // ticked only through the same config-gated GetPlayerbotAI lookup.
    int TickLikePlayerbots(Player* player)
    {
        return PlayerbotsMgr::instance().GetPlayerbotAI(player) ? 1 : 0;
    }

    // Mirror of PlayerbotMgr.cpp L927-L931: the chat entry needs the
    // config-gated GET_PLAYERBOT_MGR; while disabled it refuses every
    // subcommand, including "self". Modelled as: commands work iff Enabled.
    bool CanUsePlayerbotCommand() { return sPlayerbotAIConfig.Enabled; }

    // The only in-process ways to re-run PlayerbotAIConfig::Initialize are
    // ".playerbots bot reload" (PlayerbotMgr.cpp L1079, behind the L927 gate)
    // and ".playerbots rndbot reload" (RandomPlayerbotMgr.cpp L2534, behind
    // the L2503 "if (!Enabled) return false" gate). Both need Enabled, so a
    // reload that turns Playerbots off cannot be undone without a restart.
    bool CanReloadPlayerbotsConfig() { return sPlayerbotAIConfig.Enabled; }

    // Self toggle, PlayerbotMgr.cpp L1100-L1120: delete the AI if present,
    // else attach one with the player as its own master.
    void SelfToggle(Player* master, PlayerbotAI* ai)
    {
        auto& ais = PlayerbotsMgr::instance().ais;
        if (PlayerbotsMgr::instance().GetPlayerbotAI(master))
            ais.erase(master);
        else
        {
            ai->master = master;
            ais[master] = ai;
        }
    }

    bool SameFacts(Facts const& a, Facts const& b)
    {
        return a.inWorld == b.inWorld && a.hasSession == b.hasSession &&
               a.socketOpen == b.socketOpen && a.playerbotsEnabled == b.playerbotsEnabled &&
               a.botAiAttached == b.botAiAttached && a.botMasterIsSelf == b.botMasterIsSelf &&
               a.randomBotListed == b.randomBotListed;
    }

    struct Character
    {
        WorldSession session;
        Player player;
        Character()
        {
            player.inWorld = true;
            player.session = &session;
            session.socketClosed = false;          // a connected client
        }
    };

    void Reset()
    {
        sPlayerbotAIConfig.Enabled = true;
        PlayerbotsMgr::instance().ais.clear();
        RandomPlayerbotMgr::instance().current.clear();
    }
}

int main()
{
    Reset();
    Character self;                                 // human with an active SelfBot
    PlayerbotAI selfAi;
    selfAi.master = &self.player;
    PlayerbotsMgr::instance().ais[&self.player] = &selfAi;
    Character plain;                                // ordinary connected human

    // Baseline, Playerbots enabled: the SelfBot is identified and ticked.
    Facts const enabledSelf = SampleFacts(TOKEN, &self.player);
    CHECK(Classify(enabledSelf) == Identity::SelfBot);
    CHECK(TickLikePlayerbots(&self.player) == 1);
    CHECK(HideTbcRow(B, RACE_BLOODELF, false, Identity::SelfBot));           // (e) default: hidden
    CHECK(!HideTbcRow(B_SELF_AS_HUMAN, RACE_BLOODELF, false, Identity::SelfBot));
    CHECK(Classify(SampleFacts(TOKEN, &plain.player)) == Identity::Human);

    // (a) Masked attached SelfBot: Enabled=false (a GM "reload" of the
    // Playerbots config). The attachment is NOT evicted...
    sPlayerbotAIConfig.Enabled = false;
    CHECK(PlayerbotsMgr::instance().ais.count(&self.player) == 1);
    Facts const maskedSelf = SampleFacts(TOKEN, &self.player);
    CHECK(maskedSelf.socketOpen && !maskedSelf.playerbotsEnabled && !maskedSelf.botAiAttached);
    CHECK(Classify(maskedSelf) == Identity::Human);                         // the counterexample
    CHECK(!HideTbcRow(B, RACE_BLOODELF, false, Classify(maskedSelf)));       // (e) shown under B
    // ...but it is inert: the same gated lookup means its AI is not ticked.
    CHECK(TickLikePlayerbots(&self.player) == 0);

    // (b) Ordinary human with Playerbots disabled: identical facts.
    Facts const maskedPlain = SampleFacts(TOKEN, &plain.player);
    CHECK(SameFacts(maskedSelf, maskedPlain));                              // unavoidable ambiguity
    CHECK(Classify(maskedPlain) == Identity::Human);
    CHECK(TickLikePlayerbots(&plain.player) == 0);
    // No public, config-independent fact separates them: every Playerbots
    // accessor the adapter may use is gated on Enabled.
    CHECK(PlayerbotsMgr::instance().GetPlayerbotAI(&self.player) == nullptr);
    CHECK(!RandomPlayerbotMgr::instance().IsRandomBot(&self.player));

    // (c) Explicit self-toggle. While masked, both the toggle and every
    // config reload are refused, so masking lasts until a restart.
    CHECK(!CanUsePlayerbotCommand());
    CHECK(!CanReloadPlayerbotsConfig());
    // A restart starts with an empty AI map. The player is Human until the
    // toggle (or SelfBotLevel > 2 auto-self at login, L1734) re-attaches.
    Reset();
    CHECK(CanUsePlayerbotCommand());
    SelfToggle(&self.player, &selfAi);
    CHECK(Classify(SampleFacts(TOKEN, &self.player)) == Identity::SelfBot);
    CHECK(TickLikePlayerbots(&self.player) == 1);
    // Disarm: "self" again deletes GET_PLAYERBOT_AI(master) (L1104).
    SelfToggle(&self.player, &selfAi);
    CHECK(Classify(SampleFacts(TOKEN, &self.player)) == Identity::Human);
    CHECK(TickLikePlayerbots(&self.player) == 0);

    // (d) Socket drop and contradictions fail closed.
    SelfToggle(&self.player, &selfAi);               // armed again
    sPlayerbotAIConfig.Enabled = false;              // reload with Enabled = 0
    self.session.socketClosed = true;                // masked SelfBot, client gone
    CHECK(Classify(SampleFacts(TOKEN, &self.player)) == Identity::Unknown);
    CHECK(HideTbcRow(B, RACE_DRAENEI, false, Classify(SampleFacts(TOKEN, &self.player))));
    sPlayerbotAIConfig.Enabled = true;               // linkdead SelfBot, enabled
    CHECK(Classify(SampleFacts(TOKEN, &self.player)) == Identity::Unknown);
    Character other;
    PlayerbotAI foreign;
    foreign.master = &other.player;
    PlayerbotsMgr::instance().ais[&plain.player] = &foreign;   // socket + foreign AI
    CHECK(Classify(SampleFacts(TOKEN, &plain.player)) == Identity::Unknown);

    // (e) Snapshot path: the masked sample, published, reads back as Human.
    IdentityBoard board;
    IdentityBoard::Clock::time_point const t0{std::chrono::seconds(1)};
    board.Publish(t0, {{7, maskedSelf}});
    CHECK(board.Lookup(7, t0, std::chrono::seconds(5)) == Identity::Human);

    if (checks != EXPECTED_CHECKS)
    {
        std::printf("COUNT DRIFT: ran %d checks, expected %d\n", checks, EXPECTED_CHECKS);
        return 1;
    }
    if (failures)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: F14 P12 masked SelfBot matrix, %d checks\n", checks);
    return 0;
}
