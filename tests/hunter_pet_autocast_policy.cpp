#include "HunterPetAutocastPolicy.h"

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

    void ExpectOne(char const* name, std::vector<ChainOutcome> const& outcomes, Outcome want)
    {
        bool const ok = outcomes.size() == 1 && outcomes[0].Result == want;
        if (ok)
            return;
        std::cerr << "FAIL case " << name << " expected " << OutcomeName(want) << " got ";
        if (outcomes.empty())
            std::cerr << "no outcome";
        else
            std::cerr << OutcomeName(outcomes[0].Result) << " x" << outcomes.size();
        std::cerr << "\n";
        ++g_failed;
    }

    void TestDecisionTable()
    {
        std::vector<SpellView> on{Choice(801, 800, ACT_ENABLED)};
        std::vector<SpellView> off{Choice(800, 800, ACT_DISABLED)};
        ExpectOne("switch-off", DecideCall(false, true, on, off), Outcome::OutOfScope);
        ExpectOne("not-human", DecideCall(true, false, on, off), Outcome::OutOfScope);
        ExpectOne("rank-swap-on", DecideCall(true, true, on, off), Outcome::RestoreEnabled);

        std::vector<SpellView> baseOff{Choice(801, 800, ACT_DISABLED)};
        ExpectOne("rank-swap-off-already", DecideCall(true, true, baseOff, off), Outcome::NoWrite);
        std::vector<SpellView> curOn{Choice(800, 800, ACT_ENABLED)};
        ExpectOne("rank-swap-off-bar-on", DecideCall(true, true, baseOff, curOn), Outcome::RestoreDisabled);

        SpellView splitOff = Choice(800, 800, ACT_DISABLED);
        splitOff.Bar = ACT_ENABLED;
        ExpectOne("successor-split-row-off", DecideCall(true, true, baseOff, {splitOff}), Outcome::NoWrite);
        SpellView splitOn = Choice(800, 800, ACT_ENABLED);
        splitOn.Bar = ACT_DISABLED;
        ExpectOne("successor-split-row-on", DecideCall(true, true, on, {splitOn}), Outcome::NoWrite);

        ExpectOne("removal-no-successor",
            DecideCall(true, true, {Choice(1742, 1742, ACT_ENABLED)}, {}),
            Outcome::NoLearn);

        ExpectOne("same-spell-on",
            DecideCall(true, true, {Choice(9001, 9001, ACT_ENABLED)}, {Choice(9001, 9001, ACT_DISABLED)}),
            Outcome::NoWrite);
        ExpectOne("same-spell-off",
            DecideCall(true, true, {Choice(9001, 9001, ACT_DISABLED)}, {Choice(9001, 9001, ACT_DISABLED)}),
            Outcome::NoWrite);

        SpellView splitBase = Choice(801, 800, ACT_ENABLED);
        splitBase.Bar = ACT_DISABLED;
        splitBase.InAutospells = true;
        ExpectOne("split-baseline", DecideCall(true, true, {splitBase}, off), Outcome::NoWrite);

        ExpectOne("two-baseline-ranks",
            DecideCall(true, true, {Choice(801, 800, ACT_ENABLED), Choice(802, 800, ACT_DISABLED)}, off),
            Outcome::NoWrite);
        ExpectOne("two-current-ranks",
            DecideCall(true, true, on, {Choice(800, 800, ACT_DISABLED), Choice(802, 800, ACT_DISABLED)}),
            Outcome::NoWrite);

        SpellView passiveSuccessor = Choice(800, 800, ACT_DISABLED);
        passiveSuccessor.Autocastable = false;
        ExpectOne("not-autocastable", DecideCall(true, true, on, {passiveSuccessor}), Outcome::NoWrite);

        SpellView missingBar = Choice(800, 800, ACT_DISABLED);
        missingBar.HasBar = false;
        missingBar.Bar = 0;
        ExpectOne("missing-bar", DecideCall(true, true, on, {missingBar}), Outcome::NoBar);

        SpellView passive = Choice(801, 800, ACT_PASSIVE);
        passive.Autocastable = false;
        passive.InAutospells = false;
        SpellView passiveNow = Choice(800, 800, ACT_PASSIVE);
        passiveNow.Autocastable = false;
        passiveNow.InAutospells = false;
        ExpectOne("passive", DecideCall(true, true, {passive}, {passiveNow}), Outcome::NoWrite);

        ExpectOne("chain-mismatch",
            DecideCall(true, true, on, {Choice(800, 999, ACT_DISABLED)}),
            Outcome::NoLearn);
        ExpectOne("already-enabled",
            DecideCall(true, true, on, {Choice(800, 800, ACT_ENABLED)}),
            Outcome::NoWrite);
        ExpectOne("empty-baseline", DecideCall(true, true, {}, {}), Outcome::NoWrite);

        SpellView splitVector = Choice(800, 800, ACT_DISABLED);
        splitVector.InAutospells = true;
        ExpectOne("successor-split-vector", DecideCall(true, true, on, {splitVector}), Outcome::NoWrite);
    }

    struct PinnedRank
    {
        uint32_t First;
        uint32_t Spell;
    };

    PinnedRank const PINNED[] = {
        {17253, 17253}, {17253, 17255}, {17253, 17256}, {17253, 17257}, {17253, 17258},
        {17253, 17259}, {17253, 17260}, {17253, 17261}, {17253, 27050}, {17253, 52473},
        {17253, 52474},
        {16827, 16827}, {16827, 16828}, {16827, 16829}, {16827, 16830}, {16827, 16831},
        {16827, 16832}, {16827, 3010}, {16827, 3009}, {16827, 27049}, {16827, 52471},
        {16827, 52472},
        {24604, 24604}, {24604, 64491}, {24604, 64492}, {24604, 64493}, {24604, 64494},
        {24604, 64495},
        {24450, 24450}, {24450, 24452}, {24450, 24453}
    };

    uint32_t ChainOf(uint32_t spellId)
    {
        for (PinnedRank const& row : PINNED)
            if (row.Spell == spellId)
                return row.First;
        return spellId;
    }

    void TestPinnedChains()
    {
        Check(sizeof(PINNED) / sizeof(PINNED[0]) == 31, "31 pinned rows", __FILE__, __LINE__);
        int bite = 0;
        int claw = 0;
        int howl = 0;
        int prowl = 0;
        for (PinnedRank const& row : PINNED)
        {
            if (row.First == 17253)
                ++bite;
            else if (row.First == 16827)
                ++claw;
            else if (row.First == 24604)
                ++howl;
            else if (row.First == 24450)
                ++prowl;
            else
                Check(false, "unknown family", __FILE__, __LINE__);
        }
        Check(bite == 11 && claw == 11 && howl == 6 && prowl == 3, "family counts", __FILE__, __LINE__);

        uint32_t const cowerRanks[] = {1742, 1753, 1754, 1755, 1756, 16697, 27048};
        for (uint32_t spellId : cowerRanks)
            Check(ChainOf(spellId) == spellId, "cower rank is its own chain", __FILE__, __LINE__);

        auto restore = [](uint32_t from, uint32_t to, uint8_t active) {
            return DecideCall(true, true,
                {Choice(from, ChainOf(from), active)},
                {Choice(to, ChainOf(to), active == ACT_ENABLED ? ACT_DISABLED : ACT_ENABLED)});
        };
        ExpectOne("bite-9-to-10", restore(27050, 52473, ACT_ENABLED), Outcome::RestoreEnabled);
        ExpectOne("bite-10-to-11", restore(52473, 52474, ACT_ENABLED), Outcome::RestoreEnabled);
        ExpectOne("claw-10-to-11", restore(52471, 52472, ACT_DISABLED), Outcome::RestoreDisabled);
        ExpectOne("howl-5-to-6", restore(64494, 64495, ACT_ENABLED), Outcome::RestoreEnabled);
        ExpectOne("prowl-1-to-3", restore(24450, 24453, ACT_ENABLED), Outcome::RestoreEnabled);
        ExpectOne("bite-to-claw", restore(52474, 52472, ACT_ENABLED), Outcome::NoLearn);
        ExpectOne("unknown-removed",
            DecideCall(true, true, {Choice(999001, ChainOf(999001), ACT_ENABLED)}, {}),
            Outcome::NoLearn);
        ExpectOne("unknown-cross",
            DecideCall(true, true,
                {Choice(999001, ChainOf(999001), ACT_ENABLED)},
                {Choice(999002, ChainOf(999002), ACT_DISABLED)}),
            Outcome::NoLearn);
    }

    void TestGuardMutations()
    {
        std::vector<SpellView> on{Choice(801, 800, ACT_ENABLED)};
        std::vector<SpellView> off{Choice(800, 800, ACT_DISABLED)};
        ExpectOne("enabled-guard", DecideCall(false, true, on, off), Outcome::OutOfScope);
        auto enabledRemoved = DecideCall(false, true, on, off, false, true, true, true, true);
        ExpectOne("enabled-guard-removed", enabledRemoved, Outcome::RestoreEnabled);
        Check(enabledRemoved.size() == 1 && enabledRemoved[0].Result != Outcome::OutOfScope,
            "off key test fails when the enabled guard is removed", __FILE__, __LINE__);

        ExpectOne("human-guard", DecideCall(true, false, on, off), Outcome::OutOfScope);
        auto humanRemoved = DecideCall(true, false, on, off, true, false, true, true, true);
        ExpectOne("human-guard-removed", humanRemoved, Outcome::RestoreEnabled);
        Check(humanRemoved.size() == 1 && humanRemoved[0].Result != Outcome::OutOfScope,
            "bot key test fails when the human guard is removed", __FILE__, __LINE__);

        std::vector<SpellView> cower{Choice(1742, 1742, ACT_ENABLED)};
        std::vector<SpellView> invented{Choice(800, 1742, ACT_DISABLED)};
        ExpectOne("cower-guard", DecideChains(cower, invented), Outcome::NoLearn);
        auto cowerRemoved = DecideChains(cower, invented, false, true, true);
        ExpectOne("cower-guard-removed", cowerRemoved, Outcome::RestoreEnabled);
        Check(cowerRemoved.size() == 1 && cowerRemoved[0].Result != Outcome::NoLearn,
            "cower key test fails when the cower guard is removed", __FILE__, __LINE__);
        Check(cowerRemoved[0].SuccessorSpellId != COWER_SPELL_ID, "successor is not 1742", __FILE__, __LINE__);

        ExpectOne("cower-same-id",
            DecideCall(true, true, cower, {Choice(1742, 1742, ACT_DISABLED)}),
            Outcome::NoWrite);

        ApplyStats stats;
        CommitResult resurrect = CommitRestore(Choice(COWER_SPELL_ID, COWER_SPELL_ID, ACT_DISABLED), true, true, true, true, stats);
        Check(resurrect.Claim == Outcome::NoLearn, "commit refuses cower", __FILE__, __LINE__);
        Check(stats.LearnCalls == 0 && stats.ToggleCalls == 0, "cower commit does not learn or toggle", __FILE__, __LINE__);

        ExpectOne("same-chain-guard",
            DecideCall(true, true, on, {Choice(800, 999, ACT_DISABLED)}),
            Outcome::NoLearn);
        auto chainRemoved = DecideChains(on, {Choice(800, 999, ACT_DISABLED)}, true, false, true);
        ExpectOne("same-chain-guard-removed", chainRemoved, Outcome::RestoreEnabled);
        Check(chainRemoved.size() == 1 && chainRemoved[0].Result != Outcome::NoLearn,
            "cross-chain key test fails when the chain guard is removed", __FILE__, __LINE__);

        SpellView splitVector = Choice(800, 800, ACT_DISABLED);
        splitVector.InAutospells = true;
        ExpectOne("consistency-guard", DecideChains(on, {splitVector}), Outcome::NoWrite);
        ApplyStats quiet;
        CommitResult held = CommitRestore(splitVector, true, true, true, true, quiet);
        Check(held.Claim == Outcome::NoWrite && quiet.ToggleCalls == 0, "split vector is not toggled", __FILE__, __LINE__);
        Check(held.State.InAutospells && held.State.Active == ACT_DISABLED, "split vector unchanged", __FILE__, __LINE__);

        ApplyStats noisy;
        CommitResult unguarded = CommitRestore(splitVector, true, false, false, true, noisy);
        bool const successClaimHolds = unguarded.Claim != Outcome::RestoreEnabled || unguarded.Agrees;
        Check(!successClaimHolds, "post-write key test fails when both split guards are removed", __FILE__, __LINE__);
        Check(noisy.ToggleCalls > 0, "removed consistency guard touches the spell", __FILE__, __LINE__);

        ApplyStats reverted;
        CommitResult checked = CommitRestore(splitVector, true, false, true, true, reverted);
        Check(checked.Claim == Outcome::NoWrite && !checked.Agrees, "post-check refuses a false claim", __FILE__, __LINE__);
        Check(checked.State.Active == ACT_DISABLED && checked.State.Bar == ACT_DISABLED, "post-check restores the prior byte", __FILE__, __LINE__);

        SpellView learnedOff = Choice(800, 800, ACT_DISABLED);
        ApplyStats applied;
        CommitResult restored = CommitRestore(learnedOff, true, true, true, true, applied);
        Check(restored.Claim == Outcome::RestoreEnabled && restored.Agrees, "consistent off restores on", __FILE__, __LINE__);
        Check(restored.State.Active == ACT_ENABLED && restored.State.Bar == ACT_ENABLED && restored.State.InAutospells,
            "active, bar, and vector agree", __FILE__, __LINE__);
        Check(applied.LearnCalls == 0, "restore does not learn", __FILE__, __LINE__);

        ApplyStats barLeft;
        CommitResult noBarWrite = CommitRestore(learnedOff, true, true, true, false, barLeft);
        Check(noBarWrite.Claim == Outcome::NoWrite && !noBarWrite.Agrees, "bar left behind is not claimed", __FILE__, __LINE__);
        Check(noBarWrite.State.Active == ACT_DISABLED && !noBarWrite.State.InAutospells && noBarWrite.State.Bar == ACT_DISABLED,
            "disagreement is reverted", __FILE__, __LINE__);

        SpellView noSlot = Choice(800, 800, ACT_DISABLED);
        noSlot.HasBar = false;
        ApplyStats slotStats;
        CommitResult missing = CommitRestore(noSlot, true, true, true, true, slotStats);
        Check(missing.Claim == Outcome::NoBar && !missing.State.HasBar && slotStats.ToggleCalls == 0,
            "missing bar creates no slot", __FILE__, __LINE__);
    }

    void TestHotPathAndSeam()
    {
        std::vector<SpellView> loaded{Choice(17253, 17253, ACT_ENABLED)};
        std::vector<SpellView> dropped{Choice(17255, 17253, ACT_DISABLED)};
        BaselineMemory off;
        for (int tick = 0; tick < 8; ++tick)
            Check(!SnapshotTick(false, true, true, false, true, loaded, off), "off tick skips", __FILE__, __LINE__);
        Check(off.Allocations == 0 && off.Book.empty() && !off.Pending, "off allocates nothing", __FILE__, __LINE__);

        BaselineMemory mutated;
        Check(SnapshotTick(false, true, true, false, true, loaded, mutated, false), "removed off guard snapshots", __FILE__, __LINE__);
        bool const offKeyHolds = mutated.Allocations == 0 && mutated.Book.empty();
        Check(!offKeyHolds, "off allocation key test fails when the guard is removed", __FILE__, __LINE__);

        BaselineMemory memory;
        for (int tick = 0; tick < 8; ++tick)
            Check(SnapshotTick(true, true, true, false, true, loaded, memory), "on tick snapshots", __FILE__, __LINE__);
        Check(memory.Allocations == 1, "GetDefault allocates once", __FILE__, __LINE__);

        BaselineMemory replacing;
        for (int tick = 0; tick < 8; ++tick)
            SnapshotTick(true, true, true, false, true, loaded, replacing, true, true);
        Check(replacing.Allocations == 8, "Set would allocate every tick", __FILE__, __LINE__);

        BaselineMemory loading;
        Check(!SnapshotTick(true, true, true, true, true, loaded, loading), "loading skips", __FILE__, __LINE__);
        Check(loading.Allocations == 0, "loading allocates nothing", __FILE__, __LINE__);
        BaselineMemory notPet;
        Check(!SnapshotTick(true, false, false, false, true, loaded, notPet), "non-pet skips", __FILE__, __LINE__);
        Check(notPet.Allocations == 0, "non-pet allocates nothing", __FILE__, __LINE__);
        BaselineMemory warlock;
        Check(!SnapshotTick(true, true, false, false, false, loaded, warlock), "non-hunter skips", __FILE__, __LINE__);
        Check(warlock.Allocations == 0, "non-hunter allocates nothing", __FILE__, __LINE__);

        BaselineMemory wrongOrder;
        Check(SnapshotTick(true, true, true, false, true, loaded, wrongOrder), "snapshot before event", __FILE__, __LINE__);
        RestoreOptions options;
        RestoreTickResult early = RestoreTick(wrongOrder, loaded, options);
        Check(!early.Wrote && early.Outcomes.size() == 1 && early.Outcomes[0].Result == Outcome::NoWrite,
            "restore before the event writes nothing", __FILE__, __LINE__);
        RestoreTickResult missed = RestoreTick(wrongOrder, dropped, options);
        Check(!missed.Wrote && !wrongOrder.Pending, "a second restore without a new snapshot does not repair", __FILE__, __LINE__);
        Check(missed.Book.size() == 1 && missed.Book[0].Active == ACT_DISABLED, "dropped byte remains", __FILE__, __LINE__);

        BaselineMemory ordered;
        Check(SnapshotTick(true, true, true, false, true, loaded, ordered), "ordered snapshot", __FILE__, __LINE__);
        RestoreTickResult fixed = RestoreTick(ordered, dropped, options);
        Check(fixed.Wrote && fixed.Packets == 1, "restore after the event writes once", __FILE__, __LINE__);
        Check(fixed.Book.size() == 1 && fixed.Book[0].Active == ACT_ENABLED && fixed.Book[0].Bar == ACT_ENABLED
                && fixed.Book[0].InAutospells,
            "post-write stores agree", __FILE__, __LINE__);
        Check(fixed.Stats.LearnCalls == 0, "seam does not learn", __FILE__, __LINE__);
        Check(fixed.ConsultedRealPlayer, "a real write consults the human check", __FILE__, __LINE__);

        BaselineMemory botMemory;
        Check(SnapshotTick(true, true, true, false, true, loaded, botMemory), "bot snapshot", __FILE__, __LINE__);
        RestoreOptions bot = options;
        bot.IsRealPlayer = false;
        RestoreTickResult botResult = RestoreTick(botMemory, dropped, bot);
        Check(!botResult.Wrote && botResult.ConsultedRealPlayer, "bot is consulted and not written", __FILE__, __LINE__);
        Check(botResult.Outcomes.size() == 1 && botResult.Outcomes[0].Result == Outcome::OutOfScope, "bot is out of scope", __FILE__, __LINE__);
        Check(botResult.Book[0].Active == ACT_DISABLED, "bot book unchanged", __FILE__, __LINE__);

        BaselineMemory missingApi;
        Check(SnapshotTick(true, true, true, false, true, loaded, missingApi), "missing api snapshot", __FILE__, __LINE__);
        RestoreOptions noApi = options;
        noApi.PlayerbotsApiPresent = false;
        noApi.IsRealPlayer = true;
        RestoreTickResult closed = RestoreTick(missingApi, dropped, noApi);
        Check(!closed.Wrote && !closed.ConsultedRealPlayer, "missing header fails closed without the map read", __FILE__, __LINE__);
        Check(closed.Outcomes[0].Result == Outcome::OutOfScope, "missing header is out of scope", __FILE__, __LINE__);

        BaselineMemory mismatch;
        Check(SnapshotTick(true, true, true, false, true, loaded, mismatch), "mismatch snapshot", __FILE__, __LINE__);
        RestoreOptions otherPet = options;
        otherPet.OwnerPetMatches = false;
        RestoreTickResult mismatchResult = RestoreTick(mismatch, dropped, otherPet);
        Check(!mismatchResult.Wrote && mismatchResult.ConsultedRealPlayer, "pet mismatch consults and does not write", __FILE__, __LINE__);
        Check(mismatchResult.Outcomes[0].Result == Outcome::NoWrite, "pet mismatch is no write", __FILE__, __LINE__);

        BaselineMemory unchanged;
        std::vector<SpellView> stillOn{Choice(17253, 17253, ACT_ENABLED)};
        Check(SnapshotTick(true, true, true, false, true, stillOn, unchanged), "unchanged snapshot", __FILE__, __LINE__);
        RestoreTickResult same = RestoreTick(unchanged, stillOn, options);
        Check(!same.Wrote && !same.ConsultedRealPlayer, "no proposed write skips the human read", __FILE__, __LINE__);

        BaselineMemory featureOff;
        featureOff.Pending = true;
        featureOff.Book = loaded;
        featureOff.Allocated = true;
        RestoreOptions disabled = options;
        disabled.Enabled = false;
        RestoreTickResult stayed = RestoreTick(featureOff, dropped, disabled);
        Check(!stayed.Wrote && stayed.Book[0].Active == ACT_DISABLED, "disabled restore does not mutate", __FILE__, __LINE__);
        RestoreOptions disabledUnguarded = disabled;
        disabledUnguarded.HonorEnabledGuard = false;
        BaselineMemory featureOffMutated;
        featureOffMutated.Pending = true;
        featureOffMutated.Book = loaded;
        featureOffMutated.Allocated = true;
        RestoreTickResult didWrite = RestoreTick(featureOffMutated, dropped, disabledUnguarded);
        Check(didWrite.Wrote, "removed restore guard mutates while disabled", __FILE__, __LINE__);

        std::vector<SpellView> both{
            Choice(17253, 17253, ACT_ENABLED),
            Choice(16827, 16827, ACT_DISABLED)
        };
        std::vector<SpellView> bothDropped{
            Choice(17255, 17253, ACT_DISABLED),
            Choice(16828, 16827, ACT_ENABLED)
        };
        BaselineMemory multi;
        Check(SnapshotTick(true, true, true, false, true, both, multi), "two chains snapshot", __FILE__, __LINE__);
        RestoreTickResult bothResult = RestoreTick(multi, bothDropped, options);
        Check(bothResult.Wrote && bothResult.Packets == 1, "two chains send one packet", __FILE__, __LINE__);
        Check(bothResult.Book.size() == 2, "both successors remain", __FILE__, __LINE__);
        Check(bothResult.Book[0].Active == ACT_ENABLED && bothResult.Book[1].Active == ACT_DISABLED,
            "each chain keeps its own byte", __FILE__, __LINE__);

        BaselineMemory east;
        BaselineMemory kalimdor;
        Check(SnapshotTick(true, true, true, false, true, {Choice(17253, 17253, ACT_ENABLED)}, east), "east snapshot", __FILE__, __LINE__);
        Check(SnapshotTick(true, true, true, false, true, {Choice(16827, 16827, ACT_ENABLED)}, kalimdor), "kalimdor snapshot", __FILE__, __LINE__);
        RestoreTickResult eastResult = RestoreTick(east, dropped, options);
        RestoreTickResult kalimdorResult = RestoreTick(kalimdor, {Choice(16827, 16827, ACT_ENABLED)}, options);
        Check(eastResult.Wrote, "east pet restored", __FILE__, __LINE__);
        Check(!kalimdorResult.Wrote && kalimdor.Book.size() == 1 && kalimdor.Book[0].SpellId == 16827,
            "other map pet is untouched", __FILE__, __LINE__);

        BaselineMemory pets[8];
        for (int index = 0; index < 8; ++index)
        {
            uint32_t const spellId = 17253 + static_cast<uint32_t>(index);
            Check(SnapshotTick(true, true, true, false, true, {Choice(spellId, 17253, ACT_ENABLED)}, pets[index]),
                "per-pet snapshot", __FILE__, __LINE__);
        }
        RestoreTickResult onlyThird = RestoreTick(pets[3], {Choice(27050, 17253, ACT_DISABLED)}, options);
        Check(onlyThird.Wrote, "one of eight pets restored", __FILE__, __LINE__);
        for (int index = 0; index < 8; ++index)
        {
            if (index == 3)
                continue;
            Check(pets[index].Pending && pets[index].Book.size() == 1, "other pets keep their own baseline", __FILE__, __LINE__);
            Check(pets[index].Book[0].SpellId == 17253 + static_cast<uint32_t>(index), "baselines did not cross", __FILE__, __LINE__);
        }
    }
}

#define CHECK(condition) Check((condition), #condition, __FILE__, __LINE__)

int main()
{
    TestDecisionTable();
    TestPinnedChains();
    TestGuardMutations();
    TestHotPathAndSeam();
    if (g_failed != 0)
    {
        std::cerr << g_failed << " failure(s)\n";
        return 1;
    }
    std::cout << "PASS: Hunter pet autocast restore policy\n";
    return 0;
}
