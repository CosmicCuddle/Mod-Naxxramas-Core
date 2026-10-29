// F14 P15 (test-only): P12 (#224) and P14 (#228) composed, unwired.
//
// One pipeline, all real sources:
//   stub Players -> #202 SampleFacts (real adapter) -> Classify -> IdentityBoard
//   -> P14 seam variant of #145's real /who writer -> wire bytes
// The P12 masked-SelfBot cases drive the adapter. The P14 seam header is
// produced from the combined tree by #228's own extractor
// (tests/f14_combined_inputs.py).
//
// Each tick follows the pinned core order (P14 facts C1-C3, World.cpp at
// 8daffda): the world thread rebuilds the who rows (L1170), 8 map workers
// answer /who in parallel (L1254, MapUpdate.Threads = 8) and are joined
// (MapMgr.cpp L280), then the world thread samples and publishes the board
// (OnWorldUpdate, L1355). Replies therefore use the previous tick's board.
//
// Expected visibility is written out by hand below, not computed from
// HideTbcRow, so a policy change shows up as a failure.
//
// Build: python3 -I tests/f14_combined_inputs.py . OUT
//        g++ -std=c++20 -pthread -IOUT/seam -Isrc/Systems -Itests/f14_facts_stubs/core
//            -Itests/f14_facts_stubs/playerbots tests/f14_combined_matrix_tests.cpp
#include "PlayerIdentityFacts.cpp"
#include "WhoListingPolicy.h"
#include "WhoListingSeam.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace NaxxramasPlayerIdentity
{
    struct WorldThreadSamplingGrant
    {
        static WorldThreadSampling Token() { return WorldThreadSampling(); }
    };
}

using namespace NaxxramasPlayerIdentity;
namespace Stock = NaxxramasWhoListing;
namespace Seam = NaxxramasWhoListingSeam;

namespace
{
    constexpr int EXPECTED_CHECKS = 27;
    constexpr int MAP_THREADS = 8;             // MapUpdate.Threads = 8
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

    using Clock = IdentityBoard::Clock;
    using Bytes = std::vector<std::uint8_t>;
    WorldThreadSampling const TOKEN = WorldThreadSamplingGrant::Token();

    // ---- wire format and who rows (as in #228's test) ---------------------
    struct Writer
    {
        Bytes bytes;
        Writer& operator<<(std::uint32_t v)
        {
            for (int i = 0; i < 4; ++i)
                bytes.push_back(static_cast<std::uint8_t>(v >> (8 * i)));
            return *this;
        }
        Writer& operator<<(std::uint8_t v) { bytes.push_back(v); return *this; }
        Writer& operator<<(std::string const& s)
        {
            bytes.insert(bytes.end(), s.begin(), s.end());
            bytes.push_back(0);
            return *this;
        }
        void put(std::size_t pos, std::uint32_t v)
        {
            for (int i = 0; i < 4; ++i)
                bytes.at(pos + i) = static_cast<std::uint8_t>(v >> (8 * i));
        }
    };

    struct Text
    {
        static bool FitTo(std::string const& s, std::wstring const& search)
        {
            return std::wstring(s.begin(), s.end()).find(search) != std::wstring::npos;
        }
    };

    struct Row
    {
        std::uint64_t guid;
        std::uint8_t race;
        std::string name;
        std::wstring wname;
        std::string guild;
        std::wstring wguild;

        std::uint64_t GetGuid() const { return guid; }
        int GetTeamId() const { return 0; }
        int GetSecurity() const { return 0; }
        std::uint8_t GetLevel() const { return 60; }
        std::uint8_t GetClass() const { return 1; }
        std::uint8_t GetRace() const { return race; }
        std::uint32_t GetZoneId() const { return 1; }
        std::uint8_t GetGender() const { return 0; }
        bool IsVisible() const { return true; }
        std::wstring const& GetWidePlayerName() const { return wname; }
        std::wstring const& GetWideGuildName() const { return wguild; }
        std::string const& GetPlayerName() const { return name; }
        std::string const& GetGuildName() const { return guild; }
    };

    struct Ctx
    {
        int team = 0;
        bool canSeeOtherTeam = true;
        bool canSeeAllSecLevels = false;
        int gmLevelInWhoList = 0;
        std::uint64_t observerGuid = 0;
        bool observerIsPlayerAccount = true;
        int observerSecurity = 0;
        std::uint32_t maxReturn = 50;
        std::string AreaName(std::uint32_t) const { return "zone"; }

        PolicyConfig policy{};
        IdentityBoard const* board = nullptr;
        Clock::time_point now{};
        Clock::duration maxAge = std::chrono::seconds(5);

        bool HideRowFor(std::uint8_t race, bool rowIsObserver, std::uint64_t guid) const
        {
            Identity const identity = board
                ? board->Lookup(static_cast<std::uint32_t>(guid), now, maxAge)
                : Identity::Unknown;
            return HideTbcRow(policy, race, rowIsObserver, identity);
        }
    };

    // ---- the population ---------------------------------------------------
    constexpr std::uint8_t ELF = Stock::RACE_BLOODELF, DRAENEI = Stock::RACE_DRAENEI, ORC = 2;
    enum : std::uint64_t { SELF = 101, HUMAN = 102, RANDOM = 103, ALT = 104, LINKDEAD = 105,
                           ORCBOT = 106, OBSERVER = 107 };

    struct Character
    {
        std::uint64_t guid;
        std::uint8_t race;
        std::string name;
        bool sampled = true;               // false: logged in after the last sample
        WorldSession session;
        Player player;
        PlayerbotAI ai;
    };

    std::vector<Character> MakePopulation()
    {
        std::vector<Character> c(7);
        auto set = [&](std::size_t i, std::uint64_t g, std::uint8_t r, char const* n) {
            c[i].guid = g;
            c[i].race = r;
            c[i].name = n;
        };
        set(0, SELF, ELF, "selfelf");
        set(1, HUMAN, DRAENEI, "humandraenei");
        set(2, RANDOM, ELF, "randomelf");
        set(3, ALT, DRAENEI, "altdraenei");
        set(4, LINKDEAD, ELF, "linkdeadelf");
        set(5, ORCBOT, ORC, "orcbot");
        set(6, OBSERVER, ELF, "observerelf");
        c[6].sampled = false;
        return c;
    }

    // Wire up pointers once the vector no longer moves.
    void Attach(std::vector<Character>& c)
    {
        auto& ais = PlayerbotsMgr::instance().ais;
        auto& random = RandomPlayerbotMgr::instance().current;
        ais.clear();
        random.clear();
        for (Character& ch : c)
        {
            ch.player.inWorld = true;
            ch.player.session = &ch.session;
        }
        auto client = [](Character& ch) { ch.session.socketClosed = false; };
        client(c[0]);                                          // SelfBot: client + own AI
        c[0].ai.master = &c[0].player;
        ais[&c[0].player] = &c[0].ai;
        client(c[1]);                                          // ordinary human
        c[2].ai.master = nullptr;                              // RandomBot: no client
        ais[&c[2].player] = &c[2].ai;
        random.insert(&c[2].player);
        c[3].ai.master = &c[1].player;                         // AltBot of the human
        ais[&c[3].player] = &c[3].ai;
        // c[4]: human whose client dropped (no AI): linkdead
        c[5].ai.master = nullptr;                              // non-TBC RandomBot
        ais[&c[5].player] = &c[5].ai;
        random.insert(&c[5].player);
        client(c[6]);                                          // the observer, a human
    }

    // ---- one world tick ---------------------------------------------------
    std::vector<Row> BuildWhoRows(std::vector<Character> const& c)
    {
        std::vector<Row> rows;
        for (Character const& ch : c)
            rows.push_back(Row{ch.guid, ch.race, ch.name, std::wstring(ch.name.begin(), ch.name.end()), "", L""});
        return rows;
    }

    void PublishBoard(IdentityBoard& board, std::vector<Character>& c, Clock::time_point at)
    {
        std::vector<std::pair<std::uint32_t, Facts>> rows;
        for (Character& ch : c)
            if (ch.sampled)
                rows.emplace_back(static_cast<std::uint32_t>(ch.guid), SampleFacts(TOKEN, &ch.player));
        board.Publish(at, rows);
    }

    std::vector<std::wstring> const QUERIES = {L"", L"selfelf", L"humandraenei", L"randomelf", L"altdraenei",
                                               L"linkdeadelf", L"orcbot", L"observerelf"};

    struct Replies
    {
        std::vector<Bytes> stock, stockHidden, seamOff, seamA, seamB, seamBSelf;
    };

    Seam::WhoRequest SeamRequest(std::wstring const& name)
    {
        Seam::WhoRequest r;
        r.levelMax = 80;
        r.racemask = r.classmask = 0xFFFFFFFFu;
        r.playerName = name;
        return r;
    }

    Stock::WhoRequest StockRequest(std::wstring const& name)
    {
        Stock::WhoRequest r;
        r.levelMax = 80;
        r.racemask = r.classmask = 0xFFFFFFFFu;
        r.playerName = name;
        return r;
    }

    // A map worker: answers every query under every policy. It reads only
    // the who rows and the board; it never touches a Player.
    Replies AnswerAll(std::vector<Row> const& rows, IdentityBoard const& board, Clock::time_point now)
    {
        Replies out;
        Ctx ctx;
        ctx.observerGuid = OBSERVER;
        ctx.board = &board;
        ctx.now = now;
        for (std::wstring const& q : QUERIES)
        {
            auto stock = [&](bool hide) {
                Writer w;
                Stock::WriteWhoReply<Text>(StockRequest(q), rows, ctx, hide, w);
                return w.bytes;
            };
            auto seam = [&](PolicyConfig policy, bool hide) {
                Ctx c = ctx;
                c.policy = policy;
                Writer w;
                Seam::WriteWhoReply<Text>(SeamRequest(q), rows, c, hide, w);
                return w.bytes;
            };
            out.stock.push_back(stock(false));
            out.stockHidden.push_back(stock(true));
            out.seamOff.push_back(seam({Policy::HideBotsOnly, false}, false));
            out.seamA.push_back(seam({Policy::HideAllTbcRaces, false}, true));
            out.seamB.push_back(seam({Policy::HideBotsOnly, false}, true));
            out.seamBSelf.push_back(seam({Policy::HideBotsOnly, true}, true));
        }
        return out;
    }

    struct TickResult
    {
        std::vector<Row> rows;
        std::vector<Replies> perWorker;
    };

    // publish == false models a world thread that did not reach
    // OnWorldUpdate (a stall): the board keeps its old snapshot.
    TickResult Tick(std::vector<Character>& c, IdentityBoard& board, Clock::time_point now, bool publish)
    {
        TickResult t;
        t.perWorker.resize(MAP_THREADS);
        std::vector<Row> rows;
        rows = BuildWhoRows(c);                                   // W1: world thread, L1170
        std::vector<std::thread> workers;
        for (int w = 0; w < MAP_THREADS; ++w)                     // M: map workers, L1254
            workers.emplace_back([&, w] { t.perWorker[static_cast<std::size_t>(w)] = AnswerAll(rows, board, now); });
        for (auto& th : workers) th.join();                       // MapMgr.cpp L280
        if (publish)
            PublishBoard(board, c, now);                          // W2: OnWorldUpdate, L1355
        t.rows = rows;
        return t;
    }

    // ---- hand-written oracle ----------------------------------------------
    Bytes ExpectedReply(std::vector<Row> const& rows, std::wstring const& q, std::set<std::uint64_t> const& shown)
    {
        std::vector<Row> kept;
        for (Row const& r : rows)
            if (shown.count(r.guid))
                kept.push_back(r);
        Ctx ctx;
        ctx.observerGuid = OBSERVER;
        Writer w;
        Stock::WriteWhoReply<Text>(StockRequest(q), kept, ctx, false, w);
        return w.bytes;
    }

    bool AllWorkersAgree(TickResult const& t)
    {
        for (Replies const& r : t.perWorker)
            if (r.seamB != t.perWorker[0].seamB || r.seamA != t.perWorker[0].seamA ||
                r.seamBSelf != t.perWorker[0].seamBSelf || r.stock != t.perWorker[0].stock)
                return false;
        return true;
    }

    // Every query, every worker: the chosen reply equals the oracle.
    template <typename Pick>
    bool Matches(TickResult const& t, Pick pick, std::set<std::uint64_t> const& shown)
    {
        for (Replies const& r : t.perWorker)
            for (std::size_t q = 0; q < QUERIES.size(); ++q)
                if (pick(r)[q] != ExpectedReply(t.rows, QUERIES[q], shown))
                    return false;
        return true;
    }

    // Policy A through the seam == #145 as shipped; hiding off == stock.
    bool ShippedParity(TickResult const& t)
    {
        for (Replies const& r : t.perWorker)
            if (r.seamA != r.stockHidden || r.seamOff != r.stock)
                return false;
        return true;
    }

    bool BEqualsA(TickResult const& t)
    {
        for (Replies const& r : t.perWorker)
            if (r.seamB != r.stockHidden || r.seamBSelf != r.stockHidden)
                return false;
        return true;
    }

    bool SameFacts(Facts const& a, Facts const& b)
    {
        return a.inWorld == b.inWorld && a.hasSession == b.hasSession && a.socketOpen == b.socketOpen &&
               a.playerbotsEnabled == b.playerbotsEnabled && a.botAiAttached == b.botAiAttached &&
               a.botMasterIsSelf == b.botMasterIsSelf && a.randomBotListed == b.randomBotListed;
    }

    auto const B = [](Replies const& r) -> std::vector<Bytes> const& { return r.seamB; };
    auto const BSELF = [](Replies const& r) -> std::vector<Bytes> const& { return r.seamBSelf; };
    auto const A = [](Replies const& r) -> std::vector<Bytes> const& { return r.seamA; };
}

int main()
{
    std::vector<Character> c = MakePopulation();
    Attach(c);
    sPlayerbotAIConfig.Enabled = true;
    IdentityBoard board;
    Clock::time_point const t0{std::chrono::seconds(1000)};
    auto const tick = std::chrono::seconds(1);

    // Policy A and the observer's own row never depend on identity.
    std::set<std::uint64_t> const shownA{ORCBOT, OBSERVER};
    // Playerbots enabled: only the human's TBC row (and the observer's).
    std::set<std::uint64_t> const shownB{HUMAN, ORCBOT, OBSERVER};
    std::set<std::uint64_t> const shownBSelf{SELF, HUMAN, ORCBOT, OBSERVER};
    // Playerbots masked (P12): the SelfBot now reads as Human and is shown;
    // bots without a client become Unknown and stay hidden.
    std::set<std::uint64_t> const shownMasked{SELF, HUMAN, ORCBOT, OBSERVER};

    // T0: no board yet -> policy B behaves exactly like policy A.
    TickResult const r0 = Tick(c, board, t0, true);
    CHECK(AllWorkersAgree(r0));
    CHECK(ShippedParity(r0));
    CHECK(BEqualsA(r0));
    CHECK(Matches(r0, A, shownA));

    // T1: board from T0 (enabled).
    TickResult const r1 = Tick(c, board, t0 + tick, true);
    CHECK(AllWorkersAgree(r1));
    CHECK(ShippedParity(r1));
    CHECK(Matches(r1, B, shownB));
    CHECK(Matches(r1, BSELF, shownBSelf));
    CHECK(Matches(r1, A, shownA));
    CHECK(board.Lookup(SELF, t0 + tick, std::chrono::seconds(5)) == Identity::SelfBot);
    CHECK(board.Lookup(OBSERVER, t0 + tick, std::chrono::seconds(5)) == Identity::Unknown);

    // A reload sets Playerbots.Enabled = 0 between ticks (P12 masking).
    sPlayerbotAIConfig.Enabled = false;
    Facts const maskedSelf = SampleFacts(TOKEN, &c[0].player);
    Facts const maskedHuman = SampleFacts(TOKEN, &c[1].player);
    CHECK(SameFacts(maskedSelf, maskedHuman));              // P12: indistinguishable
    CHECK(Classify(maskedSelf) == Identity::Human);

    // T2: replies still use T1's (enabled) board: one tick of lag.
    TickResult const r2 = Tick(c, board, t0 + 2 * tick, true);
    CHECK(Matches(r2, B, shownB));
    CHECK(ShippedParity(r2));

    // T3: board from T2 (masked).
    Clock::time_point const t3 = t0 + 3 * tick;
    TickResult const r3 = Tick(c, board, t3, true);
    CHECK(AllWorkersAgree(r3));
    CHECK(ShippedParity(r3));
    CHECK(Matches(r3, B, shownMasked));
    CHECK(Matches(r3, BSELF, shownMasked));
    CHECK(Matches(r3, A, shownA));
    CHECK(board.Lookup(SELF, t3, std::chrono::seconds(5)) == Identity::Human);
    CHECK(board.Lookup(RANDOM, t3, std::chrono::seconds(5)) == Identity::Unknown);
    CHECK(board.Lookup(LINKDEAD, t3, std::chrono::seconds(5)) == Identity::Unknown);

    // T4: the world thread stalls past maxAge without publishing -> stale
    // board -> policy A.
    TickResult const r4 = Tick(c, board, t3 + std::chrono::seconds(5) + std::chrono::nanoseconds(1), false);
    CHECK(BEqualsA(r4));
    CHECK(ShippedParity(r4));

    // T5: a clock that reads earlier than the last sample -> future board
    // -> policy A.
    TickResult const r5 = Tick(c, board, t3 - std::chrono::nanoseconds(1), false);
    CHECK(BEqualsA(r5));

    // T6: back within maxAge of the T3 sample: trusted again.
    TickResult const r6 = Tick(c, board, t3 + std::chrono::seconds(5), false);
    CHECK(Matches(r6, B, shownMasked));

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
    std::printf("PASS: F14 P15 combined P12+P14 matrix, %d checks, %d map workers\n", checks, MAP_THREADS);
    return 0;
}
