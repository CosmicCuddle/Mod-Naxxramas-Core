/*
 * Naxxramas Core — A02 human Hunter pet autocast restore policy.
 *
 * Dependency-free decision rules so tests can run without a worldserver.
 * HunterPetAutocast.cpp reads the live pet and calls these functions.
 * Design contract: docs/research/a02-hunter-autocast-functional-s1.md
 * Writer note: docs/research/a02-hunter-autocast-functional-s2.md
 *
 * The chain id is supplied by the caller. Production uses
 * SpellMgr::GetFirstSpellInChain and does not invent a link. Cower 1742
 * is never a restore target and this header never learns a spell.
 */

#ifndef NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_POLICY_H
#define NAXXRAMAS_CORE_HUNTER_PET_AUTOCAST_POLICY_H

#include <cstdint>
#include <vector>

namespace NaxxramasHunterPetAutocast
{
    constexpr uint32_t COWER_SPELL_ID = 1742;
    constexpr uint8_t ACT_PASSIVE = 0x01;
    constexpr uint8_t ACT_DISABLED = 0x81;
    constexpr uint8_t ACT_ENABLED = 0xC1;

    enum class Outcome : uint8_t
    {
        OutOfScope,
        NoWrite,
        NoLearn,
        NoBar,
        RestoreEnabled,
        RestoreDisabled
    };

    enum class WriteGate : uint8_t
    {
        OutOfScope,
        NoWrite,
        Write
    };

    struct SpellView
    {
        uint32_t SpellId = 0;
        uint32_t ChainId = 0;
        uint8_t Active = 0;
        bool Autocastable = false;
        bool HasBar = false;
        uint8_t Bar = 0;
        bool InAutospells = false;
        bool BarDuplicated = false;
        bool Present = false;
    };

    struct ChainOutcome
    {
        uint32_t ChainId = 0;
        uint32_t BaselineSpellId = 0;
        uint32_t SuccessorSpellId = 0;
        Outcome Result = Outcome::NoWrite;
    };

    struct HumanGate
    {
        WriteGate Gate = WriteGate::OutOfScope;
        bool ConsultedRealPlayer = false;
    };

    struct ApplyStats
    {
        int ToggleCalls = 0;
        int BarCalls = 0;
        int LearnCalls = 0;
    };

    struct CommitResult
    {
        Outcome Claim = Outcome::NoWrite;
        SpellView State{};
        bool Agrees = false;
    };

    struct RestoreOptions
    {
        bool Enabled = true;
        bool PlayerbotsApiPresent = true;
        bool IsRealPlayer = true;
        bool OwnerPetMatches = true;
        bool HonorEnabledGuard = true;
        bool HonorHumanGuard = true;
        bool HonorCowerGuard = true;
        bool HonorSameChain = true;
        bool HonorConsistencyGuard = true;
        bool HonorPostWriteCheck = true;
        bool WriteBar = true;
    };

    struct BaselineMemory
    {
        int Allocations = 0;
        bool Allocated = false;
        bool Pending = false;
        std::vector<SpellView> Book;
        std::vector<SpellView> Scratch;

        void GetDefault()
        {
            if (!Allocated)
            {
                Allocated = true;
                ++Allocations;
                Book.reserve(16);
                Scratch.reserve(16);
            }
        }

        // Models DataMap::Set, which is not used on the tick path.
        void SetReplace()
        {
            ++Allocations;
            Allocated = true;
            Book.clear();
            Scratch.clear();
            Book.reserve(16);
            Scratch.reserve(16);
        }
    };

    struct RestoreTickResult
    {
        std::vector<ChainOutcome> Outcomes;
        bool ConsultedRealPlayer = false;
        bool Wrote = false;
        int Packets = 0;
        ApplyStats Stats{};
        std::vector<SpellView> Book;
    };

    inline bool IsChoiceByte(uint8_t active)
    {
        return active == ACT_DISABLED || active == ACT_ENABLED;
    }

    inline bool VectorMatches(SpellView const& spell)
    {
        return spell.InAutospells == (spell.Active == ACT_ENABLED);
    }

    inline bool StoresAgree(SpellView const& spell, uint8_t wantActive)
    {
        return spell.Present && spell.Autocastable && spell.HasBar && !spell.BarDuplicated
            && spell.Active == wantActive && spell.Bar == wantActive
            && spell.InAutospells == (wantActive == ACT_ENABLED);
    }

    inline bool HotFilterPasses(
        bool enabled,
        bool isPet,
        bool hunterPet,
        bool loading,
        bool ownerIsHunterInWorld)
    {
        if (!enabled)
            return false;
        if (!isPet || !hunterPet)
            return false;
        if (loading)
            return false;
        if (!ownerIsHunterInWorld)
            return false;
        return true;
    }

    inline char const* OutcomeName(Outcome outcome)
    {
        switch (outcome)
        {
            case Outcome::OutOfScope:
                return "OUT_OF_SCOPE";
            case Outcome::NoWrite:
                return "NO_WRITE";
            case Outcome::NoLearn:
                return "NO_LEARN";
            case Outcome::NoBar:
                return "NO_BAR";
            case Outcome::RestoreEnabled:
                return "RESTORE_ENABLED";
            case Outcome::RestoreDisabled:
                return "RESTORE_DISABLED";
        }
        return "UNKNOWN";
    }

    inline bool WantsWrite(std::vector<ChainOutcome> const& outcomes)
    {
        for (ChainOutcome const& outcome : outcomes)
        {
            if (outcome.Result == Outcome::RestoreEnabled || outcome.Result == Outcome::RestoreDisabled)
                return true;
        }
        return false;
    }

    // IsRealPlayer is consulted only when a restore is already proposed.
    // A missing Playerbots API is not a human. A pet that is not
    // owner->GetPet() is NoWrite after that consultation.
    inline HumanGate AuthorizeRestore(bool playerbotsApiPresent, bool isRealPlayer, bool ownerPetMatches)
    {
        HumanGate gate;
        if (!playerbotsApiPresent)
        {
            gate.Gate = WriteGate::OutOfScope;
            gate.ConsultedRealPlayer = false;
            return gate;
        }

        gate.ConsultedRealPlayer = true;
        if (!isRealPlayer)
        {
            gate.Gate = WriteGate::OutOfScope;
            return gate;
        }
        if (!ownerPetMatches)
        {
            gate.Gate = WriteGate::NoWrite;
            return gate;
        }
        gate.Gate = WriteGate::Write;
        return gate;
    }

    inline void CollectChain(
        std::vector<SpellView> const& spells,
        uint32_t chainId,
        std::vector<SpellView>& out)
    {
        out.clear();
        for (SpellView const& spell : spells)
            if (spell.ChainId == chainId)
                out.push_back(spell);
    }

    inline std::vector<ChainOutcome> DecideChains(
        std::vector<SpellView> const& baseline,
        std::vector<SpellView> const& current,
        bool honorCowerGuard = true,
        bool honorSameChain = true,
        bool honorConsistencyGuard = true)
    {
        std::vector<SpellView> adjusted = current;
        if (!honorSameChain && !baseline.empty())
        {
            uint32_t const forced = baseline.front().ChainId;
            for (SpellView& spell : adjusted)
                spell.ChainId = forced;
        }

        std::vector<uint32_t> order;
        for (SpellView const& spell : baseline)
        {
            bool seen = false;
            for (uint32_t chainId : order)
                if (chainId == spell.ChainId)
                    seen = true;
            if (!seen)
                order.push_back(spell.ChainId);
        }

        std::vector<ChainOutcome> outcomes;
        if (order.empty())
        {
            ChainOutcome only;
            only.Result = Outcome::NoWrite;
            outcomes.push_back(only);
            return outcomes;
        }

        std::vector<SpellView> base;
        std::vector<SpellView> live;
        for (uint32_t chainId : order)
        {
            ChainOutcome outcome;
            outcome.ChainId = chainId;
            CollectChain(baseline, chainId, base);
            CollectChain(adjusted, chainId, live);

            if (base.size() != 1)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            SpellView const& chosen = base[0];
            outcome.BaselineSpellId = chosen.SpellId;
            bool const choice = IsChoiceByte(chosen.Active);
            bool const barMatches = chosen.HasBar && !chosen.BarDuplicated && chosen.Bar == chosen.Active;
            bool const vectorOk = !honorConsistencyGuard || VectorMatches(chosen);
            if (!choice || !barMatches || !vectorOk)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            bool stillThere = false;
            for (SpellView const& spell : live)
                if (spell.SpellId == chosen.SpellId)
                    stillThere = true;

            // Cower has no pinned successor. Do not copy its byte onto a
            // spell this chain map does not actually continue, and do not
            // learn 1742. The same id, still present, stays NoWrite below.
            if (honorCowerGuard && chosen.SpellId == COWER_SPELL_ID && !stillThere)
            {
                outcome.Result = Outcome::NoLearn;
                outcomes.push_back(outcome);
                continue;
            }

            if (live.empty())
            {
                outcome.Result = Outcome::NoLearn;
                outcomes.push_back(outcome);
                continue;
            }
            if (live.size() != 1)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            SpellView const& successor = live[0];
            outcome.SuccessorSpellId = successor.SpellId;
            if (successor.SpellId == chosen.SpellId || !successor.Autocastable)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }
            if (successor.SpellId == COWER_SPELL_ID)
            {
                outcome.Result = Outcome::NoLearn;
                outcomes.push_back(outcome);
                continue;
            }
            if (!successor.HasBar)
            {
                outcome.Result = Outcome::NoBar;
                outcomes.push_back(outcome);
                continue;
            }
            if (successor.BarDuplicated || successor.Bar != successor.Active)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }
            if (honorConsistencyGuard && !VectorMatches(successor))
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }
            if (successor.Active == chosen.Active && successor.Bar == chosen.Active)
            {
                outcome.Result = Outcome::NoWrite;
                outcomes.push_back(outcome);
                continue;
            }

            outcome.Result = chosen.Active == ACT_ENABLED
                ? Outcome::RestoreEnabled
                : Outcome::RestoreDisabled;
            outcomes.push_back(outcome);
        }
        return outcomes;
    }

    inline std::vector<ChainOutcome> DecideCall(
        bool enabled,
        bool human,
        std::vector<SpellView> const& baseline,
        std::vector<SpellView> const& current,
        bool honorEnabledGuard = true,
        bool honorHumanGuard = true,
        bool honorCowerGuard = true,
        bool honorSameChain = true,
        bool honorConsistencyGuard = true)
    {
        if ((honorEnabledGuard && !enabled) || (honorHumanGuard && !human))
        {
            ChainOutcome outcome;
            outcome.Result = Outcome::OutOfScope;
            return {outcome};
        }
        return DecideChains(baseline, current, honorCowerGuard, honorSameChain, honorConsistencyGuard);
    }

    // Pet.cpp:2247-2286. A vector mismatch is a no-op and does not repair active.
    inline void ModelToggle(SpellView& state, bool apply, ApplyStats& stats)
    {
        ++stats.ToggleCalls;
        if (!state.Present || !state.Autocastable)
            return;

        if (apply)
        {
            if (state.InAutospells)
                return;
            state.InAutospells = true;
            if (state.Active != ACT_ENABLED)
                state.Active = ACT_ENABLED;
            return;
        }

        if (!state.InAutospells)
            return;
        state.InAutospells = false;
        if (state.Active != ACT_DISABLED)
            state.Active = ACT_DISABLED;
    }

    // CharmInfo.cpp:291-300. A missing or duplicated slot is not rewritten here.
    inline void ModelSetBar(SpellView& state, bool enabled, ApplyStats& stats)
    {
        ++stats.BarCalls;
        if (!state.HasBar || state.BarDuplicated)
            return;
        state.Bar = enabled ? ACT_ENABLED : ACT_DISABLED;
    }

    inline CommitResult CommitRestore(
        SpellView successor,
        bool wantEnabled,
        bool honorConsistencyGuard,
        bool honorPostWriteCheck,
        bool writeBar,
        ApplyStats& stats)
    {
        CommitResult result;
        result.State = successor;
        if (successor.SpellId == COWER_SPELL_ID)
        {
            result.Claim = Outcome::NoLearn;
            return result;
        }

        uint8_t const want = wantEnabled ? ACT_ENABLED : ACT_DISABLED;
        if (!successor.Present || !successor.Autocastable || !IsChoiceByte(successor.Active))
        {
            result.Claim = Outcome::NoWrite;
            return result;
        }
        if (!successor.HasBar)
        {
            result.Claim = Outcome::NoBar;
            return result;
        }
        if (honorConsistencyGuard && (successor.Bar != successor.Active || successor.BarDuplicated || !VectorMatches(successor)))
        {
            result.Claim = Outcome::NoWrite;
            return result;
        }
        if ((successor.Active == ACT_ENABLED) == wantEnabled && StoresAgree(successor, want))
        {
            result.Claim = Outcome::NoWrite;
            result.Agrees = true;
            return result;
        }

        SpellView const before = successor;
        ModelToggle(successor, wantEnabled, stats);
        if (writeBar)
            ModelSetBar(successor, wantEnabled, stats);

        bool const agrees = StoresAgree(successor, want);
        if (honorPostWriteCheck && !agrees)
        {
            successor = before;
            result.State = successor;
            result.Claim = Outcome::NoWrite;
            result.Agrees = false;
            return result;
        }

        result.State = successor;
        result.Agrees = agrees;
        result.Claim = wantEnabled ? Outcome::RestoreEnabled : Outcome::RestoreDisabled;
        return result;
    }

    inline bool SnapshotTick(
        bool enabled,
        bool isPet,
        bool hunterPet,
        bool loading,
        bool ownerIsHunterInWorld,
        std::vector<SpellView> const& live,
        BaselineMemory& memory,
        bool honorEnabledGuard = true,
        bool useSet = false)
    {
        bool const effectiveEnabled = honorEnabledGuard ? enabled : true;
        if (!HotFilterPasses(effectiveEnabled, isPet, hunterPet, loading, ownerIsHunterInWorld))
            return false;

        if (useSet)
            memory.SetReplace();
        else
            memory.GetDefault();

        memory.Book.clear();
        memory.Book.insert(memory.Book.end(), live.begin(), live.end());
        memory.Pending = true;
        return true;
    }

    inline RestoreTickResult RestoreTick(
        BaselineMemory& memory,
        std::vector<SpellView> const& live,
        RestoreOptions const& options)
    {
        RestoreTickResult result;
        result.Book = live;
        if (options.HonorEnabledGuard && !options.Enabled)
            return result;
        if (!memory.Pending)
            return result;

        memory.Pending = false;
        result.Outcomes = DecideChains(
            memory.Book,
            live,
            options.HonorCowerGuard,
            options.HonorSameChain,
            options.HonorConsistencyGuard);

        if (!WantsWrite(result.Outcomes))
            return result;

        bool const consultHuman = options.HonorHumanGuard;
        HumanGate gate = AuthorizeRestore(
            consultHuman ? options.PlayerbotsApiPresent : true,
            consultHuman ? options.IsRealPlayer : true,
            options.OwnerPetMatches);
        if (!consultHuman)
            gate.ConsultedRealPlayer = false;
        result.ConsultedRealPlayer = gate.ConsultedRealPlayer;
        if (gate.Gate != WriteGate::Write)
        {
            Outcome const replacement = gate.Gate == WriteGate::NoWrite
                ? Outcome::NoWrite
                : Outcome::OutOfScope;
            for (ChainOutcome& outcome : result.Outcomes)
            {
                if (outcome.Result == Outcome::RestoreEnabled || outcome.Result == Outcome::RestoreDisabled)
                    outcome.Result = replacement;
            }
            return result;
        }

        for (ChainOutcome& outcome : result.Outcomes)
        {
            bool const wantEnabled = outcome.Result == Outcome::RestoreEnabled;
            if (!wantEnabled && outcome.Result != Outcome::RestoreDisabled)
                continue;
            if (options.HonorCowerGuard
                && (outcome.BaselineSpellId == COWER_SPELL_ID || outcome.SuccessorSpellId == COWER_SPELL_ID))
            {
                outcome.Result = Outcome::NoLearn;
                continue;
            }

            SpellView* slot = nullptr;
            for (SpellView& spell : result.Book)
                if (spell.SpellId == outcome.SuccessorSpellId)
                    slot = &spell;
            if (!slot)
            {
                outcome.Result = Outcome::NoWrite;
                continue;
            }

            CommitResult committed = CommitRestore(
                *slot,
                wantEnabled,
                options.HonorConsistencyGuard,
                options.HonorPostWriteCheck,
                options.WriteBar,
                result.Stats);
            *slot = committed.State;
            outcome.Result = committed.Claim;
            if (committed.Claim == Outcome::RestoreEnabled || committed.Claim == Outcome::RestoreDisabled)
                result.Wrote = true;
        }

        if (result.Wrote)
            result.Packets = 1;
        return result;
    }
}

#endif
