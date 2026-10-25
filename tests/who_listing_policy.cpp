// Native tests for src/Systems/WhoListingPolicy.h (F14 S2).
//
// StockWho below is a transcription of WorldSession::HandleWhoOpcode at
// Grimfeather 8daffda (MiscHandler.cpp L220-L414) with only the session,
// world and DBC reads replaced by the test context. The fingerprint script
// fails CI when that core function changes, so this transcription and the
// module mirror must then be re-reviewed together.
//
// Wire bytes are compared, not just counts: with hiding off, the mirror must
// produce exactly the stock reply (or exactly no reply) for every request.
#include "WhoListingPolicy.h"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <map>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

using namespace NaxxramasWhoListing;

namespace
{
    constexpr std::uint32_t MAX_LEVEL = 80;
    constexpr std::uint32_t STRONG_MAX_LEVEL = 255;

    // ---- byte buffers with the ByteBuffer wire format --------------------
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

    struct ShortPacket : std::runtime_error
    {
        ShortPacket() : std::runtime_error("short packet") { }
    };

    struct Reader
    {
        std::vector<std::uint8_t> const& bytes;
        std::size_t pos = 0;
        Reader& operator>>(std::uint32_t& v)
        {
            if (pos + 4 > bytes.size())
                throw ShortPacket();
            v = 0;
            for (int i = 0; i < 4; ++i)
                v |= std::uint32_t(bytes[pos + i]) << (8 * i);
            pos += 4;
            return *this;
        }
        Reader& operator>>(std::string& s)
        {
            s.clear();
            while (true)
            {
                if (pos >= bytes.size())
                    throw ShortPacket();
                char c = static_cast<char>(bytes[pos++]);
                if (c == 0)
                    break;
                s += c;
            }
            return *this;
        }
    };

    // ---- text helpers standing in for core Util.h -------------------------
    // Byte 0xFF is treated as invalid UTF-8, like a failed Utf8toWStr
    // (which clears the output). Lowercasing is ASCII.
    struct TestText
    {
        static bool ToWide(std::string const& s, std::wstring& w)
        {
            w.clear();
            for (unsigned char c : s)
            {
                if (c == 0xFF)
                {
                    w.clear();
                    return false;
                }
                w += static_cast<wchar_t>(c);
            }
            return true;
        }
        static void Lower(std::wstring& w)
        {
            for (auto& c : w)
                if (c >= L'A' && c <= L'Z')
                    c = c - L'A' + L'a';
        }
        static bool FitTo(std::string const& s, std::wstring const& search)
        {
            std::wstring w;
            if (!ToWide(s, w))
                return false;
            Lower(w);
            return w.find(search) != std::wstring::npos;
        }
    };

    // ---- who-cache row and observer context ------------------------------
    struct Row
    {
        std::uint64_t guid;
        int team;
        int security;
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

    Row MakeRow(std::uint64_t guid, int team, std::uint8_t race, std::string name, std::string guild = "",
                std::uint8_t level = 60, std::uint8_t cls = 1, std::uint32_t zone = 1)
    {
        Row r{ guid, team, 0, level, cls, race, zone, 0, true, name, guild, {}, {} };
        TestText::ToWide(name, r.wname);
        TestText::Lower(r.wname);
        TestText::ToWide(guild, r.wguild);
        TestText::Lower(r.wguild);
        return r;
    }

    struct Ctx
    {
        int team = 0;
        bool canSeeOtherTeam = false;
        bool canSeeAllSecLevels = false;
        int gmLevelInWhoList = 0;
        std::uint64_t observerGuid = 1;
        bool observerIsPlayerAccount = true;
        int observerSecurity = 0;
        std::uint32_t maxReturn = 49;
        std::map<std::uint32_t, std::string> areas;

        std::string AreaName(std::uint32_t zone) const
        {
            auto it = areas.find(zone);
            return it == areas.end() ? std::string() : it->second;
        }
    };

    // ---- stock transcription (MiscHandler.cpp L220-L414 at 8daffda) ------
    std::optional<std::vector<std::uint8_t>> StockWho(std::vector<std::uint8_t> const& in,
                                                       std::vector<Row> const& whoList, Ctx const& c)
    {
        Reader recvData{ in };
        std::uint32_t matchCount = 0;

        std::uint32_t levelMin, levelMax, racemask, classmask, zonesCount, strCount;
        std::array<std::uint32_t, 10> zoneids = {};
        std::string packetPlayerName, packetGuildName;

        recvData >> levelMin;
        recvData >> levelMax;
        recvData >> packetPlayerName;
        recvData >> packetGuildName;
        recvData >> racemask;
        recvData >> classmask;
        recvData >> zonesCount;

        if (zonesCount > 10)
            return std::nullopt;

        for (std::uint32_t i = 0; i < zonesCount; ++i)
        {
            std::uint32_t temp;
            recvData >> temp;
            zoneids[i] = temp;
        }

        recvData >> strCount;

        if (strCount > 4)
            return std::nullopt;

        std::wstring str[4];
        for (std::uint32_t i = 0; i < strCount; ++i)
        {
            std::string temp;
            recvData >> temp;

            if (!TestText::ToWide(temp, str[i]))
                continue;

            TestText::Lower(str[i]);
        }

        std::wstring wpacketPlayerName;
        std::wstring wpacketGuildName;
        if (!(TestText::ToWide(packetPlayerName, wpacketPlayerName) && TestText::ToWide(packetGuildName, wpacketGuildName)))
            return std::nullopt;

        TestText::Lower(wpacketPlayerName);
        TestText::Lower(wpacketGuildName);

        if (levelMax >= MAX_LEVEL)
            levelMax = STRONG_MAX_LEVEL;

        int team = c.team;
        int gmLevelInWhoList = c.gmLevelInWhoList;
        std::uint32_t displaycount = 0;

        Writer data;
        data << std::uint32_t(matchCount);
        data << std::uint32_t(displaycount);

        for (auto const& target : whoList)
        {
            if (target.GetTeamId() != team && !c.canSeeOtherTeam)
                continue;

            if (!c.canSeeAllSecLevels && target.GetSecurity() > gmLevelInWhoList)
                continue;

            if ((c.observerGuid != target.GetGuid() && !target.IsVisible()) &&
                (c.observerIsPlayerAccount || target.GetSecurity() > c.observerSecurity))
            {
                continue;
            }

            std::uint8_t lvl = target.GetLevel();
            if (lvl < levelMin || lvl > levelMax)
                continue;

            std::uint8_t class_ = target.GetClass();
            if (!(classmask & (1 << class_)))
                continue;

            std::uint32_t race = target.GetRace();
            if (!(racemask & (1 << race)))
                continue;

            std::uint32_t playerZoneId = target.GetZoneId();
            std::uint8_t gender = target.GetGender();

            bool showZones = true;
            for (std::uint32_t i = 0; i < zonesCount; ++i)
            {
                if (zoneids[i] == playerZoneId)
                {
                    showZones = true;
                    break;
                }

                showZones = false;
            }

            if (!showZones)
                continue;

            std::wstring const& wideplayername = target.GetWidePlayerName();
            if (!(wpacketPlayerName.empty() || wideplayername.find(wpacketPlayerName) != std::wstring::npos))
                continue;

            std::wstring const& wideguildname = target.GetWideGuildName();
            if (!(wpacketGuildName.empty() || wideguildname.find(wpacketGuildName) != std::wstring::npos))
                continue;

            std::string aname = c.AreaName(playerZoneId);

            bool s_show = true;
            for (std::uint32_t i = 0; i < strCount; ++i)
            {
                if (!str[i].empty())
                {
                    if (wideguildname.find(str[i]) != std::wstring::npos ||
                        wideplayername.find(str[i]) != std::wstring::npos ||
                        TestText::FitTo(aname, str[i]))
                    {
                        s_show = true;
                        break;
                    }

                    s_show = false;
                }
            }

            if (!s_show)
                continue;

            if ((matchCount++) >= c.maxReturn)
                continue;

            data << target.GetPlayerName();
            data << target.GetGuildName();
            data << std::uint32_t(lvl);
            data << std::uint32_t(class_);
            data << std::uint32_t(race);
            data << std::uint8_t(gender);
            data << std::uint32_t(playerZoneId);

            ++displaycount;
        }

        data.put(0, displaycount);
        data.put(4, matchCount);
        return data.bytes;
    }

    // ---- the module mirror, as the module calls it ------------------------
    std::optional<std::vector<std::uint8_t>> MirrorWho(std::vector<std::uint8_t> const& in,
                                                        std::vector<Row> const& rows, Ctx const& c, bool hide)
    {
        Reader reader{ in };
        WhoRequest req;
        if (!ReadWhoRequest<TestText>(reader, req, MAX_LEVEL, STRONG_MAX_LEVEL))
            return std::nullopt;
        Writer out;
        WriteWhoReply<TestText>(req, rows, c, hide, out);
        return out.bytes;
    }

    // ---- request builder ---------------------------------------------------
    struct Query
    {
        std::uint32_t levelMin = 0, levelMax = 100;
        std::string name, guild;
        std::uint32_t racemask = 0xFFFFFFFF, classmask = 0xFFFFFFFF;
        std::vector<std::uint32_t> zones;
        std::vector<std::string> strs;
        std::uint32_t zonesCountOverride = 0xFFFFFFFF;
        std::uint32_t strCountOverride = 0xFFFFFFFF;
        std::size_t truncate = 0;
    };

    std::vector<std::uint8_t> Encode(Query const& q)
    {
        Writer w;
        w << q.levelMin << q.levelMax << q.name << q.guild << q.racemask << q.classmask;
        w << (q.zonesCountOverride != 0xFFFFFFFF ? q.zonesCountOverride : std::uint32_t(q.zones.size()));
        for (auto z : q.zones)
            w << z;
        w << (q.strCountOverride != 0xFFFFFFFF ? q.strCountOverride : std::uint32_t(q.strs.size()));
        for (auto const& s : q.strs)
            w << s;
        if (q.truncate && q.truncate < w.bytes.size())
            w.bytes.resize(w.bytes.size() - q.truncate);
        return w.bytes;
    }

    std::uint32_t U32(std::vector<std::uint8_t> const& b, std::size_t pos)
    {
        std::uint32_t v = 0;
        for (int i = 0; i < 4; ++i)
            v |= std::uint32_t(b.at(pos + i)) << (8 * i);
        return v;
    }

    // Decoded reply rows (name, race) for assertions.
    std::vector<std::pair<std::string, std::uint32_t>> Decode(std::vector<std::uint8_t> const& b)
    {
        std::vector<std::pair<std::string, std::uint32_t>> out;
        Reader r{ b };
        std::uint32_t display, match;
        r >> display >> match;
        for (std::uint32_t i = 0; i < display; ++i)
        {
            std::string name, guild;
            std::uint32_t lvl, cls, race, zone;
            r >> name >> guild >> lvl >> cls >> race;
            r.pos += 1; // gender
            r >> zone;
            out.emplace_back(name, race);
        }
        assert(r.pos == b.size());
        return out;
    }

    int failures = 0;
    void Check(bool ok, char const* what)
    {
        if (!ok)
        {
            ++failures;
            std::cerr << "FAIL: " << what << "\n";
        }
    }

    // ---- tests ---------------------------------------------------------------
    void TestRules()
    {
        ObserverContext o;
        o.ipHeaderAvailable = true;
        Check(!InterceptWho(o), "R1 OFF is stock");
        o.hideTbcRaces = true;
        Check(!InterceptWho(o), "R2 non-Vanilla observer is stock");
        o.observerIsVanilla = true;
        Check(InterceptWho(o), "Vanilla player observer is intercepted");

        // R0 (CS01 #145): without IP's exported header the module stays stock,
        // whatever the other inputs say, so no ConfigMgr fallback runs.
        ObserverContext noHeader = o;
        noHeader.ipHeaderAvailable = false;
        Check(!InterceptWho(noHeader), "R0 no IP header is stock");
        noHeader.gmBypass = false;
        noHeader.observerAboveSecPlayer = true;
        Check(!InterceptWho(noHeader), "R0 no IP header is stock for GMs too");
        o.observerAboveSecPlayer = true;
        Check(!InterceptWho(o), "R3 GM with bypass is stock");
        o.gmBypass = false;
        Check(InterceptWho(o), "GM without bypass is intercepted");

        Check(HideRow(RACE_BLOODELF, false) && HideRow(RACE_DRAENEI, false), "R5 hides 10 and 11");
        Check(!HideRow(RACE_BLOODELF, true), "R4 own row kept");
        for (std::uint8_t race = 1; race <= 9; ++race)
            Check(!HideRow(race, false), "Vanilla races never hidden");
    }

    std::vector<Row> RandomCache(std::mt19937& rng, std::size_t n)
    {
        static char const* names[] = { "Arthas", "Jaina", "Sylvanas", "Kaelthas", "Velen", "Grau", "Thrall", "Illidan" };
        static char const* guilds[] = { "", "Naxx", "Ashbringer", "Silvermoon" };
        std::vector<Row> rows;
        for (std::size_t i = 0; i < n; ++i)
        {
            Row r = MakeRow(100 + i, rng() % 2, std::uint8_t(1 + rng() % 11),
                            std::string(names[rng() % 8]) + std::to_string(i % 5),
                            guilds[rng() % 4], std::uint8_t(1 + rng() % 80), std::uint8_t(1 + rng() % 11),
                            std::uint32_t(1 + rng() % 4));
            r.security = (rng() % 10 == 0) ? int(rng() % 4) : 0;
            r.visible = rng() % 8 != 0;
            r.gender = std::uint8_t(rng() % 2);
            rows.push_back(r);
        }
        if (n > 0 && rng() % 2)
            rows[rng() % n].guid = 1; // sometimes the observer is in the cache
        return rows;
    }

    Query RandomQuery(std::mt19937& rng)
    {
        static char const* frag[] = { "", "ar", "JAINA", "kael", "grau", "zz", "\xFF" };
        Query q;
        q.levelMin = rng() % 3 == 0 ? rng() % 70 : 0;
        q.levelMax = rng() % 3 == 0 ? 20 + rng() % 90 : 100;
        q.name = frag[rng() % 7];
        q.guild = rng() % 4 == 0 ? frag[rng() % 7] : "";
        q.racemask = rng() % 3 == 0 ? std::uint32_t(rng()) : 0xFFFFFFFF;
        q.classmask = rng() % 4 == 0 ? std::uint32_t(rng()) : 0xFFFFFFFF;
        for (std::uint32_t i = 0, n = rng() % 4; i < n; ++i)
            q.zones.push_back(1 + rng() % 5);
        for (std::uint32_t i = 0, n = rng() % 3; i < n; ++i)
            q.strs.push_back(frag[rng() % 7]);
        if (rng() % 20 == 0)
            q.zonesCountOverride = 11;
        if (rng() % 20 == 0)
            q.strCountOverride = 5;
        if (rng() % 15 == 0)
            q.truncate = 1 + rng() % 6;
        return q;
    }

    Ctx RandomCtx(std::mt19937& rng)
    {
        Ctx c;
        c.team = int(rng() % 2);
        c.canSeeOtherTeam = rng() % 3 == 0;
        c.canSeeAllSecLevels = rng() % 5 == 0;
        c.gmLevelInWhoList = int(rng() % 3);
        c.observerIsPlayerAccount = rng() % 4 != 0;
        c.observerSecurity = c.observerIsPlayerAccount ? 0 : 1 + int(rng() % 3);
        c.maxReturn = rng() % 3 == 0 ? 3 + rng() % 10 : 49;
        c.areas = { { 1, "Stormwind City" }, { 2, "Silvermoon City" }, { 3, "Karazhan" } };
        return c;
    }

    // Hide OFF: byte-for-byte stock, including "no reply" and short packets.
    void TestStockParity()
    {
        std::mt19937 rng(20261025);
        int compared = 0, noReply = 0, shortPkts = 0;
        for (int round = 0; round < 3000; ++round)
        {
            std::vector<Row> rows = RandomCache(rng, rng() % 90);
            Ctx c = RandomCtx(rng);
            std::vector<std::uint8_t> in = Encode(RandomQuery(rng));

            bool stockThrew = false, mirrorThrew = false;
            std::optional<std::vector<std::uint8_t>> stock, mirror;
            try { stock = StockWho(in, rows, c); } catch (ShortPacket const&) { stockThrew = true; }
            try { mirror = MirrorWho(in, rows, c, false); } catch (ShortPacket const&) { mirrorThrew = true; }

            Check(stockThrew == mirrorThrew, "short packet throws in both");
            if (stockThrew)
            {
                ++shortPkts;
                continue;
            }
            Check(stock.has_value() == mirror.has_value(), "no-reply cases match");
            if (!stock)
            {
                ++noReply;
                continue;
            }
            Check(*stock == *mirror, "hide OFF reply bytes equal stock");
            ++compared;
        }
        Check(compared > 2000 && noReply > 50 && shortPkts > 50, "parity sample covers replies, no-reply and short packets");
    }

    // Hide ON: the reply equals stock run on the cache without hidden rows.
    void TestHideEqualsStockOnFilteredCache()
    {
        std::mt19937 rng(7);
        for (int round = 0; round < 3000; ++round)
        {
            std::vector<Row> rows = RandomCache(rng, rng() % 90);
            Ctx c = RandomCtx(rng);
            std::vector<std::uint8_t> in = Encode(RandomQuery(rng));

            std::vector<Row> visible;
            for (auto const& r : rows)
                if (!HideRow(r.race, r.guid == c.observerGuid))
                    visible.push_back(r);

            std::optional<std::vector<std::uint8_t>> expect, got;
            bool t1 = false, t2 = false;
            try { expect = StockWho(in, visible, c); } catch (ShortPacket const&) { t1 = true; }
            try { got = MirrorWho(in, rows, c, true); } catch (ShortPacket const&) { t2 = true; }
            Check(t1 == t2, "hide ON short packet behaviour");
            if (t1)
                continue;
            Check(expect.has_value() == got.has_value(), "hide ON no-reply cases");
            if (!expect)
                continue;
            // Byte equality with stock over the filtered cache proves that no
            // hidden row is listed or counted (the own row is kept by HideRow).
            Check(*expect == *got, "hide ON equals stock over the cache without hidden rows");
        }
    }

    void TestTargetedQueriesReturnZero()
    {
        Ctx c;
        c.canSeeOtherTeam = true;
        std::vector<Row> rows = {
            MakeRow(10, 0, RACE_BLOODELF, "Kaelthas", "Silvermoon", 70, 8, 2),
            MakeRow(11, 1, RACE_DRAENEI, "Velen", "Exodar", 70, 5, 2),
            MakeRow(12, 0, 1, "Arthas", "Naxx", 60, 1, 1),
        };
        c.areas = { { 1, "Stormwind City" }, { 2, "Silvermoon City" } };
        std::vector<std::uint8_t> const zero = { 0, 0, 0, 0, 0, 0, 0, 0 };

        Query byName; byName.name = "Kaelthas";
        Query byGuild; byGuild.guild = "exodar";
        Query byRace; byRace.racemask = 1u << RACE_BLOODELF;
        Query byRaces; byRaces.racemask = (1u << RACE_BLOODELF) | (1u << RACE_DRAENEI);
        Query byZone; byZone.zones = { 2 };
        Query byText; byText.strs = { "silvermoon" };
        Query composite; composite.name = "vel"; composite.classmask = 1u << 5; composite.zones = { 2 };
        for (Query const* q : { &byName, &byGuild, &byRace, &byRaces, &byZone, &byText, &composite })
        {
            auto got = MirrorWho(Encode(*q), rows, c, true);
            Check(got && *got == zero, "hidden-only query returns 0/0");
            auto stock = MirrorWho(Encode(*q), rows, c, false);
            Check(stock && U32(*stock, 4) > 0, "the same query finds rows in stock");
        }

        // Mixed text: only the Vanilla row remains, both counts are 1.
        Query mixed; mixed.strs = { "a" };
        auto got = MirrorWho(Encode(mixed), rows, c, true);
        Check(got && U32(*got, 0) == 1 && U32(*got, 4) == 1, "mixed query keeps only visible rows");
    }

    void TestCapAndCounts()
    {
        Ctx c;
        std::vector<Row> rows;
        for (int i = 0; i < 80; ++i)
            rows.push_back(MakeRow(100 + i, 0, (i % 4 == 0) ? RACE_BLOODELF : 1, "P" + std::to_string(i)));
        auto got = MirrorWho(Encode(Query{}), rows, c, true);
        Check(got.has_value(), "cap reply");
        Check(U32(*got, 4) == 60, "matchCount excludes the 20 hidden rows");
        Check(U32(*got, 0) == 49, "display count capped at 49");
        auto shown = Decode(*got);
        Check(shown.size() == 49, "49 rows on the wire");
        int expected = 0;
        for (int i = 0, n = 0; i < 80 && n < 49; ++i)
        {
            if (i % 4 == 0)
                continue;
            Check(shown[n].first == "P" + std::to_string(i), "first 49 visible rows in cache order");
            ++n;
            expected = i;
        }
        (void)expected;

        // A filter placed after the increment (the #107 trap) would leave
        // matchCount at 80: make sure that is not what the mirror does.
        Check(U32(*got, 4) != 80, "hidden rows are not counted");
    }

    void TestOwnRowAndGm()
    {
        Ctx c;
        c.observerGuid = 42;
        std::vector<Row> rows = { MakeRow(42, 0, RACE_BLOODELF, "Selfelf"), MakeRow(43, 0, RACE_BLOODELF, "Otherelf") };
        Query own; own.name = "selfelf";
        auto got = MirrorWho(Encode(own), rows, c, true);
        Check(got && U32(*got, 0) == 1 && U32(*got, 4) == 1, "own Blood Elf row kept (O1 default)");
        Query other; other.name = "otherelf";
        got = MirrorWho(Encode(other), rows, c, true);
        Check(got && U32(*got, 4) == 0, "another Vanilla-stage Blood Elf hidden (O2)");
    }

    void TestMalformed()
    {
        Ctx c;
        std::vector<Row> rows = { MakeRow(5, 0, 1, "Arthas") };
        for (bool hide : { false, true })
        {
            Query zones; zones.zonesCountOverride = 11;
            Check(!MirrorWho(Encode(zones), rows, c, hide), "zonesCount > 10: no reply");
            Query strs; strs.strCountOverride = 5;
            Check(!MirrorWho(Encode(strs), rows, c, hide), "strCount > 4: no reply");
            Query badName; badName.name = "\xFF";
            Check(!MirrorWho(Encode(badName), rows, c, hide), "invalid UTF-8 name: no reply");
            Query badStr; badStr.strs = { "\xFF" };
            Check(MirrorWho(Encode(badStr), rows, c, hide).has_value(), "invalid search string is skipped, as stock");
            Query cut; cut.truncate = 3;
            bool threw = false;
            try { MirrorWho(Encode(cut), rows, c, hide); } catch (ShortPacket const&) { threw = true; }
            Check(threw, "short packet throws, as stock");
        }
    }
}

int main()
{
    TestRules();
    TestStockParity();
    TestHideEqualsStockOnFilteredCache();
    TestTargetedQueriesReturnZero();
    TestCapAndCounts();
    TestOwnRowAndGm();
    TestMalformed();
    if (failures)
    {
        std::cerr << failures << " failure(s)\n";
        return 1;
    }
    std::cout << "PASS: F14 /who mirror is byte-identical to stock when not hiding; hidden rows leave both counts\n";
    return 0;
}
