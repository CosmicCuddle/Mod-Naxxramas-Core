#include "HunterPetAutocastAddon.h"

#include <iostream>
#include <string>
#include <vector>

using namespace NaxxramasHunterPetAutocast;

namespace
{
    int g_failed = 0;

    void Check(bool condition, char const* expression, char const* file, int line)
    {
        if (condition)
            return;
        std::cerr << "FAIL " << file << ":" << line << " " << expression << "\n";
        ++g_failed;
    }

    SpellLookup Lookup(uint32_t spellId, void const* /*ctx*/)
    {
        SpellLookup lookup;
        if (spellId == 999)
            return lookup;
        lookup.Autocastable = true;
        if (spellId == 17259 || spellId == 17260)
            lookup.ChainId = 17253;
        else
            lookup.ChainId = spellId;
        return lookup;
    }

    std::string Wire(std::string const& payload)
    {
        return std::string(AddonPrefix()) + "\t" + payload;
    }

    SpellView Choice(uint32_t id, uint32_t chain, uint8_t active)
    {
        SpellView spell;
        spell.SpellId = id;
        spell.ChainId = chain;
        spell.Active = active;
        spell.Autocastable = true;
        spell.HasBar = true;
        spell.Bar = active;
        spell.InAutospells = active == ACT_ENABLED;
        spell.Present = true;
        return spell;
    }

    void TestParser()
    {
        Check(AddonPayloadBudget() == 233, "payload budget is 233", __FILE__, __LINE__);
        Check(kMaxRawBytes == 255, "raw ceiling is 255", __FILE__, __LINE__);

        ParseResult example = ParseAddonMessage(Wire("v1|7|1/1|1742=0,17259=1"));
        Check(example.Kind == ParseKind::Chunk && example.Seq == 7, "example seq", __FILE__, __LINE__);
        Check(example.Index == 1 && example.Total == 1 && example.Pairs.size() == 2, "example shape", __FILE__, __LINE__);
        Check(example.Pairs[0].first == 1742 && !example.Pairs[0].second, "example cower off", __FILE__, __LINE__);
        Check(example.Pairs[1].first == 17259 && example.Pairs[1].second, "example bite on", __FILE__, __LINE__);

        Check(ParseAddonMessage("HELLO").Kind == ParseKind::NotOurs, "other text is not ours", __FILE__, __LINE__);
        Check(ParseAddonMessage("NXCPAK").Kind == ParseKind::NotOurs, "prefix without tab is not ours", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("")).Kind == ParseKind::Malformed, "empty payload", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|clear")).Kind == ParseKind::Clear, "clear", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|clearX")).Kind == ParseKind::Malformed, "clear suffix", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v2|clear")).Kind == ParseKind::Malformed, "wrong version", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|0|1/1|")).Kind == ParseKind::Malformed, "seq 0", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|01|1/1|")).Kind == ParseKind::Malformed, "seq leading zero", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|0/1|")).Kind == ParseKind::Malformed, "index 0", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|2/1|")).Kind == ParseKind::Malformed, "index above total", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/9|")).Kind == ParseKind::Malformed, "total above 8", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|12=2")).Kind == ParseKind::Malformed, "bit other than 0 or 1", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|12=1,")).Kind == ParseKind::Malformed, "trailing comma", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|,12=1")).Kind == ParseKind::Malformed, "empty pair", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|12=")).Kind == ParseKind::Malformed, "missing bit", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|=1")).Kind == ParseKind::Malformed, "missing spell", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|abc=1")).Kind == ParseKind::Malformed, "non-digit spell", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|12=1 ")).Kind == ParseKind::Malformed, "space", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|12=1\t13=0")).Kind == ParseKind::Malformed, "tab in payload", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|12=1,12=0")).Kind == ParseKind::Malformed, "duplicate spell in one chunk", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire("v1|1|1/1|")).Kind == ParseKind::Chunk, "empty pair list is a chunk", __FILE__, __LINE__);

        std::string oversized(256, 'A');
        oversized.replace(0, 7, "NXCPAK\t");
        Check(oversized.size() == 256, "oversized fixture length", __FILE__, __LINE__);
        Check(ParseAddonMessage(oversized).Kind == ParseKind::Malformed, "256 bytes are malformed", __FILE__, __LINE__);

        std::string pairs;
        for (int i = 0; i < 24; ++i)
        {
            if (i != 0)
                pairs += ',';
            pairs += std::to_string(1000000 + i);
            pairs += "=1";
        }
        std::string full = Wire(std::string("v1|1|1/1|") + pairs);
        Check(full.size() == 255, "255-byte fixture", __FILE__, __LINE__);
        Check(full.size() - 7 > AddonPayloadBudget(), "255-byte payload is above the addon budget", __FILE__, __LINE__);
        ParseResult accepted = ParseAddonMessage(full);
        Check(accepted.Kind == ParseKind::Chunk && accepted.Pairs.size() == 24, "255 bytes still parse", __FILE__, __LINE__);

        std::string counted;
        for (int i = 0; i < 64; ++i)
        {
            if (i != 0)
                counted += ',';
            counted += std::to_string(i + 1);
            counted += "=1";
        }
        std::vector<std::pair<uint32_t, bool>> parsedPairs;
        Check(ParsePairs(counted, parsedPairs) && parsedPairs.size() == 64, "64 pairs parse", __FILE__, __LINE__);
        counted += ",65=1";
        Check(!ParsePairs(counted, parsedPairs), "65 pairs are malformed", __FILE__, __LINE__);
        Check(ParseAddonMessage(Wire(std::string("v1|1|1/1|") + counted)).Kind == ParseKind::Malformed,
            "a 65-pair wire message is malformed", __FILE__, __LINE__);
    }

    void TestStore()
    {
        OptInStore store;
        uint64_t const guid = 42;
        auto accept = [&](std::string const& payload, uint64_t now, bool hunter = true) {
            return store.Accept(guid, hunter, Wire(payload), now, &Lookup, nullptr);
        };

        Check(accept("v1|7|1/1|1742=0,17259=1,999=1", 1000) == IngestResult::Published, "example publishes", __FILE__, __LINE__);
        std::shared_ptr<PreferenceSnapshot const> snap;
        uint64_t generation = store.Read(guid, snap);
        Check(generation != 0 && snap && snap->OptedIn && snap->Seq == 7, "published seq 7", __FILE__, __LINE__);
        Check(snap->Choices.size() == 2, "999 is dropped and two chains remain", __FILE__, __LINE__);
        ChainChoice const* cower = FindChoice(*snap, 1742);
        ChainChoice const* bite = FindChoice(*snap, 17253);
        Check(cower && cower->SpellId == 1742 && !cower->Enabled, "cower chain stored off", __FILE__, __LINE__);
        Check(bite && bite->SpellId == 17259 && bite->Enabled, "bite chain ignores rank id", __FILE__, __LINE__);
        std::shared_ptr<PreferenceSnapshot const> held = snap;

        Check(accept("nope", 1100) == IngestResult::Malformed, "malformed ingest", __FILE__, __LINE__);
        store.Read(guid, snap);
        Check(snap && snap->Seq == 7, "malformed does not replace the set", __FILE__, __LINE__);

        Check(store.Accept(guid, false, Wire("v1|8|1/1|17259=0"), 1200, &Lookup, nullptr) == IngestResult::IgnoredNotHunter,
            "non-hunter ignored", __FILE__, __LINE__);
        store.Read(guid, snap);
        Check(snap && snap->Seq == 7, "non-hunter does not replace the set", __FILE__, __LINE__);

        Check(accept("v1|8|2/2|17259=1", 1300) == IngestResult::Partial, "second chunk first", __FILE__, __LINE__);
        Check(accept("v1|8|1/2|1742=0", 1400) == IngestResult::Published, "first chunk completes out of order", __FILE__, __LINE__);
        store.Read(guid, snap);
        Check(snap && snap->Seq == 8 && FindChoice(*snap, 17253) && FindChoice(*snap, 17253)->Enabled,
            "out-of-order chunks publish in index order", __FILE__, __LINE__);

        uint64_t now = 1500;
        auto nextWindow = [&]() {
            now += kRateLimitWindowMs;
            return now;
        };
        Check(accept("v1|9|1/2|17259=1", nextWindow()) == IngestResult::Partial, "partial seq 9", __FILE__, __LINE__);
        Check(accept("v1|9|1/2|17259=0", now + 1) == IngestResult::Malformed, "conflicting chunk drops the partial", __FILE__, __LINE__);
        store.Read(guid, snap);
        Check(snap && snap->Seq == 8, "conflict keeps the published set", __FILE__, __LINE__);

        Check(accept("v1|10|1/2|1742=0", nextWindow()) == IngestResult::Partial, "partial seq 10", __FILE__, __LINE__);
        Check(accept("v1|10|1/2|1742=0", now + 1) == IngestResult::Partial, "identical chunk is not a conflict", __FILE__, __LINE__);
        Check(accept("v1|11|1/1|17259=0", nextWindow()) == IngestResult::Published, "higher seq replaces the partial", __FILE__, __LINE__);
        Check(accept("v1|10|2/2|17259=1", now + 1) == IngestResult::StaleSeq, "old partial chunk is stale", __FILE__, __LINE__);
        store.Read(guid, snap);
        Check(snap && snap->Seq == 11 && FindChoice(*snap, 17253) && !FindChoice(*snap, 17253)->Enabled,
            "higher seq won", __FILE__, __LINE__);
        Check(accept("v1|4|1/1|17259=1", now + 2) == IngestResult::StaleSeq, "lower seq ignored while online", __FILE__, __LINE__);

        store.OnLogin(guid);
        Check(accept("v1|1|1/1|17259=1", nextWindow()) == IngestResult::Published, "login accepts a lower seq", __FILE__, __LINE__);
        store.Read(guid, snap);
        Check(snap && snap->Seq == 1, "seq 1 replaced the set after login", __FILE__, __LINE__);

        Check(accept("v1|clear", nextWindow()) == IngestResult::Cleared, "clear", __FILE__, __LINE__);
        uint64_t clearedGeneration = store.Read(guid, snap);
        Check(clearedGeneration != 0 && !snap, "clear removes the snapshot and keeps a generation", __FILE__, __LINE__);
        Check(held && held->Seq == 7 && held->Choices.size() == 2, "held snapshot stays immutable", __FILE__, __LINE__);
        Check(accept("v1|1|1/1|17259=1", now + 1) == IngestResult::Published, "clear resets seq tracking", __FILE__, __LINE__);

        store.OnLogout(guid);
        std::shared_ptr<PreferenceSnapshot const> gone;
        Check(store.Read(guid, gone) == 0 && !gone, "logout clears the player", __FILE__, __LINE__);

        OptInStore limited;
        for (uint32_t seq = 1; seq <= kRateLimitCount; ++seq)
        {
            IngestResult result = limited.Accept(
                7, true, Wire("v1|" + std::to_string(seq) + "|1/1|17259=1"), 5000, &Lookup, nullptr);
            Check(result == IngestResult::Published, "messages inside the rate window publish", __FILE__, __LINE__);
        }
        Check(limited.Accept(7, true, Wire("v1|9|1/1|17259=0"), 5001, &Lookup, nullptr) == IngestResult::RateLimited,
            "the ninth message in the window is limited", __FILE__, __LINE__);
        std::shared_ptr<PreferenceSnapshot const> limitedSnap;
        limited.Read(7, limitedSnap);
        Check(limitedSnap && limitedSnap->Seq == kRateLimitCount, "rate limit does not publish the extra message", __FILE__, __LINE__);
        Check(limited.Accept(7, true, Wire("v1|9|1/1|17259=0"), 5000 + kRateLimitWindowMs, &Lookup, nullptr) == IngestResult::Published,
            "a new window accepts again", __FILE__, __LINE__);
    }

    void TestPlan()
    {
        SpellView oldOn = Choice(17259, 17253, ACT_ENABLED);
        SpellView neuOff = Choice(17260, 17253, ACT_DISABLED);
        SpellView cowerOn = Choice(1742, 1742, ACT_ENABLED);
        ExpensiveWork work;
        AddonPlan blocked = BuildAddonPlan({oldOn}, {neuOff}, nullptr, 0, 0, &work);
        Check(!blocked.OptedIn && blocked.Toggles.empty() && !blocked.UsedDecide && work.DecideCalls == 0,
            "no write and no decision without an opt-in", __FILE__, __LINE__);

        PreferenceSnapshot set;
        set.OptedIn = true;
        set.Seq = 7;
        ChainChoice cower;
        cower.ChainId = 1742;
        cower.SpellId = 1742;
        cower.Enabled = false;
        ChainChoice bite;
        bite.ChainId = 17253;
        bite.SpellId = 17259;
        bite.Enabled = true;
        set.Choices.push_back(cower);
        set.Choices.push_back(bite);

        AddonPlan fresh = BuildAddonPlan({oldOn}, {neuOff, cowerOn}, &set, 1, 0, &work);
        Check(fresh.OptedIn && !fresh.UsedDecide && work.DecideCalls == 0, "a new set does not call DecideChains", __FILE__, __LINE__);
        Check(fresh.Toggles.size() == 1 && fresh.Toggles[0].SpellId == 17260 && fresh.Toggles[0].Enable,
            "fresh apply matches the chain and skips cower", __FILE__, __LINE__);

        AddonPlan missing = BuildAddonPlan({}, {}, &set, 1, 0, &work);
        Check(missing.Toggles.empty(), "a listed spell the pet lacks is not learned", __FILE__, __LINE__);

        ExpensiveWork reapply;
        AddonPlan again = BuildAddonPlan({oldOn}, {neuOff}, &set, 1, 1, &reapply);
        Check(again.UsedDecide && reapply.DecideCalls == 1, "a later reset decides once", __FILE__, __LINE__);
        Check(again.Toggles.size() == 1 && again.Toggles[0].SpellId == 17260 && again.Toggles[0].Enable,
            "the stored set is re-applied after the reset", __FILE__, __LINE__);

        PreferenceSnapshot other;
        other.OptedIn = true;
        ChainChoice growl;
        growl.ChainId = 2649;
        growl.SpellId = 2649;
        growl.Enabled = true;
        other.Choices.push_back(growl);
        ExpensiveWork unlisted;
        AddonPlan left = BuildAddonPlan({oldOn}, {neuOff}, &other, 3, 3, &unlisted);
        Check(left.UsedDecide && left.Toggles.empty(), "an unlisted chain is left alone", __FILE__, __LINE__);

        SpellView clicked = Choice(17259, 17253, ACT_DISABLED);
        ExpensiveWork click;
        AddonPlan stuck = BuildAddonPlan({oldOn}, {clicked}, &set, 1, 1, &click);
        Check(click.DecideCalls == 1 && stuck.Toggles.empty(), "a same-id click is not overwritten", __FILE__, __LINE__);

        std::vector<SpellView> steady{oldOn};
        ExpensiveWork quiet;
        uint64_t applied = 0;
        bool primed = false;
        auto tick = [&](std::vector<SpellView> const& live, bool honorFast, ExpensiveWork& counter) {
            if (honorFast && primed && SameBook(steady, live) && applied == 1)
                return;
            BuildAddonPlan(steady, live, &set, 1, applied, &counter);
            steady = live;
            applied = 1;
            primed = true;
        };
        tick(steady, true, quiet);
        int const afterPrime = quiet.DecideCalls;
        for (int i = 0; i < 1000; ++i)
            tick(steady, true, quiet);
        Check(quiet.DecideCalls == afterPrime && afterPrime == 0, "1000 identical ticks do not decide", __FILE__, __LINE__);

        ExpensiveWork forced;
        for (int i = 0; i < 1000; ++i)
            BuildAddonPlan(steady, steady, &set, 1, 1, &forced);
        Check(forced.DecideCalls == 1000, "removing the fast path decides every identical tick", __FILE__, __LINE__);
    }
}

int main()
{
    TestParser();
    TestStore();
    TestPlan();
    if (g_failed != 0)
    {
        std::cerr << g_failed << " failure(s)\n";
        return 1;
    }
    std::cout << "PASS: Hunter pet autocast addon protocol\n";
    return 0;
}
