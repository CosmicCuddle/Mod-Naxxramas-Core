// F14 P16 (test-only): a race the /who writer hides is still sent by the
// name query.
//
// SendNameQueryOpcode.inc is the real WorldSession::SendNameQueryOpcode
// (QueryHandler.cpp L32-L62 at Grimfeather 8daffda) and WhoListingPolicy.h is
// #145's real /who writer; tests/f14_race_exposure_extract.py writes both,
// unchanged. The stubs below supply only the names that function uses.
//
// Build: python3 -I tests/f14_race_exposure_extract.py CORE . OUT
//        g++ -std=c++20 -IOUT tests/f14_race_exposure_tests.cpp
#include "WhoListingPolicy.h"

#include <cstdint>
#include <cstdio>
#include <map>
#include <string>
#include <string_view>
#include <vector>

// ---- stubs for the names SendNameQueryOpcode uses -------------------------
constexpr std::uint8_t RACE_NONE = 0;
constexpr std::uint8_t GENDER_MALE = 0;
constexpr std::uint8_t CLASS_NONE = 0;
constexpr std::uint8_t RACE_HUMAN = 1, RACE_BLOODELF = 10, RACE_DRAENEI = 11;

struct PackedGuid
{
    std::uint64_t value = 0;
};

struct ObjectGuid
{
    std::uint64_t value = 0;
    PackedGuid WriteAsPacked() const { return PackedGuid{value}; }
    bool operator<(ObjectGuid const& o) const { return value < o.value; }
};

struct DeclinedName
{
    std::string name[5];
};

class Player
{
public:
    std::uint8_t race = 0, gender = 0, cls = 0;
    std::uint8_t getRace() const { return race; }
    std::uint8_t getGender() const { return gender; }
    std::uint8_t getClass() const { return cls; }
    DeclinedName const* GetDeclinedNames() const { return nullptr; }
};

struct CharacterCacheEntry
{
    ObjectGuid Guid;
    std::string Name;
    std::uint8_t Class = 0, Race = 0, Sex = 0;
};

struct CharacterCache
{
    std::map<std::uint64_t, CharacterCacheEntry> rows;
    CharacterCacheEntry const* GetCharacterCacheByGuid(ObjectGuid g) const
    {
        auto it = rows.find(g.value);
        return it == rows.end() ? nullptr : &it->second;
    }
};
CharacterCache characterCache;
CharacterCache* const sCharacterCache = &characterCache;

std::map<std::uint64_t, Player*> connected;
namespace ObjectAccessor
{
    Player* FindConnectedPlayer(ObjectGuid g)
    {
        auto it = connected.find(g.value);
        return it == connected.end() ? nullptr : it->second;
    }
}

class WorldPacket;
namespace WorldPackets::Query
{
    // Field list as in QueryPackets.h L38-L54 at 8daffda.
    class NameQueryResponse
    {
    public:
        PackedGuid Guid;
        std::uint8_t NameUnknown = false;
        std::string_view Name;
        std::string_view RealmName = "";
        std::uint8_t Race = RACE_NONE;
        std::uint8_t Sex = GENDER_MALE;
        std::uint8_t Class = CLASS_NONE;
        std::uint8_t Declined = false;
        DeclinedName DeclinedNames;
        NameQueryResponse const* Write() const { return this; }
    };
}

// Any logged-in session; the function never reads who is asking.
class WorldSession
{
public:
    explicit WorldSession(std::string observer) : observerName(std::move(observer)) { }
    std::string observerName;
    std::vector<WorldPackets::Query::NameQueryResponse> sent;
    void SendPacket(WorldPackets::Query::NameQueryResponse const* p) { sent.push_back(*p); }
    void SendNameQueryOpcode(ObjectGuid guid);
};

#include "SendNameQueryOpcode.inc"

// ---- /who side (as in #228's test) ----------------------------------------
namespace
{
    constexpr int EXPECTED_CHECKS = 12;
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
        static bool FitTo(std::string const&, std::wstring const&) { return false; }
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
        std::uint64_t observerGuid = 999;
        bool observerIsPlayerAccount = true;
        int observerSecurity = 0;
        std::uint32_t maxReturn = 50;
        std::string AreaName(std::uint32_t) const { return "zone"; }
    };

    // Shown / matched counts of #145's reply to "/who <name>".
    std::pair<std::uint32_t, std::uint32_t> Who(std::vector<Row> const& rows, std::wstring const& name, bool hide)
    {
        NaxxramasWhoListing::WhoRequest req;
        req.levelMax = 80;
        req.racemask = req.classmask = 0xFFFFFFFFu;
        req.playerName = name;
        Writer w;
        NaxxramasWhoListing::WriteWhoReply<Text>(req, rows, Ctx{}, hide, w);
        auto u32 = [&](std::size_t at) {
            return std::uint32_t(w.bytes[at]) | std::uint32_t(w.bytes[at + 1]) << 8 |
                   std::uint32_t(w.bytes[at + 2]) << 16 | std::uint32_t(w.bytes[at + 3]) << 24;
        };
        return {u32(0), u32(4)};
    }

    WorldPackets::Query::NameQueryResponse Ask(WorldSession& s, std::uint64_t guid)
    {
        s.SendNameQueryOpcode(ObjectGuid{guid});
        return s.sent.back();
    }
}

int main()
{
    // Online Blood Elf (201), offline Draenei (202), online Human (203).
    Player elf;
    elf.race = RACE_BLOODELF;
    elf.cls = 2;
    Player human;
    human.race = RACE_HUMAN;
    human.cls = 1;
    connected[201] = &elf;
    connected[203] = &human;
    characterCache.rows[201] = {ObjectGuid{201}, "elfplayer", 2, RACE_BLOODELF, 0};
    characterCache.rows[202] = {ObjectGuid{202}, "draeneialt", 7, RACE_DRAENEI, 1};
    characterCache.rows[203] = {ObjectGuid{203}, "humanplayer", 1, RACE_HUMAN, 0};

    std::vector<Row> who = {
        {201, RACE_BLOODELF, "elfplayer", L"elfplayer", "", L""},
        {203, RACE_HUMAN, "humanplayer", L"humanplayer", "", L""},
    };

    // 1. #145 hides the Blood Elf from a Vanilla-stage observer's /who...
    CHECK(Who(who, L"elfplayer", true) == std::make_pair(0u, 0u));
    CHECK(Who(who, L"elfplayer", false) == std::make_pair(1u, 1u));   // stock shows it
    CHECK(Who(who, L"humanplayer", true) == std::make_pair(1u, 1u));

    // 2. ...but the same observer's name query for that GUID returns the race.
    WorldSession vanilla("vanilla observer");
    auto const r1 = Ask(vanilla, 201);
    CHECK(!r1.NameUnknown);
    CHECK(r1.Race == RACE_BLOODELF);
    CHECK(r1.Name == "elfplayer");

    // 3. An offline character is answered from the character cache.
    auto const r2 = Ask(vanilla, 202);
    CHECK(!r2.NameUnknown);
    CHECK(r2.Race == RACE_DRAENEI);

    // 4. The reply does not depend on who asks.
    WorldSession tbc("tbc observer");
    auto const r3 = Ask(tbc, 201);
    CHECK(r3.Race == r1.Race && r3.Name == r1.Name && r3.Class == r1.Class && r3.Sex == r1.Sex);

    // 5. An online player's live race wins over the cache (cache can lag a
    //    race change).
    characterCache.rows[201].Race = RACE_HUMAN;
    CHECK(Ask(vanilla, 201).Race == RACE_BLOODELF);
    characterCache.rows[201].Race = RACE_BLOODELF;

    // 6. Only an unknown GUID gets no race.
    auto const r4 = Ask(vanilla, 404);
    CHECK(r4.NameUnknown);
    CHECK(r4.Race == RACE_NONE);

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
    std::printf("PASS: F14 P16 name query exposes race hidden by /who, %d checks\n", checks);
    return 0;
}
