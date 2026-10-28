// F14 P14 (test-only): how #202's identity board would meet #145's /who
// writer, without wiring either.
//
// WhoListingPolicy.h is #145's real header (01c6b32, blob e66f72c) and
// WhoListingSeam.h is the same header with its one HideRow call routed
// through ctx.HideRowFor; tests/f14_visibility_seam_extract.py makes both and
// fails on any drift. PlayerIdentityPolicy.h (Classify, HideTbcRow,
// IdentityBoard) is #202's real header.
//
// Build: python3 -I tests/f14_visibility_seam_extract.py . OUT
//        g++ -std=c++20 -IOUT -Isrc/Systems tests/f14_visibility_seam_tests.cpp
#include "PlayerIdentityPolicy.h"
#include "WhoListingPolicy.h"
#include "WhoListingSeam.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <map>
#include <random>
#include <string>
#include <utility>
#include <vector>

using namespace NaxxramasPlayerIdentity;
namespace Stock = NaxxramasWhoListing;
namespace Seam = NaxxramasWhoListingSeam;

namespace
{
    constexpr int EXPECTED_CHECKS = 23;
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
    constexpr int CASES = 2000;

    // ByteBuffer wire format, as in #145's tests.
    struct Writer
    {
        std::vector<std::uint8_t> bytes;
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

    // A who-cache row (WhoListCacheMgr.h L25-L72 at 8daffda): the GUID is
    // the player's; the board is keyed by its low part (GetCounter).
    struct Row
    {
        std::uint64_t guid;
        int team, security;
        std::uint8_t level, cls, race;
        std::uint32_t zone;
        std::uint8_t gender;
        bool visible;
        std::string name, guild;
        std::wstring wname, wguild;

        std::uint64_t GetGuid() const { return guid; }
        int GetTeamId() const { return team; }
        int GetSecurity() const { return security; }
        std::uint8_t GetLevel() const { return level; }
        std::uint8_t GetClass() const { return cls; }
        std::uint8_t GetRace() const { return race; }
        std::uint32_t GetZoneId() const { return zone; }
        std::uint8_t GetGender() const { return gender; }
        bool IsVisible() const { return visible; }
        std::wstring const& GetWidePlayerName() const { return wname; }
        std::wstring const& GetWideGuildName() const { return wguild; }
        std::string const& GetPlayerName() const { return name; }
        std::string const& GetGuildName() const { return guild; }
    };

    // Observer context. The stock writer reads only the first block; the
    // seam also calls HideRowFor, which is the whole proposed integration.
    struct Ctx
    {
        int team = 0;
        bool canSeeOtherTeam = false;
        bool canSeeAllSecLevels = false;
        int gmLevelInWhoList = 0;
        std::uint64_t observerGuid = 0;
        bool observerIsPlayerAccount = true;
        int observerSecurity = 0;
        std::uint32_t maxReturn = 50;
        std::string AreaName(std::uint32_t zone) const { return "zone" + std::to_string(zone); }

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

    Facts FactsFor(Identity id)
    {
        Facts f;
        f.inWorld = f.hasSession = true;
        f.playerbotsEnabled = true;
        switch (id)
        {
            case Identity::Human: f.socketOpen = true; break;
            case Identity::SelfBot: f.socketOpen = f.botAiAttached = f.botMasterIsSelf = true; break;
            case Identity::RandomBot: f.botAiAttached = f.randomBotListed = true; break;
            case Identity::AltBot: f.botAiAttached = true; break;
            case Identity::Unknown: f.inWorld = false; break;
        }
        return f;
    }

    struct Case
    {
        std::vector<Row> rows;
        std::map<std::uint64_t, Identity> identity;   // absent: not on the board
        Stock::WhoRequest req;
        Ctx ctx;
    };

    Case MakeCase(std::mt19937& rng)
    {
        auto pick = [&](int n) { return static_cast<int>(rng() % static_cast<unsigned>(n)); };
        Case c;
        int const n = 1 + pick(40);
        for (int i = 0; i < n; ++i)
        {
            Row r{};
            r.guid = (std::uint64_t(pick(2)) << 48) | std::uint64_t(100 + i);  // high bits vary
            r.team = pick(2);
            r.security = pick(5) == 0 ? pick(4) : 0;
            r.level = static_cast<std::uint8_t>(1 + pick(80));
            r.cls = static_cast<std::uint8_t>(1 + pick(11));
            r.race = static_cast<std::uint8_t>(pick(3) == 0 ? 10 + pick(2) : 1 + pick(11));
            r.zone = static_cast<std::uint32_t>(pick(6));
            r.gender = static_cast<std::uint8_t>(pick(2));
            r.visible = pick(10) != 0;
            r.name = "p" + std::to_string(i);
            r.guild = pick(3) ? "" : "g" + std::to_string(pick(3));
            r.wname.assign(r.name.begin(), r.name.end());
            r.wguild.assign(r.guild.begin(), r.guild.end());
            if (pick(8) != 0)                         // most rows are on the board
                c.identity[r.guid] = static_cast<Identity>(pick(5));
            c.rows.push_back(r);
        }

        c.req.levelMin = static_cast<std::uint32_t>(pick(3) ? 0 : pick(40));
        c.req.levelMax = static_cast<std::uint32_t>(pick(3) ? 80 : 40 + pick(41));
        c.req.racemask = pick(4) ? 0xFFFFFFFFu : static_cast<std::uint32_t>(rng());
        c.req.classmask = pick(4) ? 0xFFFFFFFFu : static_cast<std::uint32_t>(rng());
        c.req.zonesCount = static_cast<std::uint32_t>(pick(4) ? 0 : 1 + pick(3));
        for (std::uint32_t z = 0; z < c.req.zonesCount; ++z)
            c.req.zoneids[z] = static_cast<std::uint32_t>(pick(6));
        if (pick(6) == 0)
            c.req.playerName = L"p" + std::to_wstring(pick(10));

        c.ctx.team = pick(2);
        c.ctx.canSeeOtherTeam = pick(2);
        c.ctx.canSeeAllSecLevels = pick(4) == 0;
        c.ctx.gmLevelInWhoList = pick(4);
        c.ctx.observerGuid = pick(3) ? c.rows[static_cast<std::size_t>(pick(n))].guid : 1;
        c.ctx.observerIsPlayerAccount = pick(4) != 0;
        c.ctx.observerSecurity = pick(4);
        c.ctx.maxReturn = static_cast<std::uint32_t>(1 + pick(60));
        return c;
    }

    void Publish(IdentityBoard& board, Case const& c, Clock::time_point at)
    {
        std::vector<std::pair<std::uint32_t, Facts>> rows;
        for (auto const& [guid, id] : c.identity)
            rows.emplace_back(static_cast<std::uint32_t>(guid), FactsFor(id));
        board.Publish(at, rows);
    }

    template <typename Fn>
    std::vector<std::uint8_t> Reply(Fn&& write)
    {
        Writer w;
        write(w);
        return w.bytes;
    }

    std::vector<std::uint8_t> StockReply(Case const& c, std::vector<Row> const& rows, bool hide)
    {
        return Reply([&](Writer& w) { Stock::WriteWhoReply<Text>(c.req, rows, c.ctx, hide, w); });
    }

    // Same struct, separate namespace: copy every field.
    Seam::WhoRequest ToSeam(Stock::WhoRequest const& r)
    {
        Seam::WhoRequest s;
        s.levelMin = r.levelMin;
        s.levelMax = r.levelMax;
        s.racemask = r.racemask;
        s.classmask = r.classmask;
        s.zonesCount = r.zonesCount;
        s.strCount = r.strCount;
        s.zoneids = r.zoneids;
        for (std::uint32_t i = 0; i < Stock::MAX_STRINGS; ++i)
            s.str[i] = r.str[i];
        s.playerName = r.playerName;
        s.guildName = r.guildName;
        return s;
    }

    std::vector<std::uint8_t> SeamReply(Case const& c, Ctx const& ctx, bool hide)
    {
        Seam::WhoRequest const req = ToSeam(c.req);
        return Reply([&](Writer& w) { Seam::WriteWhoReply<Text>(req, c.rows, ctx, hide, w); });
    }

    // Oracle for policy B: stock output (no hiding) over the rows that the
    // identity rule keeps. Hidden rows are skipped before the count, so
    // removing them is equivalent.
    std::vector<Row> KeptRows(Case const& c, PolicyConfig const& policy, bool boardTrusted)
    {
        std::vector<Row> kept;
        for (Row const& r : c.rows)
        {
            auto const it = c.identity.find(r.guid);
            Identity const id = boardTrusted && it != c.identity.end() ? it->second : Identity::Unknown;
            if (!HideTbcRow(policy, r.race, r.guid == c.ctx.observerGuid, id))
                kept.push_back(r);
        }
        return kept;
    }
}

int main()
{
    PolicyConfig const A{Policy::HideAllTbcRaces, false};
    PolicyConfig const B{Policy::HideBotsOnly, false};
    PolicyConfig const B_SELF{Policy::HideBotsOnly, true};
    Identity const ALL[] = {Identity::Human, Identity::SelfBot, Identity::RandomBot,
                            Identity::AltBot, Identity::Unknown};

    // 1. #145's shipped rule is #197's policy A, for every race, observer
    //    flag and identity: wiring under A cannot change any reply.
    int ruleMismatch = 0;
    for (int race = 0; race < 256; ++race)
        for (bool self : {false, true})
            for (Identity id : ALL)
                for (bool sbh : {false, true})
                    if (Stock::HideRow(static_cast<std::uint8_t>(race), self) !=
                        HideTbcRow({Policy::HideAllTbcRaces, sbh}, static_cast<std::uint8_t>(race), self, id))
                        ++ruleMismatch;
    CHECK(ruleMismatch == 0);

    std::mt19937 rng(20261028);
    Clock::time_point const t0{std::chrono::seconds(1000)};
    int offSame = 0, aSame = 0, bSame = 0, bSelfSame = 0, staleSame = 0, futureSame = 0,
        noBoardSame = 0, edgeSame = 0, bDiffers = 0;
    for (int i = 0; i < CASES; ++i)
    {
        Case const c = MakeCase(rng);
        IdentityBoard board;
        Publish(board, c, t0);

        Ctx ctx = c.ctx;
        ctx.board = &board;
        ctx.now = t0 + std::chrono::seconds(2);

        // 2. Feature off (hide == false): seam bytes == stock bytes.
        ctx.policy = B;
        offSame += SeamReply(c, ctx, false) == StockReply(c, c.rows, false);

        // 3. Policy A through the seam == #145 as shipped, whatever the board says.
        ctx.policy = A;
        auto const shipped = StockReply(c, c.rows, true);
        aSame += SeamReply(c, ctx, true) == shipped;

        // 4. Policy B, fresh board: stock minus the rows the identity rule hides.
        ctx.policy = B;
        auto const bReply = SeamReply(c, ctx, true);
        bSame += bReply == StockReply(c, KeptRows(c, B, true), false);
        bDiffers += bReply != shipped;
        ctx.policy = B_SELF;
        bSelfSame += SeamReply(c, ctx, true) == StockReply(c, KeptRows(c, B_SELF, true), false);

        // 5. Fail closed: stale, future or missing board -> every TBC row
        //    except the observer's is hidden, i.e. exactly policy A.
        ctx.policy = B;
        ctx.now = t0 + ctx.maxAge + std::chrono::nanoseconds(1);
        staleSame += SeamReply(c, ctx, true) == shipped;
        ctx.now = t0 - std::chrono::nanoseconds(1);
        futureSame += SeamReply(c, ctx, true) == shipped;
        Ctx noBoard = ctx;
        noBoard.board = nullptr;
        noBoardSame += SeamReply(c, noBoard, true) == shipped;
        // ...and exactly at maxAge the board is still trusted.
        ctx.now = t0 + ctx.maxAge;
        edgeSame += SeamReply(c, ctx, true) == StockReply(c, KeptRows(c, B, true), false);
    }
    CHECK(offSame == CASES);
    CHECK(aSame == CASES);
    CHECK(bSame == CASES);
    CHECK(bSelfSame == CASES);
    CHECK(staleSame == CASES);
    CHECK(futureSame == CASES);
    CHECK(noBoardSame == CASES);
    CHECK(edgeSame == CASES);
    CHECK(bDiffers > CASES / 10);              // the generator really exercises B

    // 6. Named rows, policy B, fresh board.
    Case named;
    named.req.levelMax = 80;
    named.req.racemask = named.req.classmask = 0xFFFFFFFFu;
    named.ctx.observerGuid = 1;
    auto add = [&](std::uint64_t guid, std::uint8_t race, std::string const& name, Identity id) {
        Row r{};
        r.guid = guid;
        r.level = 60;
        r.cls = 1;
        r.race = race;
        r.visible = true;
        r.name = name;
        r.wname.assign(name.begin(), name.end());
        named.rows.push_back(r);
        named.identity[guid] = id;
    };
    add(201, Stock::RACE_BLOODELF, "humanelf", Identity::Human);
    add(202, Stock::RACE_DRAENEI, "selfdraenei", Identity::SelfBot);
    add(203, Stock::RACE_BLOODELF, "randomelf", Identity::RandomBot);
    add(204, Stock::RACE_DRAENEI, "altdraenei", Identity::AltBot);
    add(205, 1, "humanhuman", Identity::RandomBot);         // non-TBC bot: never hidden
    IdentityBoard board;
    Publish(board, named, t0);
    Ctx ctx = named.ctx;
    ctx.board = &board;
    ctx.now = t0;
    ctx.policy = B;
    auto counts = [&](std::wstring const& name, Ctx const& cx) {
        Case q = named;
        q.req.playerName = name;
        auto const bytes = SeamReply(q, cx, true);
        std::uint32_t const shown = bytes[0] | bytes[1] << 8 | bytes[2] << 16 | std::uint32_t(bytes[3]) << 24;
        std::uint32_t const matched = bytes[4] | bytes[5] << 8 | bytes[6] << 16 | std::uint32_t(bytes[7]) << 24;
        return std::make_pair(shown, matched);
    };
    CHECK(counts(L"humanelf", ctx) == std::make_pair(1u, 1u));
    CHECK(counts(L"selfdraenei", ctx) == std::make_pair(0u, 0u));  // hidden-only query: 0/0
    CHECK(counts(L"randomelf", ctx) == std::make_pair(0u, 0u));
    CHECK(counts(L"altdraenei", ctx) == std::make_pair(0u, 0u));
    CHECK(counts(L"humanhuman", ctx) == std::make_pair(1u, 1u));
    CHECK(counts(L"", ctx) == std::make_pair(2u, 2u));
    ctx.policy = B_SELF;
    CHECK(counts(L"selfdraenei", ctx) == std::make_pair(1u, 1u));
    CHECK(counts(L"", ctx) == std::make_pair(3u, 3u));

    // 7. The board is keyed by GUID low part: a different high part with the
    //    same counter reads the same entry, a different counter does not.
    ctx.policy = B;
    CHECK(!ctx.HideRowFor(Stock::RACE_BLOODELF, false, (std::uint64_t(7) << 48) | 201));
    CHECK(ctx.HideRowFor(Stock::RACE_BLOODELF, false, 299));
    // The observer's own TBC row is kept even when it is unknown.
    CHECK(!ctx.HideRowFor(Stock::RACE_DRAENEI, true, 299));

    // 8. An over-full snapshot is invalid, so policy B falls back to A.
    std::vector<std::pair<std::uint32_t, Facts>> tooMany;
    for (std::uint32_t g = 1; g <= IdentityBoard::MAX_ENTRIES + 1; ++g)
        tooMany.emplace_back(g, FactsFor(Identity::Human));
    board.Publish(t0, tooMany);
    CHECK(ctx.HideRowFor(Stock::RACE_BLOODELF, false, 201));
    CHECK(counts(L"", ctx) == std::make_pair(1u, 1u));      // only the non-TBC row

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
    std::printf("PASS: F14 P14 /who identity seam, %d checks, %d random cases\n", checks, CASES);
    return 0;
}
